"""
OAIW LLM Provider 抽象基类
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """Provider 配置，可从 DB 或环境变量读取。"""
    provider: str = "deepseek"
    api_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    extra: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 调用的统一返回类型。"""
    content: str = ""
    tool_calls: Optional[list[dict]] = None


class BaseLLMProvider(ABC):
    """所有 LLM Provider 的抽象基类。"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        ...
