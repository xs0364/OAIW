"""
OAIW LLM Provider 工厂

支持多模型供应商统一调用。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.addons.llm.providers.base import LLMConfig


def get_provider_config_from_db(db: Session) -> LLMConfig:
    """从数据库 settings 表读取主模型配置。"""
    from backend.core.models.setting import Setting

    def _get(key: str, default: str = "") -> str:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s and s.value else default

    provider = _get("llm_provider", "deepseek")
    return LLMConfig(
        provider=provider,
        api_url=_get("llm_api_url", "https://api.deepseek.com/v1"),
        api_key=_get("llm_api_key", ""),
        model=_get("llm_model", "deepseek-chat"),
    )


def get_vision_config_from_db(db: Session) -> LLMConfig:
    """从数据库读取视觉模型配置。"""
    from backend.core.models.setting import Setting

    def _get(key: str, default: str = "") -> str:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s and s.value else default

    return LLMConfig(
        provider=_get("vision_provider", "ollama"),
        api_url=_get("vision_api_url", "http://localhost:11434/v1"),
        api_key=_get("vision_api_key", ""),
        model=_get("vision_model", "llama3.2-vision"),
    )


def create_provider(config: LLMConfig):
    """工厂方法：根据配置创建对应的 Provider 实例。"""
    if config.provider in ("deepseek", "openai"):
        from backend.addons.llm.providers.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(config)
    elif config.provider in ("ollama", "lm_studio", "local"):
        from backend.addons.llm.providers.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(config)
    else:
        from backend.addons.llm.providers.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(config)
