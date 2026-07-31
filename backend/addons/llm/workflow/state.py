"""
OAIW Chat Workflow State — LangGraph 状态定义

当前用 dataclass，未来 LangGraph 原生支持 TypedDict 后可直接迁移。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OAIWState:
    """工作流全局状态 — 所有 Node 读写该对象的字段。"""

    # === 输入 ===
    user_message: str = ""
    history: list[dict] = field(default_factory=list)
    user_role: str = "operator"
    user_name: str = ""
    conversation_id: Optional[str] = None

    # === Agent 识别 ===
    intent: str = ""             # 用户意图分类: query_price | fill_letter | track_cargo | general
    agent_route: str = ""        # 路由到哪个 Agent: price | letter | cargo | general

    # === Node 产出 ===
    kb_context: str = ""         # 知识库检索结果
    rag_context: str = ""        # 记忆检索结果
    rpa_result: str = ""         # RPA 浏览器操作结果
    system_prompt: str = ""      # 拼好的完整 system prompt
    llm_response: str = ""       # LLM 原始回复
    tool_calls: Optional[list[dict]] = None

    # === 输出 ===
    reply: str = ""
    error: Optional[str] = None

    # === Provider 配置 ===
    provider_type: str = "deepseek"
    provider_api_url: str = "https://api.deepseek.com/v1"
    provider_api_key: str = ""
    provider_model: str = "deepseek-chat"
