"""
OAIW Workflow Nodes — 每个 Node 是一个独立的处理函数

节点的输入输出统一为 OAIWState，方便未来升级为 LangGraph StateGraph。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from backend.addons.llm.workflow.state import OAIWState


async def classify_intent(state: OAIWState) -> OAIWState:
    """Node 1: 意图识别 — 判断用户想做什么。"""
    msg = state.user_message.lower()

    if any(k in msg for k in ["码头", "开港", "进港", "放行", "装船", "港口状态"]):
        state.intent = "query_port"
        state.agent_route = "rpa_port"
    elif any(k in msg for k in ["运价", "价格", "多少钱", "运费", "rate", "查价"]):
        state.intent = "query_rate"
        state.agent_route = "rpa_rate"
    elif any(k in msg for k in ["保函", "非危", "电池", "化工", "电放"]):
        state.intent = "generate_letter"
        state.agent_route = "letter"
    elif any(k in msg for k in ["箱单", "发票", "合并", "拼柜"]):
        state.intent = "merge_docs"
        state.agent_route = "docs"
    elif any(k in msg for k in ["账单", "佰信", "录入"]):
        state.intent = "fill_bill"
        state.agent_route = "rpa_bill"
    elif any(k in msg for k in ["跟踪", "货物", "到哪", "航班", "状态"]):
        state.intent = "track_cargo"
        state.agent_route = "rpa_track"
    else:
        state.intent = "general"
        state.agent_route = "general"

    return state


async def build_prompt(state: OAIWState) -> OAIWState:
    """Node 2(可选): 根据意图拼接 system prompt。"""
    base_prompt = """你是西岸国际货运代理有限公司操作部AI助手。
你帮助操作员处理日常货运操作，包括查询码头状态、查运价、生成保函、合并文档、录入账单等。
请用中文回复，专业、简洁、准确。

当前用户信息：
- 角色：{role}
- 姓名：{name}
"""

    intent_guides = {
        "query_port": "用户想查询码头状态。如果需要，使用 RPA 工具自动查码头网站。",
        "query_rate": "用户想查询运价。如果需要，使用 RPA 工具查船公司官网或共享报价表。",
        "generate_letter": "用户需要生成保函。请确认货物信息和船司后生成对应格式的保函。",
        "merge_docs": "用户需要合并箱单发票。请获取各工厂文件后合并为标准格式。",
        "fill_bill": "用户需要录入账单到佰信系统。请确认账单金额和业务单号。",
        "track_cargo": "用户想跟踪货物状态。使用 RPA 查询航班或船期信息。",
        "general": "用户有一般性问题，直接回答。",
    }

    guide = intent_guides.get(state.intent, intent_guides["general"])
    state.system_prompt = base_prompt.format(role=state.user_role, name=state.user_name) + f"\n识别到的意图：{state.intent}\n{guide}"
    return state


async def call_llm(state: OAIWState) -> OAIWState:
    """Node 3: 调用大模型生成回复。"""
    # 检查是否配置了 API Key
    if not state.provider_api_key and state.provider_type == "deepseek":
        state.llm_response = _fallback_reply(state)
        return state

    try:
        from backend.addons.llm.providers import create_provider
        from backend.addons.llm.providers.base import LLMConfig
        from backend.addons.llm.workflow.tools import TOOLS

        config = LLMConfig(
            provider=state.provider_type,
            api_url=state.provider_api_url,
            api_key=state.provider_api_key,
            model=state.provider_model,
        )
        provider = create_provider(config)

        messages = list(state.history) if state.history else []
        context_parts = []
        if state.kb_context:
            context_parts.append(f"【知识库参考】\n{state.kb_context}")
        if state.rag_context:
            context_parts.append(f"【历史记忆参考】\n{state.rag_context}")
        if state.rpa_result:
            context_parts.append(f"【RPA 查询结果】\n{state.rpa_result}")

        if context_parts:
            messages.append({"role": "system", "content": f"以下是从系统中获取的参考信息：\n\n" + "\n\n".join(context_parts)})

        messages.append({"role": "user", "content": state.user_message})

        resp = await provider.chat(
            messages=messages,
            system_prompt=state.system_prompt,
            tools=TOOLS if state.intent != "general" else None,
        )
        state.llm_response = resp.content
        state.tool_calls = resp.tool_calls
    except Exception as e:
        state.llm_response = _fallback_reply(state, error=str(e))
    return state


def _fallback_reply(state: OAIWState, error: str = "") -> str:
    """没有 API Key 或 LLM 调用失败时，基于规则回复。"""
    if error:
        print(f"[LLM Fallback] {error}")

    replies = {
        "query_port": "🔍 码头状态查询功能需要配置 API Key 后才能使用。\n\n当前支持查询：盐田港、蛇口港、上海港、宁波港、青岛港。",
        "generate_letter": "📄 保函生成功能需要配置 API Key 后才能使用。\n\n支持非危保函、电放保函等格式。",
        "merge_docs": "📑 文档合并功能需要配置 API Key 后才能使用。\n\n支持多家工厂箱单发票合并。",
        "fill_bill": "💰 账单录入功能需要配置 API Key 后才能使用。\n\n支持自动录入佰信系统。",
        "track_cargo": "🚚 货物跟踪功能需要配置 API Key 后才能使用。\n\n支持查询航班状态、货物位置。",
        "general": f"您好！我是操作部AI助手。\n\n我可以帮您：\n• 查询码头状态 — 「查盐田港状态」\n• 查询船司运价 — 「MSK 盐田到汉堡多少钱」\n• 填写非危保函 — 「生成电池非危保函」\n• 填写电放保函 — 「生成电放保函」\n• 合并箱单发票 — 「合并拼柜箱单」\n• 录入佰信账单 — 「录入同行账单」\n• 跟踪货物状态 — 「查货物到哪了」\n\n请在系统设置中配置 API Key 后使用完整功能。",
    }
    return replies.get(state.intent, replies["general"])


async def parse_reply(state: OAIWState) -> OAIWState:
    """Node 4: 解析 LLM 回复，提取工具调用结果或最终回复。"""
    if state.tool_calls:
        # 有工具调用 — 执行工具并记录结果
        results = []
        for tc in state.tool_calls:
            fn = tc["function"]
            results.append(f"调用工具: {fn['name']}\n参数: {fn['arguments']}")
        state.reply = state.llm_response + "\n\n" + "\n".join(results)
    else:
        state.reply = state.llm_response or "抱歉，我暂时无法处理这个问题。"
    return state


async def route_to_agent(state: OAIWState) -> OAIWState:
    """路由 Node: 根据意图决定下一步走哪个 Agent 子流程。"""
    # 目前所有路由最终都走 LLM
    # 后续可以扩展为条件分支：
    # if state.agent_route == "rpa_port": → 执行 RPA Port Agent
    # if state.agent_route == "letter": → 执行保函生成 Agent
    return state
