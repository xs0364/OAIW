"""
OAIW RPA 港口驱动模块 — 统一接口

每个港口一个驱动模块，实现 PortDriver 协议：

    class XxxPort:
        name = "港口名"

        @staticmethod
        def query_container(page, params: dict) -> dict:
            \"""查询集装箱状态，返回 {"success": bool, "data": str, "error": str}\"""
            ...

驱动通过 @register("港口名") 装饰器自动注册到全局注册表。
"""

_registry: dict[str, type] = {}


def register(name: str):
    """装饰器：注册港口驱动。"""
    def decorator(cls):
        cls.name = name
        _registry[name] = cls
        return cls
    return decorator


def get_driver(name: str):
    """按名称获取港口驱动类。"""
    # 支持模糊匹配
    for key, cls in _registry.items():
        if name == key or name in key or key in name:
            return cls
    return None


def list_ports() -> list[str]:
    """列出所有已注册的港口名称。"""
    return list(_registry.keys())


# ===== 导入所有港口驱动以触发 @register 装饰器 =====
from backend.rpa.ports import yantian  # noqa
from backend.rpa.ports import shekou  # noqa
from backend.rpa.ports import npedi  # noqa
from backend.rpa.ports import qingdao  # noqa
