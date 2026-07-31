"""
MiniMax M3 工具调用 — RPA 集装箱查询 / 码头状态查询
"""
from __future__ import annotations

# ===== 工具定义（OpenAI Function Calling 格式） =====

RPA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_container",
            "description": "查询集装箱在港口的在场状态、海关放行、进港时间、是否可提柜等信息。需要提供柜号，港口名称可选。",
            "parameters": {
                "type": "object",
                "properties": {
                    "container_no": {
                        "type": "string",
                        "description": "集装箱号/柜号，例如 TEMU1234567"
                    },
                    "port_name": {
                        "type": "string",
                        "description": "港口名称，可选。不提供则自动判断。可选值：盐田、蛇口、上海、宁波、青岛",
                        "enum": ["盐田", "蛇口", "上海", "宁波", "青岛"]
                    }
                },
                "required": ["container_no"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_port_status",
            "description": "查询码头的最新通知公告、运营状态、台风/拥堵/系统升级等异常公告。",
            "parameters": {
                "type": "object",
                "properties": {
                    "port_name": {
                        "type": "string",
                        "description": "港口名称。可选值：盐田、蛇口、上海、宁波、青岛",
                        "enum": ["盐田", "蛇口", "上海", "宁波", "青岛"]
                    }
                },
                "required": ["port_name"]
            }
        }
    },
]


async def execute_tool_call(tool_name: str, arguments: dict | str) -> str:
    """执行工具调用（带 Redis 缓存），返回人类可读的结果字符串。"""
    import json
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return f"❌ 工具参数解析失败：{arguments}"

    from backend.rpa import run_browser_task
    from backend.addons.llm.redis_cache import get_rpa_cache, set_rpa_cache
    from backend.config import settings

    if tool_name == "query_container":
        container_no = (arguments.get("container_no") or "").strip().upper()
        port_name = (arguments.get("port_name") or "").strip()
        if not container_no:
            return "❌ 错误：缺少柜号（container_no）"

        # Redis 缓存：同一柜号 5 分钟内不重复查
        cache_key = f"container:{container_no}"
        if settings.REDIS_ENABLED:
            cached = get_rpa_cache(cache_key)
            if cached:
                return f"📦 {container_no} 查询结果（缓存）:\n{cached}"

        params = {"container_no": container_no}
        if port_name:
            params["port_name"] = port_name
            cache_key += f":{port_name}"
        result = await run_browser_task("port_query", params)
        if result.get("success"):
            data = result.get("data", "查询完成，但无返回数据")
            # 写缓存
            if settings.REDIS_ENABLED:
                set_rpa_cache(cache_key, data, ttl=settings.REDIS_RPA_CACHE_TTL)
            return f"📦 {container_no} 查询结果:\n{data}"
        else:
            return f"❌ 查询失败：{result.get('error', '未知错误')}"

    elif tool_name == "query_port_status":
        port_name = (arguments.get("port_name") or "").strip()
        if not port_name:
            return "❌ 错误：请指定港口名称（port_name）"

        # Redis 缓存：同一港口公告 5 分钟缓存
        cache_key = f"port_status:{port_name}"
        if settings.REDIS_ENABLED:
            cached = get_rpa_cache(cache_key)
            if cached:
                return f"⏱️ {port_name} 港口状态（缓存）:\n{cached}"

        params = {"port_name": port_name}
        result = await run_browser_task("port_status", params)
        if result.get("success"):
            data = result.get("data", "查询完成，但无返回数据")
            if settings.REDIS_ENABLED:
                set_rpa_cache(cache_key, data, ttl=settings.REDIS_RPA_CACHE_TTL)
            return f"⏱️ {port_name} 港口状态:\n{data}"
        else:
            return f"❌ 查询失败：{result.get('error', '未知错误')}"

    else:
        return f"❌ 未知工具: {tool_name}"
