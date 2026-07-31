"""
短信验证码桥接模块 — 用于 RPA 流程中等待用户输入短信验证码。

流程：
1. RPA 线程调用 request_sms(session_id) → 阻塞等待用户输入
2. 前端通过 SSE 收到 __SMS_REQUIRED__ 事件 → 弹出输入框
3. 用户输入验证码 → POST /api/rpa/submit_sms → submit_sms(session_id, code)
4. RPA 线程拿到验证码 → 继续执行
"""

from __future__ import annotations

import queue as _queue
import threading
from typing import Optional

# 全局存储：session_id → Queue（每个等待的验证码请求一个队列）
_sms_queues: dict[str, _queue.Queue] = {}
_lock = threading.Lock()


def create_session() -> str:
    """创建一个新的短信验证码等待会话，返回 session_id。"""
    import uuid
    session_id = uuid.uuid4().hex[:12]
    with _lock:
        _sms_queues[session_id] = _queue.Queue()
    return session_id


def wait_for_sms(session_id: str, timeout: int = 120) -> Optional[str]:
    """
    RPA 线程调用：等待用户输入短信验证码。
    阻塞直到用户提交或超时。

    Returns:
        str: 用户输入的短信验证码
        None: 超时
    """
    q = _sms_queues.get(session_id)
    if not q:
        return None
    try:
        code = q.get(timeout=timeout)
        return code
    except _queue.Empty:
        return None


def submit_sms(session_id: str, code: str) -> bool:
    """
    API 端点调用：用户提交短信验证码。
    将验证码推送给等待中的 RPA 线程。

    Returns:
        True 会话存在且验证码已提交
        False 会话不存在或已过期
    """
    q = _sms_queues.get(session_id)
    if not q:
        return False
    q.put(code)
    return True


def cleanup(session_id: str):
    """清理会话（RPA 线程结束后调用）。"""
    with _lock:
        _sms_queues.pop(session_id, None)
