"""
佰信集装箱查询结果标准化路由

RPA 集装箱查询各港口（盐田/蛇口/宁波/青岛）查出的字段不一致。本接口把港口查询
原始结果文本交给 LLM，统一成佰信海运订舱字段（标准字段集 = 佰信订舱坐标模板
_baixin_fill_template.json 的 18 个容器相关字段，每项精确对应 55 个表单字段之一）。

纯展示/转换用途，不回填佰信。复用 deepseek_chat（deepseek-chat，key 走 settings 表
agent_key_deepseek_chat），做法对齐 backend/core/routers/fee.py。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.services import get_current_user_required
from backend.core.models import ContainerStandardize
from backend.addons.llm.multi_agent import get_agent_configs, create_agent_provider

router = APIRouter(prefix="/api/standardize", tags=["standardize"])

# ===== 标准字段集：18 个容器相关字段 → 佰信海运订舱字段 一一对应 =====
# 来源：_baixin_fill_template.json（sources 17 个规范 key + fields 55 个表单字段，已实测）。
# baixin_key 为佰信表单字段 key；None 表示该标准字段在 55 个表单字段中无对应项
# （container_no/seal 是订舱网格列，terminal/status 仅 sources 层有定义）。
STANDARD_FIELDS = [
    {"key": "container_no", "label": "柜号",     "baixin_key": "grid.container_no", "baixin_label": "集装箱号",   "note": "订舱网格第3列"},
    {"key": "size_type",    "label": "箱型",     "baixin_key": "size_type",        "baixin_label": "箱型箱重",   "note": ""},
    {"key": "seal",         "label": "封条",     "baixin_key": "grid.seal",        "baixin_label": "封铅号",     "note": "订舱网格第4列"},
    {"key": "gross",        "label": "毛重",     "baixin_key": "gross",            "baixin_label": "毛重",       "note": ""},
    {"key": "booking_no",   "label": "订舱单号", "baixin_key": "so_no",            "baixin_label": "S/O NO",     "note": "必填"},
    {"key": "bl_no",        "label": "提单号",   "baixin_key": "bl_no",            "baixin_label": "船东提单号", "note": ""},
    {"key": "vessel",       "label": "船名",     "baixin_key": "vessel_en",        "baixin_label": "英文船名",   "note": "必填；另有中文船名"},
    {"key": "voyage",       "label": "航次",     "baixin_key": "terminal",         "baixin_label": "航次",       "note": "模板内 key=terminal 实为航次"},
    {"key": "terminal",     "label": "码头",     "baixin_key": None,               "baixin_label": "码头/当前位置", "note": "sources 层，无表单字段"},
    {"key": "pol",          "label": "装货港",   "baixin_key": "pol",              "baixin_label": "装运港",     "note": ""},
    {"key": "dest",         "label": "目的港",   "baixin_key": "dest",             "baixin_label": "目的港+卸货港", "note": "映射 dest 与 dest_unload 两字段"},
    {"key": "eta",          "label": "ETA",      "baixin_key": "eta",              "baixin_label": "ETA",        "note": ""},
    {"key": "etd",          "label": "ETD",      "baixin_key": "etd",              "baixin_label": "ETD",        "note": ""},
    {"key": "owner",        "label": "箱主",     "baixin_key": "owner",            "baixin_label": "船东",       "note": ""},
    {"key": "status",       "label": "状态",     "baixin_key": None,               "baixin_label": "状态",       "note": "sources 层，无表单字段"},
    {"key": "pieces",       "label": "件数",     "baixin_key": "pieces",           "baixin_label": "件数",       "note": "必填"},
    {"key": "volume",       "label": "体积",     "baixin_key": "volume",           "baixin_label": "体积",       "note": "必填"},
    {"key": "cargo_name",   "label": "品名",     "baixin_key": "cargo_name",       "baixin_label": "货物简称",   "note": ""},
]

_STANDARD_KEYS = [f["key"] for f in STANDARD_FIELDS]
# 给 LLM 的 schema：key → 中文标签
_STANDARD_SCHEMA = json.dumps(
    {f["key"]: f["label"] for f in STANDARD_FIELDS}, ensure_ascii=False
)


class StandardizeRequest(BaseModel):
    port_name: str = ""
    container_no: str = ""
    raw_text: str


def _clean_fields(data: dict) -> dict:
    """规范化 18 个字段：只留字符串非空值，缺的补空串，去掉未知 key。"""
    fields = {}
    for k in _STANDARD_KEYS:
        v = data.get(k)
        fields[k] = str(v).strip() if isinstance(v, (str, int, float)) else ""
    return fields


def _save_record(db, port_name: str, container_no: str, raw_text: str,
                 fields: dict, summary: str, created_by: str) -> ContainerStandardize:
    """标准化结果落库一条（保留全部历史，同柜号不覆盖）。"""
    record = ContainerStandardize(
        port_name=port_name,
        container_no=container_no,
        raw_text=raw_text,
        fields_json=json.dumps(fields, ensure_ascii=False),
        summary=summary or "",
        created_by=created_by or "",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


class HistoryUpdateRequest(BaseModel):
    fields: dict


async def _standardize_fields(port_name: str, raw_text: str, db: Session) -> dict:
    """deepseek_chat 一步从港口结果文本抽佰信字段。返回 {success, port_name, fields, summary}。"""
    system_prompt = (
        "你是货代订舱助手。把港口集装箱查询结果统一成佰信海运订舱标准字段。\n"
        f"查询港口: {port_name or '未知'}\n"
        "输入是某港口（盐田/蛇口/宁波/青岛）查询集装箱后得到的原始文本，格式各港不同\n"
        "（可能是中文标签行、key=value、表格区块）。你的任务：\n"
        "- 逐字段把文本中出现的值填到对应标准字段，值原样保留、去掉多余空白\n"
        "- 字段的取值优先级：优先该港明确标注的值；多值冲突取最相关的\n"
        "- 船名/航次可能拆在多个字段里（如 进港船名航次、离港船名航次），取出口/当前一票的\n"
        "- 封条号 seal：青岛港的 QFH/QFH1 就是封条号，其它港口看 封条/封铅号/封条号 标签，值带斜杠也照填\n"
        "- 港口结果里查不到的字段填空字符串，绝不臆造或猜测\n"
        "- 件数/毛重/体积取数字（可带单位，原样保留），金额/时间格式不变\n"
        "返回 ONLY 有效 JSON，不要任何解释，不要 markdown。Schema 的 key 与中文含义:\n"
        + _STANDARD_SCHEMA
    )

    agents = get_agent_configs(db)
    agent = next((a for a in agents if a.name == "deepseek_chat"), agents[0] if agents else None)
    if not agent:
        return {"success": False, "error": "没有可用的 LLM Agent"}
    provider = create_agent_provider(agent)
    resp = await provider.chat(
        messages=[{"role": "user", "content": raw_text}],
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

    fields = _clean_fields(data)
    filled = [k for k in _STANDARD_KEYS if fields[k]]
    return {
        "success": True,
        "port_name": (data.get("port_name") or port_name or "").strip(),
        "fields": fields,
        "summary": (data.get("summary") or f"识别出 {len(filled)} 个字段，其余留空").strip(),
    }


@router.post("/parse")
async def parse_standardize(
    body: StandardizeRequest,
    db: Session = Depends(get_db),
    auth_user=Depends(get_current_user_required),
):
    raw_text = (body.raw_text or "").strip()
    if not raw_text:
        return {"success": False, "error": "请先粘贴港口查询结果"}
    port_name = (body.port_name or "").strip()
    container_no = (body.container_no or "").strip()
    result = await _standardize_fields(port_name, raw_text, db)
    if result.get("success"):
        result["container_no"] = container_no
        record = _save_record(
            db, port_name, container_no, raw_text,
            result["fields"], result.get("summary", ""),
            getattr(auth_user, "username", "") or "",
        )
        result["id"] = record.id
    return result


@router.get("/history")
async def list_history(
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """标准化历史列表，按时间倒序（保留全部历史）。"""
    rows = db.query(ContainerStandardize).order_by(
        ContainerStandardize.created_at.desc()
    ).all()
    items = []
    for r in rows:
        try:
            fields = json.loads(r.fields_json or "{}")
        except json.JSONDecodeError:
            fields = {}
        fields = _clean_fields(fields)
        items.append({
            "id": r.id,
            "port_name": r.port_name or "",
            "container_no": r.container_no or "",
            "summary": r.summary or "",
            "created_by": r.created_by or "",
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "filled_count": sum(1 for v in fields.values() if v),
            "fields": fields,
        })
    return {"success": True, "items": items}


@router.put("/history/{record_id}")
async def update_history(
    record_id: int,
    body: HistoryUpdateRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """手改保存：更新该条的 18 字段值。"""
    record = db.query(ContainerStandardize).filter(
        ContainerStandardize.id == record_id
    ).first()
    if not record:
        return {"success": False, "error": "记录不存在"}
    record.fields_json = json.dumps(_clean_fields(body.fields), ensure_ascii=False)
    record.updated_at = datetime.now()
    db.commit()
    return {"success": True, "id": record.id}


@router.delete("/history/{record_id}")
async def delete_history(
    record_id: int,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    record = db.query(ContainerStandardize).filter(
        ContainerStandardize.id == record_id
    ).first()
    if not record:
        return {"success": False, "error": "记录不存在"}
    db.delete(record)
    db.commit()
    return {"success": True, "id": record_id}
