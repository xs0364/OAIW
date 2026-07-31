"""
OAIW 聊天工作流 — 线性编排（准备升级 LangGraph）

节点顺序：
1. 意图识别 (classify_intent)
2. 拼装 prompt (build_prompt)
3. 调用 LLM (call_llm)
4. 解析回复 (parse_reply)

未来 LangGraph 升级：
```python
from langgraph.graph import StateGraph
graph = StateGraph(OAIWState)
graph.add_node("classify", classify_intent)
graph.add_node("build", build_prompt)
graph.add_node("llm", call_llm)
graph.add_node("parse", parse_reply)
graph.add_conditional_edges("classify", route_agent, {...})
graph.set_entry_point("classify")
app = graph.compile()
"""
from __future__ import annotations

from typing import Optional

from backend.addons.llm.workflow.state import OAIWState
from backend.addons.llm.workflow.nodes import (
    classify_intent,
    build_prompt,
    call_llm,
    parse_reply,
)
from backend.addons.llm.redis_cache import get_llm_cache, set_llm_cache, is_available
from backend.config import settings


async def run_workflow(
    user_message: str,
    history: list[dict] | None = None,
    user_role: str = "operator",
    user_name: str = "",
    provider_type: str = "deepseek",
    provider_api_url: str = "https://api.deepseek.com/v1",
    provider_api_key: str = "",
    provider_model: str = "deepseek-chat",
) -> tuple[str, Optional[str]]:
    """
    运行聊天工作流（带 Redis 缓存）。

    Returns:
        (reply_text, error_message)
    """
    state = OAIWState(
        user_message=user_message,
        history=history or [],
        user_role=user_role,
        user_name=user_name,
        provider_type=provider_type,
        provider_api_url=provider_api_url,
        provider_api_key=provider_api_key,
        provider_model=provider_model,
    )

    # 串行执行节点
    state = await classify_intent(state)
    state = await build_prompt(state)

    # === Redis 缓存：通用查询（非工具类）走缓存 ===
    cached = None
    if settings.REDIS_ENABLED and state.intent in ("general", "query_rate", "analysis"):
        cached = get_llm_cache(
            message=user_message,
            history=history or [],
            model=provider_model,
        )
        if cached:
            state.reply = cached
            state.llm_response = cached
            return state.reply, None

    state = await call_llm(state)
    state = await parse_reply(state)

    # 缓存 LLM 回复
    if settings.REDIS_ENABLED and state.reply and not state.error:
        try:
            set_llm_cache(
                message=user_message,
                history=history or [],
                reply=state.reply,
                model=provider_model,
                ttl=settings.REDIS_LLM_CACHE_TTL,
            )
        except Exception:
            pass

    return state.reply, state.error
