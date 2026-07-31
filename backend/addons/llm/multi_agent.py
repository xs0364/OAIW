"""
OAIW 多Agent智能体编排 — 英伟达NIM多模型协作

支持:
- 3个独立Agent (不同模型/Key)
- 意图路由: 自动分配合适Agent
- 并行执行: 多个Agent同时处理
- Agent切换: 手动指定Agent处理
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from backend.addons.llm.providers.base import LLMConfig, LLMResponse
from backend.addons.llm.providers.openai_compat import OpenAICompatProvider

# 英伟达NIM API 基础地址
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"


@dataclass
class AgentProfile:
    """单个Agent配置。"""
    name: str
    display_name: str
    api_key: str
    model: str
    api_url: str = NVIDIA_API_BASE
    description: str = ""
    enabled: bool = True


def simple_classify_intent(message: str) -> str:
    """简单的意图分类（同步版本，不依赖OAIWState）。"""
    msg = message.lower()
    if any(k in msg for k in ["码头", "开港", "进港", "放行", "装船", "港口状态"]):
        return "query_port"
    if any(k in msg for k in ["运价", "价格", "多少钱", "运费", "rate", "查价"]):
        return "query_rate"
    if any(k in msg for k in ["保函", "非危", "电池", "化工", "电放"]):
        return "generate_letter"
    if any(k in msg for k in ["箱单", "发票", "合并", "拼柜"]):
        return "merge_docs"
    if any(k in msg for k in ["账单", "佰信", "录入"]):
        return "fill_bill"
    if any(k in msg for k in ["跟踪", "货物", "到哪", "航班", "状态", "查货"]):
        return "track_cargo"
    return "general"


# 预置4个英伟达Agent配置 (key从settings表读取)
AGENT_DEFAULTS = [
    AgentProfile(
        name="nim_gpt",
        display_name="GPT-OSS 120B",
        api_key="",
        model="openai/gpt-oss-120b",
        description="通用推理，适合复杂业务逻辑分析、合同审核、决策建议",
    ),
    AgentProfile(
        name="nim_qwen",
        display_name="Llama 3.1 70B",
        api_key="",
        model="meta/llama-3.1-70b-instruct",
        api_url=NVIDIA_API_BASE,
        description="综合能力强，多语言翻译好，适合文档处理、翻译、摘要",
    ),
    AgentProfile(
        name="nim_minimax",
        display_name="DeepSeek Chat",
        api_key="",
        model="deepseek-chat",
        api_url=DEEPSEEK_API_BASE,
        description="DeepSeek官方API，适合快速问答、港口查询、货物跟踪",
    ),
    AgentProfile(
        name="nim_deepseek",
        display_name="Nemotron Super 120B",
        api_key="",
        model="nvidia/nemotron-3-super-120b-a12b",
        description="英伟达顶级推理模型，适合复杂分析、运价走势分析、利润预测、业务决策",
    ),
]


def get_agent_configs(db: Session) -> list[AgentProfile]:
    """从数据库读取Agent配置 (预设 + 自定义, key/url存储在settings表)。"""
    from backend.core.models.setting import Setting

    agents = []
    for default in AGENT_DEFAULTS:
        key_setting = db.query(Setting).filter(
            Setting.key == f"agent_key_{default.name}"
        ).first()
        url_setting = db.query(Setting).filter(
            Setting.key == f"agent_url_{default.name}"
        ).first()
        api_key = key_setting.value if key_setting else ""
        api_url = url_setting.value if url_setting else default.api_url
        agents.append(AgentProfile(
            name=default.name,
            display_name=default.display_name,
            api_key=api_key or default.api_key,
            api_url=api_url,
            model=default.model,
            description=default.description,
        ))

    # 加载自定义Agent
    try:
        custom = db.query(Setting).filter(Setting.key == "agent_custom_list").first()
        if custom and custom.value:
            import json
            for item in json.loads(custom.value):
                agents.append(AgentProfile(
                    name=item.get("name", ""),
                    display_name=item.get("display_name", item.get("name", "")),
                    api_key=item.get("api_key", ""),
                    api_url=item.get("api_url", NVIDIA_API_BASE),
                    model=item.get("model", ""),
                    description=item.get("description", ""),
                ))
    except Exception:
        logging.warning("[multi_agent] failed to parse custom agent config")

    return agents


def create_agent_provider(agent: AgentProfile) -> OpenAICompatProvider:
    """为单个Agent创建Provider实例。"""
    config = LLMConfig(
        provider="openai",
        api_url=agent.api_url,
        api_key=agent.api_key,
        model=agent.model,
    )
    return OpenAICompatProvider(config)


class MultiAgentOrchestrator:
    """多Agent编排器 — 管理和调度多个LLM Agent + RAG知识检索。"""

    # 每个Agent的专业System Prompt前缀
    AGENT_SYSTEM_PROMPTS = {
        "nim_gpt": (
            "你是【GPT-OSS 业务分析专家】。\n"
            "你的专长：复杂业务逻辑分析、合同审核、决策建议、信函起草。\n"
            "请从业务分析视角回答，侧重业务流程合规性、风险提示和优化建议。\n"
            "回答力求专业、有条理，适当给出具体建议。"
        ),
        "nim_qwen": (
            "你是【Llama 文档处理专家】。\n"
            "你的专长：中英文双语处理、文档翻译、摘要提取、箱单发票合并等文档相关任务。\n"
            "请从文档处理视角回答，确保信息准确、格式规范、语言通顺。\n"
            "如果涉及翻译或文档格式问题，请给出专业处理建议。"
        ),
        "nim_minimax": (
            "你是【DeepSeek 快速查询专家】。\n"
            "你的专长：快速查询港口状态、跟踪货物、获取实时数据、查阅操作信息。\n"
            "请从数据查询视角回答，只提供确凿的事实性信息。\n"
            "回答应简明扼要，以数据为核心，不做过多的推测。"
        ),
        "nim_deepseek": (
            "你是【Nemotron 深度分析专家】。\n"
            "你的专长：运价走势分析、市场预测、利润分析、复杂业务决策。\n"
            "请从战略分析视角回答，要深入透彻，给出数据驱动的洞见。\n"
            "回答结构清晰，先结论后分析，必要时提供数据支撑。"
        ),
    }

    def __init__(self, agents: list[AgentProfile], enable_rag: bool = True):
        self.agents = {a.name: a for a in agents if a.enabled}
        self.providers = {
            name: create_agent_provider(a)
            for name, a in self.agents.items()
        }
        self.enable_rag = enable_rag

    def get_agent_names(self) -> list[str]:
        return list(self.agents.keys())

    def get_agent(self, name: str) -> Optional[AgentProfile]:
        return self.agents.get(name)

    def _build_rag_context(self, user_message: str) -> str:
        """检索知识库，返回格式化的上下文片段。"""
        if not self.enable_rag:
            return ""
        try:
            from backend.addons.rag import search_knowledge, format_knowledge_context
            results = search_knowledge(user_message, top_k=5)
            if results:
                return format_knowledge_context(results)
        except Exception:
            pass
        return ""

    def _build_system_prompt(self, base_prompt: str, rag_context: str) -> str:
        """拼接含RAG上下文的system prompt。"""
        if rag_context:
            return f"{base_prompt}\n\n{rag_context}"
        return base_prompt

    async def chat_collaborate(
        self,
        messages: list[dict],
        user_message: str = "",
        temperature: float = 0.7,
    ) -> dict:
        """
        一呼百应 — 所有Agent从各自专业视角并行分析，由最强Agent合成统一回复。

        返回:
            {
                "synthesized": "合成后的统一回复",
                "synthesizer": "nim_deepseek",
                "contributions": {
                    "nim_minimax": { "agent": "MiniMax M3", "content": "...", "model": "..." },
                    "nim_gpt": { ... },
                    "nim_qwen": { ... },
                    "nim_deepseek": { ... },
                }
            }
        """
        import asyncio
        import datetime

        # 1. RAG上下文（共享给所有Agent）
        rag_context = self._build_rag_context(user_message or messages[-1].get("content", "") if messages else "")

        # 2. 并行调用所有Agent（各有专长System Prompt）
        base_info = f"\n\n当前用户消息: {user_message}"
        tasks = {}
        for name, provider in self.providers.items():
            prompt = self.AGENT_SYSTEM_PROMPTS.get(name, "")
            if rag_context:
                prompt += f"\n\n【知识库参考】\n{rag_context}"
            prompt += base_info
            tasks[name] = asyncio.create_task(
                provider.chat(
                    messages=messages,
                    system_prompt=prompt,
                    temperature=temperature,
                )
            )

        # 3. 收集结果
        contributions = {}
        for name, task in tasks.items():
            try:
                resp = await task
                agent = self.get_agent(name)
                contributions[name] = {
                    "agent": agent.display_name if agent else name,
                    "content": resp.content or "[无回复]",
                    "model": agent.model if agent else name,
                }
            except Exception as e:
                contributions[name] = {
                    "agent": name,
                    "content": f"[{name} 执行失败: {str(e)}]",
                    "model": "",
                }

        # 4. 用最强Agent（Nemotron/DeepSeek）合成统一回复
        #    按优先级选合成器: nim_deepseek > nim_gpt > nim_qwen > nim_minimax > 第一个可用
        synthesizer_priority = ["nim_deepseek", "nim_gpt", "nim_qwen", "nim_minimax"]
        synthesizer_name = None
        for name in synthesizer_priority:
            if name in self.providers and contributions.get(name, {}).get("content", "").strip():
                synthesizer_name = name
                break
        if not synthesizer_name:
            synthesizer_name = next(iter(self.providers.keys()), None)

        if synthesizer_name:
            try:
                synthesis_prompt = """你是西岸国际货运代理有限公司操作部的首席AI专家（Nemotron Super）。
你的任务是将多个专业AI助手的分析结果**合成一份统一、连贯、专业的回答**。

## 合成原则
1. **取长补短**：综合各分析中有价值的信息，去除重复内容
2. **结构清晰**：按逻辑组织（先结论、后分析、再建议）
3. **保持一致**：避免矛盾表述，如有冲突以深度分析专家结论为准
4. **保留专业视角**：适当标注信息来源（如"业务分析：..."、"数据查询：..."）
5. **简洁专业**：最终回答不超过500字，用中文

## 各Agent的分析结果
"""
                for name, contrib in contributions.items():
                    agent_name = contrib.get("agent", name)
                    content_summary = contrib.get("content", "")[:2000]
                    synthesis_prompt += f"\n--- {agent_name} 的分析 ---\n{content_summary}\n"

                synthesis_prompt += "\n\n请输出合成后的统一回复，以「📋 综合AI分析」开头。"

                synth_provider = self.providers.get(synthesizer_name)
                if synth_provider:
                    synth_resp = await synth_provider.chat(
                        messages=[{"role": "user", "content": synthesis_prompt}],
                        system_prompt="你是一个专业的回答合成专家。",
                        temperature=0.3,
                    )
                    synthesized = synth_resp.content or ""
                else:
                    # fallback: 拼接所有
                    synthesized = self._fallback_synthesize(contributions)
            except Exception as e:
                synthesized = self._fallback_synthesize(contributions)
        else:
            synthesized = self._fallback_synthesize(contributions)

        return {
            "synthesized": synthesized.strip(),
            "synthesizer": synthesizer_name or "",
            "contributions": contributions,
        }

    async def chat_collaborate_stream(
        self,
        messages: list[dict],
        user_message: str = "",
        temperature: float = 0.7,
    ):
        """流式协作 — 先并行收集各Agent回复，再流式输出合成结果。

        Yields dicts with SSE event data:
            {"type": "status", "phase": "collecting"}
            {"type": "status", "phase": "synthesizing"}
            {"type": "synth", "content": "..."}
            {"type": "done", "contributions": {...}, "synthesized": "...", "synthesizer": "..."}
        """
        import asyncio

        # 1. Status: collecting
        yield {"type": "status", "phase": "collecting"}

        # 2. RAG上下文（共享给所有Agent）
        rag_context = self._build_rag_context(user_message or messages[-1].get("content", "") if messages else "")

        # 3. 并行调用所有Agent（各有专长System Prompt）
        base_info = f"\n\n当前用户消息: {user_message}"
        tasks = {}
        for name, provider in self.providers.items():
            prompt = self.AGENT_SYSTEM_PROMPTS.get(name, "")
            if rag_context:
                prompt += f"\n\n【知识库参考】\n{rag_context}"
            prompt += base_info
            tasks[name] = asyncio.create_task(
                provider.chat(
                    messages=messages,
                    system_prompt=prompt,
                    temperature=temperature,
                )
            )

        # 4. 收集结果
        contributions = {}
        for name, task in tasks.items():
            try:
                resp = await task
                agent = self.get_agent(name)
                contributions[name] = {
                    "agent": agent.display_name if agent else name,
                    "content": resp.content or "[无回复]",
                    "model": agent.model if agent else name,
                }
            except Exception as e:
                contributions[name] = {
                    "agent": name,
                    "content": f"[{name} 执行失败: {str(e)}]",
                    "model": "",
                }

        # 5. Status: synthesizing
        yield {"type": "status", "phase": "synthesizing"}

        # 6. 用最强Agent（Nemotron/DeepSeek）流式合成统一回复
        synthesizer_priority = ["nim_deepseek", "nim_gpt", "nim_qwen", "nim_minimax"]
        synthesizer_name = None
        for name in synthesizer_priority:
            if name in self.providers and contributions.get(name, {}).get("content", "").strip():
                synthesizer_name = name
                break
        if not synthesizer_name:
            synthesizer_name = next(iter(self.providers.keys()), None)

        synthesized = ""
        if synthesizer_name:
            try:
                synthesis_prompt = """你是西岸国际货运代理有限公司操作部的首席AI专家（Nemotron Super）。
你的任务是将多个专业AI助手的分析结果**合成一份统一、连贯、专业的回答**。

## 合成原则
1. **取长补短**：综合各分析中有价值的信息，去除重复内容
2. **结构清晰**：按逻辑组织（先结论、后分析、再建议）
3. **保持一致**：避免矛盾表述，如有冲突以深度分析专家结论为准
4. **保留专业视角**：适当标注信息来源（如"业务分析：..."、"数据查询：..."）
5. **简洁专业**：最终回答不超过500字，用中文

## 各Agent的分析结果
"""
                for name, contrib in contributions.items():
                    agent_name = contrib.get("agent", name)
                    content_summary = contrib.get("content", "")[:2000]
                    synthesis_prompt += f"\n--- {agent_name} 的分析 ---\n{content_summary}\n"

                synthesis_prompt += "\n\n请输出合成后的统一回复，以「📋 综合AI分析」开头。"

                synth_provider = self.providers.get(synthesizer_name)
                if synth_provider:
                    async for event in synth_provider.chat_stream(
                        messages=[{"role": "user", "content": synthesis_prompt}],
                        system_prompt="你是一个专业的回答合成专家。",
                        temperature=0.3,
                    ):
                        if event["type"] == "text":
                            synthesized += event["content"]
                            yield {"type": "synth", "content": event["content"]}
                else:
                    synthesized = self._fallback_synthesize(contributions)
                    yield {"type": "synth", "content": synthesized}
            except Exception:
                synthesized = self._fallback_synthesize(contributions)
                yield {"type": "synth", "content": synthesized}
        else:
            synthesized = self._fallback_synthesize(contributions)
            yield {"type": "synth", "content": synthesized}

        # 7. Final done event with all contributions
        yield {
            "type": "done",
            "contributions": contributions,
            "synthesized": synthesized.strip(),
            "synthesizer": synthesizer_name or "",
        }

    def _fallback_synthesize(self, contributions: dict) -> str:
        """合成器失败时的降级方案：直接拼接各Agent回答。"""
        parts = ["📋 综合AI分析（各Agent独立回答）\n"]
        for name, contrib in contributions.items():
            content = contrib.get("content", "")
            if content and content != "[无回复]":
                parts.append(f"\n--- {contrib.get('agent', name)} ---\n{content}")
        return "\n".join(parts)

    async def chat(
        self,
        agent_name: str,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        user_message: str = "",
    ) -> LLMResponse:
        """调用指定Agent进行对话（自动注入RAG上下文）。"""
        provider = self.providers.get(agent_name)
        if not provider:
            raise ValueError(f"Agent '{agent_name}' 不存在或未启用")

        # RAG检索增强
        rag_context = self._build_rag_context(user_message or messages[-1].get("content", "") if messages else "")
        final_system = self._build_system_prompt(system_prompt or "", rag_context)

        return await provider.chat(
            messages=messages,
            system_prompt=final_system,
            temperature=temperature,
        )

    async def chat_all(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        user_message: str = "",
    ) -> dict[str, LLMResponse]:
        """所有Agent并行执行同一任务（自动注入RAG上下文）。"""
        import asyncio
        rag_context = self._build_rag_context(user_message or messages[-1].get("content", "") if messages else "")
        final_system = self._build_system_prompt(system_prompt or "", rag_context)

        tasks = {}
        for name, provider in self.providers.items():
            tasks[name] = asyncio.create_task(
                provider.chat(
                    messages=messages,
                    system_prompt=final_system,
                    temperature=temperature,
                )
            )
        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                results[name] = LLMResponse(content=f"[{name} 执行失败: {str(e)}]")
        return results

    async def chat_stream(
        self,
        agent_name: str,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        user_message: str = "",
    ):
        """流式调用指定Agent进行对话（自动注入RAG上下文）。

        Yields dicts with SSE event data:
            {"type": "text", "content": "..."}
        """
        provider = self.providers.get(agent_name)
        if not provider:
            raise ValueError(f"Agent '{agent_name}' 不存在或未启用")

        # RAG检索增强
        rag_context = self._build_rag_context(
            user_message or (messages[-1].get("content", "") if messages else "")
        )
        final_system = self._build_system_prompt(system_prompt or "", rag_context)

        async for event in provider.chat_stream(
            messages=messages,
            system_prompt=final_system,
            temperature=temperature,
        ):
            yield event

    async def route_by_intent(
        self,
        intent: str,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        user_message: str = "",
    ) -> tuple[str, LLMResponse]:
        """根据意图自动路由到最合适的Agent（自动注入RAG上下文）。"""
        # 意图 -> Agent 映射
        # nim_deepseek: 深度推理/分析/运价/决策
        # nim_gpt: 合同审核/复杂文档/写信
        # nim_qwen: 中英双语/翻译/通用
        # nim_minimax: 快速查询/港口状态
        intent_map = {
            "query_port": "nim_minimax",
            "query_rate": "nim_deepseek",
            "track_cargo": "nim_minimax",
            "generate_letter": "nim_gpt",
            "merge_docs": "nim_qwen",
            "fill_bill": "nim_gpt",
            "translate": "nim_qwen",
            "analysis": "nim_deepseek",
            "general": "nim_qwen",
        }
        agent_name = intent_map.get(intent, "nim_qwen")
        # fallback: 如果首选不可用则用第一个可用
        if agent_name not in self.providers:
            agent_name = next(iter(self.providers.keys()), None)
        if not agent_name:
            raise RuntimeError("没有可用的Agent")
        resp = await self.chat(agent_name, messages, system_prompt, temperature=0.7, user_message=user_message)
        return agent_name, resp
