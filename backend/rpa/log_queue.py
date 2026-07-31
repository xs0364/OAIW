"""
RPA 实时日志队列 — SSE 流式推送。
放在独立模块中避免循环引用。
"""
from __future__ import annotations

import queue as _queue
import sys as _sys

_rpa_log_queue: _queue.Queue | None = None


def set_log_queue(q: _queue.Queue | None):
    """设置日志队列（由 SSE 端点调用）。"""
    global _rpa_log_queue
    _rpa_log_queue = q


def rpa_log(msg: str):
    """打印日志到终端并推送到 SSE 流。"""
    _sys.__stdout__.write(f"  {msg}\n")
    _sys.__stdout__.flush()
    q = _rpa_log_queue
    if q is not None:
        q.put_nowait(msg)
