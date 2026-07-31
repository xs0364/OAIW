"""
OAIW 操作部AI工作台 — 工具函数
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from backend.core.services import get_current_user


def require_user(authorization: Optional[str] = Header(None), db=None) -> "User":
    """依赖注入：要求用户已登录。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user = get_current_user(authorization[7:], db)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")
    return user


def require_admin(user: "User") -> "User":
    """依赖注入：要求管理员权限。"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
