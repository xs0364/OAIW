"""
佰信费用粘贴识别路由

操作员把 Excel/邮件/其他系统的费用内容复制粘贴进「佰信合并录入」页费用卡
→ LLM 抽取为多行费用（应收 recv_* / 应付 pay_*）→ 前端填充多行表格核对后一键填佰信。

复用 deepseek_chat（deepseek-chat，key 走 settings 表 agent_key_deepseek_chat）做一次性
JSON 抽取，做法对齐 backend/addons/llm/llm_service.py::extract_json。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.services import get_current_user_required
from backend.addons.llm.multi_agent import get_agent_configs, create_agent_provider

router = APIRouter(prefix="/api/fee", tags=["fee"])

# 多行费用抽取 schema（给 LLM 的字段说明，不含具体值）
_FEE_SCHEMA = (
    '{"mode":"sea|air","order_no":"工作号(可空,如 SB-A26080130)",'
    '"rows":[{"recv_trader":"应收往来单位","recv_amount":"应收金额","recv_qty":"应收数量","recv_price":"应收单价",'
    '"pay_trader":"应付往来单位","pay_amount":"应付金额","pay_qty":"应付数量","pay_price":"应付单价"}],'
    '"summary":"识别摘要(中文)"}'
)

_FEE_FIELD_KEYS = (
    "recv_trader", "recv_amount", "recv_qty", "recv_price",
    "pay_trader", "pay_amount", "pay_qty", "pay_price",
)


class FeeParseRequest(BaseModel):
    text: str


def _clean_row(r) -> Optional[dict]:
    """规范化一行费用：只保留费用 key + 非空值；全空返回 None。"""
    if not isinstance(r, dict):
        return None
    row = {}
    for k in _FEE_FIELD_KEYS:
        v = r.get(k)
        if isinstance(v, (str, int, float)):
            s = str(v).strip()
            if s:
                row[k] = s
    return row or None


async def _extract_fee_rows(text: str, db: Session) -> dict:
    """deepseek_chat 一次性抽取多行费用。返回 {success, mode, order_no, rows, summary} 或错误。"""
    system_prompt = (
        "你是货代应收应付登记助手。从用户粘贴的费用内容中抽取费用行。\n"
        "内容可能来自邮件正文、Excel 表格复制块(Tab/换行分隔)、聊天记录。\n"
        "规则：\n"
        "- 每个费用项一行：应收填 recv_*，应付填 pay_*；往来单位原样，金额/数量/单价纯数字(如 12500、12500.00、10)\n"
        "- 一行里同时有应收和应付就都填，只有一边就只填那边；不要单位符号、不要格式化货币\n"
        "- 只填内容中出现的字段，不臆造；往来单位缺失就省略对应字段\n"
        "- 用户没给工作号时 order_no 填空串；模式推断：工作号 SB-A 前缀或含航班/始发站→air，SB-S 或船名/柜号→sea，否则按上下文\n"
        "返回 ONLY 有效 JSON，不要任何解释，不要 markdown。Schema:\n"
        + _FEE_SCHEMA
    )

    agents = get_agent_configs(db)
    agent = next((a for a in agents if a.name == "deepseek_chat"), agents[0] if agents else None)
    if not agent:
        return {"success": False, "error": "没有可用的 LLM Agent"}
    provider = create_agent_provider(agent)
    resp = await provider.chat(
        messages=[{"role": "user", "content": text}],
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=2048,
    )
    content = resp.content.strip() if resp and resp.content else ""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if not match:
            return {"success": False, "error": f"LLM 返回无法解析: {content[:200]}"}
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return {"success": False, "error": f"LLM 返回无法解析: {content[:200]}"}

    if not isinstance(data, dict):
        return {"success": False, "error": "LLM 返回格式错误"}

    raw_rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    rows = [r for r in (_clean_row(r) for r in raw_rows) if r]
    mode = (data.get("mode") or "").strip().lower()
    order_no = (data.get("order_no") or "").strip().upper()
    if mode not in ("sea", "air"):
        mode = "air" if order_no.startswith("SB-A") else "sea"
    if not rows:
        return {"success": False, "error": "未识别到任何费用行，请检查粘贴内容"}
    return {
        "success": True,
        "mode": mode,
        "order_no": order_no,
        "rows": rows,
        "summary": (data.get("summary") or "").strip(),
    }


@router.post("/parse")
async def parse_fee(
    body: FeeParseRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    text = (body.text or "").strip()
    if not text:
        return {"success": False, "error": "请先粘贴费用内容"}
    return await _extract_fee_rows(text, db)
