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
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """非流式聊天。"""
    user = _get_user((authorization or "").replace("Bearer ", ""), db) if authorization else None

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


async def _chat_with_tools(
    orchestrator,
    agent_name: str,
    messages: list[dict],
    system_prompt: str,
) -> str:
    """工具调用循环：发送消息 → 处理工具调用 → 继续调用 → 返回最终文本。"""
    import logging
    from backend.addons.llm.tools import RPA_TOOLS, execute_tool_call

    provider = orchestrator.providers.get(agent_name)
    if not provider:
        return f"Agent '{agent_name}' 不可用"

    current_messages = list(messages)
    max_rounds = 5  # 防止无限循环

    for _round in range(max_rounds):
        resp = await provider.chat(
            messages=current_messages,
            system_prompt=system_prompt,
            tools=RPA_TOOLS,
        )

        if resp.tool_calls:
            for tc in resp.tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                args = func.get("arguments", "{}")
                tc_id = tc.get("id", "")

                logging.info(f"[tool_call] round={_round} name={tool_name} args={args}")

                # 执行工具
                tool_result = await execute_tool_call(tool_name, args)

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
        else:
            return (resp.content or "").strip()

    return "⚠️ 工具调用次数过多，请简化查询条件。"


class MultiAgentChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    agent_name: str = ""          # 指定Agent, 空=自动路由
    parallel: bool = False         # 是否并行调用所有Agent
    file_contexts: list[dict] = []  # [{file_id, filename, text, ...}]


@router.post("/multi-agent/send")
async def multi_agent_send(
    req: MultiAgentChatRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
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
        if req.agent_name == "nim_minimax":
            content = await _chat_with_tools(orchestrator, req.agent_name, messages, system)
            return {
                "success": True,
                "mode": "single",
                "agent": agent.display_name,
                "agent_name": req.agent_name,
                "model": agent.model,
                "content": content,
                "tool_enabled": True,
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
            "query_port": "nim_minimax",
            "query_rate": "nim_deepseek",
            "track_cargo": "nim_minimax",
            "generate_letter": "nim_gpt",
            "merge_docs": "nim_gpt",
            "fill_bill": "nim_gpt",
            "translate": "nim_gpt",
            "analysis": "nim_deepseek",
            "general": "nim_minimax",
        }
        agent_name = intent_map.get(intent, "nim_qwen")
        if agent_name not in orchestrator.providers:
            available = orchestrator.get_agent_names()
            agent_name = available[0] if available else None
        if not agent_name:
            return {"success": False, "error": "没有可用的Agent"}

        agent = orchestrator.get_agent(agent_name)

        # MiniMax 启用工具调用
        if agent_name == "nim_minimax":
            content = await _chat_with_tools(orchestrator, agent_name, messages, system)
            return {
                "success": True,
                "mode": "routed",
                "intent": intent,
                "agent": agent.display_name if agent else agent_name,
                "agent_name": agent_name,
                "model": agent.model if agent else "",
                "content": content,
                "tool_enabled": True,
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
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
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
                if req.agent_name == "nim_minimax":
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'tool_calling'}, ensure_ascii=False)}\n\n"
                    tool_content = await _chat_with_tools(orchestrator, req.agent_name, messages, system)
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'streaming'}, ensure_ascii=False)}\n\n"
                    # 将工具调用结果作为完整文本输出
                    yield f"data: {json.dumps({'type': 'text', 'content': tool_content}, ensure_ascii=False)}\n\n"
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
                    "query_port": "nim_minimax",
                    "query_rate": "nim_deepseek",
                    "track_cargo": "nim_minimax",
                    "generate_letter": "nim_gpt",
                    "merge_docs": "nim_gpt",       # qwen DEGRADED
                    "fill_bill": "nim_gpt",
                    "translate": "nim_gpt",         # qwen DEGRADED
                    "analysis": "nim_deepseek",
                    "general": "nim_minimax",       # qwen DEGRADED
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
                if agent_name == "nim_minimax":
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'tool_calling'}, ensure_ascii=False)}\n\n"
                    tool_content = await _chat_with_tools(orchestrator, agent_name, messages, system)
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'streaming'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'text', 'content': tool_content}, ensure_ascii=False)}\n\n"
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
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
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
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
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
async def list_agents(db: Session = Depends(get_db)):
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
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
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
