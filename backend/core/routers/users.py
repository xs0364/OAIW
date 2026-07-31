"""
OAIW 操作部AI工作台 — 用户管理路由（仅管理员）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.models import User
from backend.core.schemas import UserOut as UserSchema
from backend.core.services import hash_password, require_admin, get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取所有用户列表（管理员）。"""
    users = db.query(User).order_by(User.id).all()
    return {"success": True, "data": [UserSchema.model_validate(u).model_dump() for u in users]}


@router.post("")
def create_user(
    data: dict,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员创建新用户。"""
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "operator")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if role not in ("admin", "operator"):
        raise HTTPException(status_code=400, detail="角色无效")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=username,
        hashed_password=hash_password(password),
        display_name=data.get("display_name", username),
        role=role,
        email=data.get("email", ""),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"success": True, "data": UserSchema.model_validate(user).model_dump()}


@router.put("/{user_id}")
def update_user(
    user_id: int,
    data: dict,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员更新用户信息。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if "role" in data:
        if data["role"] not in ("admin", "operator"):
            raise HTTPException(status_code=400, detail="角色无效")
        user.role = data["role"]
    if "display_name" in data:
        user.display_name = data["display_name"]
    if "email" in data:
        user.email = data["email"]
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data["password"])
    if "is_active" in data:
        user.is_active = 1 if data["is_active"] else 0

    db.commit()
    db.refresh(user)
    return {"success": True, "data": UserSchema.model_validate(user).model_dump()}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员删除用户。"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"success": True, "message": f"已删除用户 {user.username}"}
