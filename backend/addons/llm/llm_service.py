"""
OAIW LLM 服务层 — 高层封装，供路由和 Agent 调用
"""
from __future__ import annotations

import json
import re
from typing import Optional

from sqlalchemy.orm import Session

from backend.addons.llm.providers import get_provider_config_from_db, create_provider


async def simple_chat(
    messages: list[dict],
    system_prompt: Optional[str] = None,
    db: Optional[Session] = None,
) -> str:
    """简单对话，返回文本回复。"""
    if db is not None:
        config = get_provider_config_from_db(db)
    else:
        from backend.addons.llm.providers.base import LLMConfig
        config = LLMConfig()

    provider = create_provider(config)
    resp = await provider.chat(
        messages=messages,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=4096,
    )
    return resp.content.strip() if resp and resp.content else ""


async def extract_json(
    user_message: str,
    schema_description: str,
    db: Optional[Session] = None,
) -> dict:
    """调用 LLM 提取结构化 JSON 数据。"""
    system_prompt = f"""从以下内容提取结构化数据。
返回 ONLY 有效的 JSON，不要任何解释。
Schema: {schema_description}"""

    from backend.addons.llm.providers.base import LLMConfig

    if db is not None:
        config = get_provider_config_from_db(db)
    else:
        config = LLMConfig()

    provider = create_provider(config)
    resp = await provider.chat(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=2048,
    )
    content = resp.content.strip() if resp and resp.content else ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if match:
            return json.loads(match.group(1))
        return {"raw": content, "error": "Failed to parse JSON"}
