"""
OpenAI 兼容 Provider — DeepSeek / Ollama / LM Studio 等
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import httpx

from backend.addons.llm.providers.base import BaseLLMProvider, LLMConfig, LLMResponse


class OpenAICompatProvider(BaseLLMProvider):
    """调用 OpenAI 兼容 API，支持流式输出和 Function Calling。"""

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model or "",
            "messages": [],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].extend(messages)
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.config.api_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            result = resp.json()
            if "error" in result:
                raise RuntimeError(f"API error: {result['error']}")
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {json.dumps(result)[:300]}")
            choice = result["choices"][0]
            msg = choice.get("message", {})

        content = (msg.get("content") or "").strip()

        tool_calls_raw = msg.get("tool_calls")
        tool_calls = None
        if tool_calls_raw:
            tool_calls = []
            for tc in tool_calls_raw:
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                })

        return LLMResponse(content=content, tool_calls=tool_calls)

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        tools: Optional[list[dict]] = None,
    ):
        """流式聊天生成器，每次 yield 文本块或 tool_calls 事件。"""
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model or "",
            "messages": [],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].extend(messages)
        if tools:
            payload["tools"] = tools

        retries = 3
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST",
                        f"{self.config.api_url.rstrip('/')}/chat/completions",
                        json=payload,
                        headers=headers,
                    ) as resp:
                        if resp.status_code >= 500 and attempt < retries - 1:
                            wait = 2 ** attempt
                            await asyncio.sleep(wait)
                            continue
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield {"type": "text", "content": content}
                                except json.JSONDecodeError:
                                    pass
                        # If we get here successfully, break retry loop
                        break
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt >= retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
