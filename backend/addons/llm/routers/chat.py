"""
OAIW 聊天路由 — 支持流式 + 非流式对话 + 文件上下文
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Header, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import settings
from backend.core.services import get_current_user_required
from backend.addons.llm.workflow.workflow import run_workflow
from backend.parser import extract_text

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 文件上下文 — 每文件最多截取字符数
MAX_FILE_TEXT_CHARS = 6000


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    stream: bool = False
    file_contexts: list[dict] = []  # [{file_id, filename, text, ...}]


class ChatResponse(BaseModel):
    reply: str
    intent: str = ""


def _get_user(token: str, db: Session):
    """从 token 获取用户信息。"""
    from backend.core.services import get_current_user
    user = get_current_user(token, db)
    if not user:
        return None
    return user


@router.post("/send")
async def chat_send(
    req: ChatRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """非流式聊天。"""
    user = _auth_user

    # 注入文件上下文
    file_text = _build_file_context_text(req.file_contexts or [])
    enriched_message = req.message
    if file_text:
        enriched_message = f"{file_text}\n\n---\n用户提问: {req.message}"

    if req.stream:
        return StreamingResponse(
            _stream_chat(req, user),
            media_type="text/event-stream",
        )

    reply, error = await run_workflow(
        user_message=enriched_message,
        history=req.history,
        user_role=user.role if user else "operator",
        user_name=user.display_name if user else "",
        user_id=user.id if user else None,
        provider_type=settings.DEEPSEEK_API_URL and "deepseek" or "ollama",
        provider_api_url=settings.DEEPSEEK_API_URL,
        provider_api_key=settings.DEEPSEEK_API_KEY,
        provider_model=settings.DEEPSEEK_MODEL,
    )
    return {"reply": reply or error or "请求失败", "intent": ""}


# ===== 多Agent聊天 =====

def _build_file_context_text(file_contexts: list[dict]) -> str:
    """将文件上下文列表拼成 system prompt 片段。"""
    if not file_contexts:
        return ""
    parts = ["当前上下文包含以下文件："]
    for fc in file_contexts:
        filename = fc.get("filename", "未知文件")
        text = fc.get("text", "")
        # 截断到最大字符数
        if len(text) > MAX_FILE_TEXT_CHARS:
            text = text[:MAX_FILE_TEXT_CHARS] + "\n...[内容已截断]"
        parts.append(f"\n## {filename}\n{text}\n")
    return "\n".join(parts)


# ===== 保函意图分流 =====
# 保函 docx 生成不依赖模型工具自觉：服务端确定性判定「生成保函」请求并直接走模板填写，
# 避免 deepseek_chat 在多轮对话下 auto tool-calling 不稳定（单轮可触发、多轮不触发）的问题。

_LETTER_ACTIONS = ("填", "生成", "做", "出", "写", "按", "根据", "直接", "帮我", "请")
_LETTER_STRONG_ACTIONS = ("填", "生成", "帮我", "请", "直接", "按", "根据")  # 咨询疑问下仍视为生成命令
_LETTER_TOPICS = ("保函", "非危", "电放", "危险品", "化工", "电池", "模板", "word", "docx", "sds", "鉴定书", "loi")
_LETTER_NEGATIVES = ("不要", "别", "不用", "算了", "取消", "不生成", "先不")
_LETTER_QUESTIONS = ("是什么", "什么", "怎么", "流程", "解释", "说明", "区别", "如何", "吗", "?", "？")
_LETTER_CONTINUE = ("模板", "word", "docx", "生成", "填", "按", "出", "做", "文件", "保函")

# /multi-agent/send 注入文件上下文的前缀标记（file_text + 分隔 + 用户真实提问）
_ASK_MARK = "---\n用户提问: "


def _strip_file_context(content: str) -> str:
    """剥离 /multi-agent/send 注入的 file_contexts 文本段，只保留用户真实提问。

    file_contexts 拼入 user 消息后，模板文件名（如「非危保函.docx」）会污染
    保函主题判定——上传过模板后问别的事（如查集装箱）会被误判为保函生成。
    判定只看注入标记之后的部分；未注入的原始消息原样返回。
    """
    if _ASK_MARK in content:
        return content.split(_ASK_MARK, 1)[1]
    return content


def _letter_kind(file_contexts, low_text: str) -> str:
    """判定保函类型：模板文件名优先，其次消息关键词；默认 dg。"""
    for fc in (file_contexts or []):
        fn = (fc.get("filename") or "").lower()
        if fn.endswith((".docx", ".doc")):
            if "电放" in fn:
                return "telex"
            if any(k in fn for k in ("非危", "non-dg", "chemical", "危险品")):
                return "dg"
    if "电放" in low_text:
        return "telex"
    if any(k in low_text for k in ("非危", "电池", "化工", "危险品")):
        return "dg"
    return "dg"


def _classify_letter_request(messages: list[dict], file_contexts: list[dict] | None) -> str | None:
    """判定当前请求是否为保函生成请求，返回 'dg'/'telex'；非生成请求返回 None。

    - 当前消息命中「动作词 + 保函主题」→ 生成
    - 历史已保函主题 + 当前含延续词（模板/word/生成…）→ 生成（覆盖「直接用word模版」场景）
    - 纯咨询（疑问词且无动作词）、否定、与保函无关 → None（走正常模型回答）
    """
    if not messages:
        return None
    # 剥离 file_contexts 注入段，只看用户真实提问（避免模板文件名污染主题判定）
    user_msgs = [_strip_file_context(m.get("content", "")) for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return None
    current = (user_msgs[-1] or "").strip()
    history = " ".join(user_msgs[-3:-1])
    text = current + " " + history
    low = text.lower()

    # 否定优先
    if any(n in current for n in _LETTER_NEGATIVES):
        return None

    has_topic = any(t in low for t in _LETTER_TOPICS)
    has_action = any(a in current for a in _LETTER_ACTIONS)
    has_strong = any(s in current for s in _LETTER_STRONG_ACTIONS)
    is_question = any(q in current for q in _LETTER_QUESTIONS)

    if not has_topic:
        return None

    # 咨询疑问：除非含强命令词（填/生成/帮我/请/直接/按/根据），否则视为咨询不生成
    if is_question:
        return _letter_kind(file_contexts, low) if has_strong else None

    # 当前消息直接命中：保函主题 + 动作词
    if has_action:
        return _letter_kind(file_contexts, low)

    # 延续识别：历史已保函主题 + 当前是延续指令（模板/word/生成/填/文件…）
    if any(t in history.lower() for t in _LETTER_TOPICS) and any(cw in current for cw in _LETTER_CONTINUE):
        return _letter_kind(file_contexts, low)

    return None


async def _handle_letter_request(orchestrator, messages: list[dict], file_contexts: list[dict] | None, kind: str) -> str:
    """服务端确定性执行保函生成：提取字段 → 填模板(docx) → 无模板时纯文本兜底。"""
    import json
    from backend.addons.llm.tools import _try_fill_nonhazardous_docx, _try_fill_telex_docx

    # 1. 一次轻量 LLM 提取字段（非工具调用，不依赖模型对工具的认知）
    args: dict = {}
    provider = orchestrator.providers.get("deepseek_chat")
    if provider:
        try:
            ctx = _build_file_context_text(file_contexts)
            history_text = "\n".join(m.get("content", "") for m in messages if m.get("content"))
            extract_sys = (
                "你是国际货运操作助手。从下面的对话和文件内容中提取保函填写字段，"
                "只输出 JSON 对象，不要输出任何其他文字。可用的键（缺失的省略）："
                "carrier(船公司), vessel(船名), voyage(航次), pol(起运港), pod(目的港), "
                "bl_no(提单号), container_no(柜号), 中文品名, 英文品名, CAS_NO, "
                "外观与性状, 主要用途, shipper(发货人), consignee(收货人)。"
            )
            resp = await provider.chat(
                messages=[{"role": "user", "content": f"对话内容：\n{history_text[:8000]}\n\n文件内容：\n{ctx[:4000]}"}],
                system_prompt=extract_sys,
                temperature=0.1,
                max_tokens=1024,
            )
            raw = (resp.content or "").strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                args = parsed
        except Exception:
            args = {}

    # 2. 模板填写（复用 tools.py _try_fill_*，内含模板匹配 + 校验 + 下载链接）
    carrier = (args.get("carrier") or "").strip()
    if kind == "telex":
        docx_md = await _try_fill_telex_docx(args, file_contexts, carrier)
    else:
        docx_md = await _try_fill_nonhazardous_docx(args, file_contexts, carrier)
    if docx_md:
        return docx_md

    # 3. 纯文本兜底（复用 rpa.py _generate_*_letter）
    from datetime import date
    from backend.core.routers.rpa import _generate_non_hazardous_letter, _generate_telex_letter
    if not carrier:
        return "❌ 生成保函：缺少船公司/航司名称（carrier），请补充。"

    if kind == "telex":
        data = {
            "date": date.today().isoformat(),
            "bl_no": (args.get("bill_of_lading_no") or args.get("bl_no") or "").strip(),
            "pol": (args.get("port_of_loading") or args.get("pol") or "").strip(),
            "pod": (args.get("port_of_discharge") or args.get("pod") or "").strip(),
            "container_no": (args.get("container_no") or "").strip(),
            "shipper": (args.get("shipper") or "").strip(),
            "consignee": (args.get("consignee") or "").strip(),
        }
        return f"📄 电放保函已生成：\n\n{_generate_telex_letter(carrier, data)}"

    goods = (args.get("goods_name") or args.get("中文品名") or "").strip()
    dg = (args.get("danger_class") or "").strip()
    commodity = f"{goods}（危险品类别/UN编号: {dg}）" if (goods and dg) else (goods or dg)
    data = {
        "date": date.today().isoformat(),
        "pol": (args.get("port_of_loading") or args.get("pol") or "").strip(),
        "commodity": commodity,
        "container_no": (args.get("container_no") or "").strip(),
        "shipper": (args.get("shipper") or "").strip(),
        "consignee": (args.get("consignee") or "").strip(),
    }
    return f"📄 非危保函已生成：\n\n{_generate_non_hazardous_letter(carrier, data)}"


async def _chat_with_tools(
    orchestrator,
    agent_name: str,
    messages: list[dict],
    system_prompt: str,
    file_contexts: list[dict] | None = None,
    user_id: int | None = None,
) -> str:
    """工具调用循环：发送消息 → 处理工具调用 → 继续调用 → 返回最终文本。

    file_contexts 来自对话上传文件（[{file_id, filename, ext, ...}]），
    传给保函类工具用于定位用户上传的 docx 模板。
    user_id 用于按用户配置执行的工具（如 send_email_to_user 用本人邮箱）。
    """
    import logging
    from backend.addons.llm.tools import (
        RPA_TOOLS, OAIW_TOOLS, BAIXIN_FILL_TOOL, BAIXIN_FEE_FILL_TOOL, BAIXIN_PENDING_PREFIX, execute_tool_call,
    )

    provider = orchestrator.providers.get(agent_name)
    if not provider:
        return f"Agent '{agent_name}' 不可用"

    current_messages = list(messages)
    max_rounds = 5  # 防止无限循环

    # 保函意图分流：确定性生成 docx，不经过模型工具决策
    kind = _classify_letter_request(current_messages, file_contexts)
    if kind:
        return await _handle_letter_request(orchestrator, current_messages, file_contexts, kind)

    for _round in range(max_rounds):
        resp = await provider.chat(
            messages=current_messages,
            system_prompt=system_prompt,
            tools=RPA_TOOLS + OAIW_TOOLS + [BAIXIN_FILL_TOOL, BAIXIN_FEE_FILL_TOOL],
        )

        if resp.tool_calls:
            doc_results = []
            for tc in resp.tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                args = func.get("arguments", "{}")
                tc_id = tc.get("id", "")

                logging.info(f"[tool_call] round={_round} name={tool_name} args={args}")

                # 执行工具
                tool_result = await execute_tool_call(tool_name, args, file_contexts, user_id=user_id)

                # 佰信填值/费用录入：不继续工具循环，把待确认参数交给调用方
                # （execute 已返回 BAIXIN_PENDING_PREFIX + args_json）
                if tool_name in ("baixin_merge_fill", "baixin_fee_fill"):
                    return tool_result

                # 保函/合并等成文文档工具：结果即最终交付物，直接返回——
                # 不再喂回 LLM 续写（否则保函全文会被模型润色成摘要，用户拿不到可复制的完整文件）
                if tool_name in ("generate_dg_letter", "generate_telex_letter", "merge_invoice_packing"):
                    doc_results.append(tool_result)

                # 添加 assistant 回应（含 tool_calls）
                current_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc],
                })
                # 添加 tool 执行结果
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_result,
                })

            if doc_results:
                return "\n\n".join(doc_results)
        else:
            return (resp.content or "").strip()

    return "⚠️ 工具调用次数过多，请简化查询条件。"


def _split_baixin_pending(content: str):
    """若 content 是佰信待确认包装（BAIXIN_PENDING_PREFIX + args_json），
    返回 (args_dict, 给用户看的摘要文本)；否则返回 (None, content)。"""
    from backend.addons.llm.tools import BAIXIN_PENDING_PREFIX
    if content and content.startswith(BAIXIN_PENDING_PREFIX):
        import json as _json
        try:
            args = _json.loads(content[len(BAIXIN_PENDING_PREFIX):])
            return args, args.get("summary") or "已识别佰信填值字段，请确认后再录入"
        except Exception:
            return None, content
    return None, content


class MultiAgentChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    agent_name: str = ""          # 指定Agent, 空=自动路由
    parallel: bool = False         # 是否并行调用所有Agent
    file_contexts: list[dict] = []  # [{file_id, filename, text, ...}]


@router.post("/multi-agent/send")
async def multi_agent_send(
    req: MultiAgentChatRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """多Agent聊天 — 支持指定Agent/自动路由/并行执行。"""
    from backend.addons.llm.multi_agent import get_agent_configs, MultiAgentOrchestrator

    agents = get_agent_configs(db)
    orchestrator = MultiAgentOrchestrator(agents)

    # 注入文件上下文
    file_text = _build_file_context_text(req.file_contexts or [])
    enriched_message = req.message
    if file_text:
        enriched_message = f"{file_text}\n\n---\n用户提问: {req.message}"

    messages = list(req.history)
    messages.append({"role": "user", "content": enriched_message})

    system = "你是西岸国际货运代理有限公司操作部的AI助手。请用中文回答，专业、简洁、准确。"

    if req.parallel:
        # 并行：所有Agent同时回答（RAG增强）
        results = await orchestrator.chat_all(messages, system_prompt=system, user_message=enriched_message)
        return {
            "success": True,
            "mode": "parallel",
            "results": {
                name: {
                    "agent": orchestrator.get_agent(name).display_name if orchestrator.get_agent(name) else name,
                    "content": resp.content or "",
                    "model": orchestrator.get_agent(name).model if orchestrator.get_agent(name) else name,
                }
                for name, resp in results.items()
            },
        }
    elif req.agent_name:
        # 指定Agent（RAG增强）
        agent = orchestrator.get_agent(req.agent_name)
        if not agent:
            return {"success": False, "error": f"Agent '{req.agent_name}' 不存在"}

        # MiniMax 注入工具调用能力
        if req.agent_name == "deepseek_chat":
            content = await _chat_with_tools(orchestrator, req.agent_name, messages, system, req.file_contexts, user_id=_auth_user.id)
            baixin_args, text = _split_baixin_pending(content)
            return {
                "success": True,
                "mode": "single",
                "agent": agent.display_name,
                "agent_name": req.agent_name,
                "model": agent.model,
                "content": text,
                "tool_enabled": True,
                **({"baixin_confirm": baixin_args} if baixin_args else {}),
            }

        resp = await orchestrator.chat(req.agent_name, messages, system_prompt=system, user_message=enriched_message)
        return {
            "success": True,
            "mode": "single",
            "agent": agent.display_name,
            "agent_name": req.agent_name,
            "model": agent.model,
            "content": resp.content or "",
        }
    else:
        # 自动路由: 先做意图分类再选Agent
        from backend.addons.llm.multi_agent import simple_classify_intent
        intent = simple_classify_intent(req.message)
        intent_map = {
            "query_port": "deepseek_chat",
            "query_rate": "nim_deepseek",
            "track_cargo": "deepseek_chat",
            "generate_letter": "deepseek_chat",
            "merge_docs": "deepseek_chat",
            "fill_bill": "deepseek_chat",
            "send_email": "deepseek_chat",
            "translate": "nim_gpt",
            "analysis": "nim_deepseek",
            "general": "deepseek_chat",
        }
        agent_name = intent_map.get(intent, "nim_qwen")
        if agent_name not in orchestrator.providers:
            available = orchestrator.get_agent_names()
            agent_name = available[0] if available else None
        if not agent_name:
            return {"success": False, "error": "没有可用的Agent"}

        agent = orchestrator.get_agent(agent_name)

        # MiniMax 启用工具调用
        if agent_name == "deepseek_chat":
            content = await _chat_with_tools(orchestrator, agent_name, messages, system, req.file_contexts, user_id=_auth_user.id)
            baixin_args, text = _split_baixin_pending(content)
            return {
                "success": True,
                "mode": "routed",
                "intent": intent,
                "agent": agent.display_name if agent else agent_name,
                "agent_name": agent_name,
                "model": agent.model if agent else "",
                "content": text,
                "tool_enabled": True,
                **({"baixin_confirm": baixin_args} if baixin_args else {}),
            }

        # 其他Agent走常规对话
        resp = await orchestrator.chat(agent_name, messages, system_prompt=system, user_message=enriched_message)
        return {
            "success": True,
            "mode": "routed",
            "intent": intent,
            "agent": agent.display_name if agent else agent_name,
            "agent_name": agent_name,
            "model": agent.model if agent else "",
            "content": resp.content or "",
        }


@router.post("/multi-agent/send/stream")
async def multi_agent_send_stream(
    req: MultiAgentChatRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """多Agent聊天 — 流式SSE输出，支持指定Agent/自动路由。"""
    from backend.addons.llm.multi_agent import get_agent_configs, MultiAgentOrchestrator, simple_classify_intent

    agents = get_agent_configs(db)
    orchestrator = MultiAgentOrchestrator(agents)

    file_text = _build_file_context_text(req.file_contexts or [])
    enriched_message = req.message
    if file_text:
        enriched_message = f"{file_text}\n\n---\n用户提问: {req.message}"

    messages = list(req.history)
    messages.append({"role": "user", "content": enriched_message})

    system = "你是西岸国际货运代理有限公司操作部的AI助手。请用中文回答，专业、简洁、准确。"

    async def _stream_events():
        try:
            if req.agent_name:
                agent = orchestrator.get_agent(req.agent_name)
                if not agent:
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Agent 不存在'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                # MiniMax 先执行工具调用循环（非流式）
                if req.agent_name == "deepseek_chat":
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'tool_calling'}, ensure_ascii=False)}\n\n"
                    tool_content = await _chat_with_tools(orchestrator, req.agent_name, messages, system, req.file_contexts, user_id=_auth_user.id)
                    baixin_args, text = _split_baixin_pending(tool_content)
                    if baixin_args:
                        # 佰信填值 → 推待确认卡参数给前端
                        tool_name = 'baixin_fee_fill' if baixin_args.get('kind') == 'fee' else 'baixin_merge_fill'
                        yield f"data: {json.dumps({'type': 'tool_confirm', 'tool': tool_name, 'args': baixin_args}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'agent': agent.display_name, 'agent_name': agent.name, 'model': agent.model or '', 'tool_enabled': True}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'streaming'}, ensure_ascii=False)}\n\n"
                    # 将工具调用结果作为完整文本输出
                    yield f"data: {json.dumps({'type': 'text', 'content': text}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'agent': agent.display_name, 'agent_name': agent.name, 'model': agent.model or '', 'tool_enabled': True}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                async for event in orchestrator.chat_stream(
                    agent_name=req.agent_name,
                    messages=messages,
                    system_prompt=system,
                    user_message=req.message,
                ):
                    if event["type"] == "text":
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'agent': agent.display_name, 'agent_name': agent.name, 'model': agent.model or ''}, ensure_ascii=False)}\n\n"
            else:
                intent = simple_classify_intent(req.message)
                intent_map = {
                    "query_port": "deepseek_chat",
                    "query_rate": "nim_deepseek",
                    "track_cargo": "deepseek_chat",
                    "generate_letter": "deepseek_chat",
                    "merge_docs": "deepseek_chat",
                    "fill_bill": "deepseek_chat",
                    "send_email": "deepseek_chat",
                    "translate": "nim_gpt",         # qwen DEGRADED
                    "analysis": "nim_deepseek",
                    "general": "deepseek_chat",       # qwen DEGRADED
                }
                agent_name = intent_map.get(intent, "nim_qwen")
                if agent_name not in orchestrator.providers:
                    available = orchestrator.get_agent_names()
                    agent_name = available[0] if available else None
                if not agent_name:
                    yield f"data: {json.dumps({'type': 'error', 'content': '没有可用的Agent'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                agent = orchestrator.get_agent(agent_name)

                # 路由到 MiniMax 时启用工具调用
                if agent_name == "deepseek_chat":
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'tool_calling'}, ensure_ascii=False)}\n\n"
                    tool_content = await _chat_with_tools(orchestrator, agent_name, messages, system, req.file_contexts, user_id=_auth_user.id)
                    baixin_args, text = _split_baixin_pending(tool_content)
                    if baixin_args:
                        # 佰信填值 → 推待确认卡参数给前端
                        tool_name = 'baixin_fee_fill' if baixin_args.get('kind') == 'fee' else 'baixin_merge_fill'
                        yield f"data: {json.dumps({'type': 'tool_confirm', 'tool': tool_name, 'args': baixin_args}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'intent': intent, 'agent': agent.display_name if agent else agent_name, 'agent_name': agent_name, 'model': agent.model if agent else '', 'tool_enabled': True}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'streaming'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'text', 'content': text}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'intent': intent, 'agent': agent.display_name if agent else agent_name, 'agent_name': agent_name, 'model': agent.model if agent else '', 'tool_enabled': True}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                async for event in orchestrator.chat_stream(
                    agent_name=agent_name,
                    messages=messages,
                    system_prompt=system,
                    user_message=req.message,
                ):
                    if event["type"] == "text":
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'intent': intent, 'agent': agent.display_name if agent else agent_name, 'agent_name': agent_name, 'model': agent.model if agent else ''}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_events(),
        media_type="text/event-stream",
    )


@router.post("/multi-agent/collaborate")
async def multi_agent_collaborate(
    req: MultiAgentChatRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """一呼百应 — 所有Agent从各自专业视角并行分析，由最强Agent合成统一回复。"""
    from backend.addons.llm.multi_agent import get_agent_configs, MultiAgentOrchestrator

    agents = get_agent_configs(db)
    orchestrator = MultiAgentOrchestrator(agents)

    # 注入文件上下文
    file_text = _build_file_context_text(req.file_contexts or [])
    enriched_message = req.message
    if file_text:
        enriched_message = f"{file_text}\n\n---\n用户提问: {req.message}"

    messages = list(req.history)
    messages.append({"role": "user", "content": enriched_message})

    result = await orchestrator.chat_collaborate(
        messages=messages,
        user_message=enriched_message,
    )

    return {
        "success": True,
        "mode": "collaborate",
        "synthesized": result["synthesized"],
        "synthesizer": result["synthesizer"],
        "contributions": result["contributions"],
    }


@router.post("/multi-agent/collaborate/stream")
async def multi_agent_collaborate_stream(
    req: MultiAgentChatRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """流式协作 — 先并行收集各Agent回复，再流式输出合成结果。"""
    from backend.addons.llm.multi_agent import get_agent_configs, MultiAgentOrchestrator

    agents = get_agent_configs(db)
    orchestrator = MultiAgentOrchestrator(agents)

    # 注入文件上下文
    file_text = _build_file_context_text(req.file_contexts or [])
    enriched_message = req.message
    if file_text:
        enriched_message = f"{file_text}\n\n---\n用户提问: {req.message}"

    messages = list(req.history)
    messages.append({"role": "user", "content": enriched_message})

    async def _stream_events():
        try:
            async for event in orchestrator.chat_collaborate_stream(
                messages=messages,
                user_message=enriched_message,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_events(),
        media_type="text/event-stream",
    )


@router.get("/multi-agent/list")
async def list_agents(db: Session = Depends(get_db),
                      _auth_user=Depends(get_current_user_required)):
    """列出可用的Agent配置。"""
    from backend.addons.llm.multi_agent import get_agent_configs
    agents = get_agent_configs(db)
    return {
        "success": True,
        "agents": [
            {
                "name": a.name,
                "display_name": a.display_name,
                "model": a.model,
                "description": a.description,
                "configured": bool(a.api_key),
            }
            for a in agents
        ],
    }


async def _stream_chat(req: ChatRequest, user):
    """流式聊天 SSE。"""
    from backend.addons.llm.providers import create_provider
    from backend.addons.llm.providers.base import LLMConfig

    config = LLMConfig(
        provider="deepseek",
        api_url=settings.DEEPSEEK_API_URL,
        api_key=settings.DEEPSEEK_API_KEY,
        model=settings.DEEPSEEK_MODEL,
    )
    provider = create_provider(config)

    # 注入文件上下文
    file_text = _build_file_context_text(req.file_contexts or [])
    enriched_message = req.message
    if file_text:
        enriched_message = f"{file_text}\n\n---\n用户提问: {req.message}"

    messages = list(req.history)
    messages.append({"role": "user", "content": enriched_message})

    try:
        async for event in provider.chat_stream(messages=messages):
            if event["type"] == "text":
                yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


# ===== 文件上下文上传 =====

ALLOWED_CONTEXT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".png", ".jpg", ".jpeg"}


@router.post("/upload-context-file")
async def upload_context_file(
    file: UploadFile,
    conversation_id: str = Form(...),
    db: Session = Depends(get_db),
    _auth_user=Depends(get_current_user_required),
):
    """上传文件到当前对话上下文。

    支持格式: pdf, docx, xlsx, txt, png, jpg
    返回: { success, file_id, filename, file_size, text_preview }
    """
    # 验证文件类型
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_CONTEXT_EXTENSIONS:
        return {"success": False, "error": f"不支持的文件类型: {ext}，支持: pdf/docx/xlsx/txt/png/jpg"}

    # 创建上传目录
    upload_dir = os.path.join(
        settings.UPLOAD_DIR, "context_files", str(conversation_id)
    )
    os.makedirs(upload_dir, exist_ok=True)

    # 生成唯一文件名保存
    file_id = str(uuid.uuid4())
    save_path = os.path.join(upload_dir, f"{file_id}{ext}")

    content_bytes = await file.read()
    with open(save_path, "wb") as f:
        f.write(content_bytes)

    # 提取文本
    extracted = extract_text(save_path)

    # 截取预览（前200字）和完整文本（截断到 MAX_FILE_TEXT_CHARS）
    text_preview = extracted[:200] if len(extracted) > 200 else extracted
    text_full = extracted[:MAX_FILE_TEXT_CHARS] if len(extracted) > MAX_FILE_TEXT_CHARS else extracted

    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename or "未知文件",
        "file_size": len(content_bytes),
        "ext": ext,
        "text_preview": text_preview,
        "text": text_full,
    }
