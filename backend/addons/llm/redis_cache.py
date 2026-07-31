"""
OAIW Redis 缓存模块
====================
用途:
  - LLM 响应缓存（同一问题避免重复调 DeepSeek API）
  - RPA 查询结果缓存（柜号/提单号短时重复查询）
  - 速率限制（per-user API 调用频率控制）

Redis 运行在 WSL2 Ubuntu 中（D:\\download\\wsl-ubuntu\\）
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# 全局单例
_client: Optional["redis.Redis"] = None


def _import_redis():
    """延迟导入 redis，避免未安装时启动失败。"""
    import redis
    return redis


def get_client() -> "redis.Redis":
    """获取 Redis 客户端（单例，懒初始化）。"""
    global _client
    if _client is not None:
        try:
            _client.ping()
            return _client
        except Exception:
            logger.warning("Redis 连接断开，重新连接...")
            _client = None

    redis = _import_redis()
    try:
        _client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            socket_connect_timeout=2,
            socket_timeout=3,
            decode_responses=True,
        )
        _client.ping()
        logger.info("Redis 连接成功 (localhost:6379)")
    except Exception as e:
        logger.warning(f"Redis 不可用，缓存功能将跳过: {e}")
        _client = None
    return _client


def is_available() -> bool:
    """Redis 是否可用。"""
    try:
        c = get_client()
        return c is not None
    except Exception:
        return False


# ===== LLM 响应缓存 =====

def _cache_key(message: str, history: list[dict], model: str = "") -> str:
    """生成 LLM 缓存 key（基于消息内容和模型名 hash）。"""
    raw = json.dumps({"msg": message.strip(), "hist": history[-4:], "model": model}, ensure_ascii=False)
    return f"oaiw:llm:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"


def get_llm_cache(message: str, history: list[dict], model: str = "") -> Optional[str]:
    """获取缓存的 LLM 回复。"""
    try:
        c = get_client()
        if c is None:
            return None
        key = _cache_key(message, history, model)
        return c.get(key)
    except Exception:
        return None


def set_llm_cache(message: str, history: list[dict], reply: str, model: str = "", ttl: int = 3600):
    """缓存 LLM 回复（默认 1 小时）。"""
    try:
        c = get_client()
        if c is None:
            return
        key = _cache_key(message, history, model)
        c.setex(key, ttl, reply)
    except Exception as e:
        logger.debug(f"Redis set_llm_cache 失败: {e}")


def invalidate_llm_cache(pattern: str = "oaiw:llm:*"):
    """清除 LLM 缓存（全部或匹配 pattern）。"""
    try:
        c = get_client()
        if c is None:
            return 0
        keys = c.keys(pattern)
        if keys:
            return c.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"Redis invalidate_llm_cache 失败: {e}")
        return 0


# ===== RPA 结果缓存 =====

def get_rpa_cache(key: str) -> Optional[str]:
    """获取 RPA 查询结果缓存。"""
    try:
        c = get_client()
        if c is None:
            return None
        return c.get(f"oaiw:rpa:{key}")
    except Exception:
        return None


def set_rpa_cache(key: str, value: str, ttl: int = 300):
    """缓存 RPA 查询结果（默认 5 分钟）。"""
    try:
        c = get_client()
        if c is None:
            return
        c.setex(f"oaiw:rpa:{key}", ttl, value)
    except Exception as e:
        logger.debug(f"Redis set_rpa_cache 失败: {e}")


# ===== 速率限制 =====

def check_rate_limit(
    user_id: str,
    max_requests: int = 30,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """检查用户速率限制。

    Args:
        user_id: 用户标识
        max_requests: 窗口内最大请求数
        window_seconds: 时间窗口（秒）

    Returns:
        (allowed, remaining): 是否允许 + 剩余次数
    """
    try:
        c = get_client()
        if c is None:
            return True, max_requests  # Redis 不可用时放行

        key = f"oaiw:ratelimit:{user_id}"
        now = time.time()
        window_start = now - window_seconds

        # 移除窗口外的记录
        c.zremrangebyscore(key, 0, window_start)
        # 当前窗口请求数
        count = c.zcard(key) or 0

        if count >= max_requests:
            return False, 0

        # 记录本次请求
        c.zadd(key, {str(now): now})
        c.expire(key, window_seconds + 5)
        return True, max_requests - count - 1

    except Exception:
        return True, max_requests


# ===== 向量存储（RediSearch） =====

def create_vector_index(
    index_name: str = "oaiw_embeddings",
    dims: int = 1536,
    distance_metric: str = "COSINE",
):
    """创建 RediSearch 向量索引（用于语义搜索）。

    需 Redis Stack + RediSearch 模块（已装）。
    """
    try:
        c = get_client()
        if c is None:
            return False

        # 检查索引是否已存在
        try:
            c.execute_command(f"FT.INFO", index_name)
            return True  # 已存在
        except Exception:
            pass

        c.execute_command(
            f"FT.CREATE", index_name,
            "ON", "HASH",
            "PREFIX", "1", "oaiw:emb:",
            "SCHEMA",
            "text", "TEXT", "WEIGHT", "1.0",
            "embedding", "VECTOR", "FLAT", "6",
            "TYPE", "FLOAT32",
            "DIM", str(dims),
            "DISTANCE_METRIC", distance_metric,
        )
        logger.info(f"RediSearch 向量索引 '{index_name}' 已创建 (dims={dims})")
        return True
    except Exception as e:
        logger.warning(f"创建向量索引失败: {e}")
        return False


# ===== 健康检查 =====

def health_check() -> dict:
    """Redis 健康检查。"""
    try:
        c = get_client()
        if c is None:
            return {"status": "unavailable", "error": "Redis 未连接"}

        info = c.info()
        return {
            "status": "ok",
            "redis_version": info.get("redis_version", ""),
            "used_memory_human": info.get("used_memory_human", ""),
            "total_connections_received": info.get("total_connections_received", 0),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "modules": [
                m.get("name") for m in info.get("modules", [])
                if isinstance(m, dict)
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
