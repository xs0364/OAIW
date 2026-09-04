"""
OAIW Tool Schemas — 操作部 AI Agent 工具定义

OpenAI 兼容 Function Calling 格式，供支持 tools 参数的 Provider 使用。

schema 单一来源在 backend.addons.llm.tools（RPA_TOOLS + OAIW_TOOLS），
本文件作为 workflow 路径的兼容导出，避免双份定义漂移。
"""
from __future__ import annotations

from backend.addons.llm.tools import RPA_TOOLS, OAIW_TOOLS

# 操作部 AI Agent 可用工具
TOOLS = RPA_TOOLS + OAIW_TOOLS
