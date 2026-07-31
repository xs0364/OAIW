"""
OAIW 操作部AI工作台 — 认证路由
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.models import User
from backend.core.schemas import UserCreate, UserLogin, UserOut, TokenOut
from backend.core.services import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut)
def register(data: UserCreate, db: Session = Depends(get_db)):
    # 第一个用户自动成为 admin，之后需要 admin 权限才能注册
    user_count = db.query(User).count()
    if user_count > 0:
        # 检查是否有管理员 token
        raise HTTPException(status_code=403, detail="仅管理员可创建新用户，请使用用户管理页面")

    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        display_name=data.display_name or data.username,
        role="admin",  # 第一个用户默认为管理员
        email=data.email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user = get_current_user(authorization[7:], db)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")
    return UserOut.model_validate(user)


@router.post("/change-password")
def change_password(
    data: dict,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """修改当前用户密码。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user = get_current_user(authorization[7:], db)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")

    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")

    if not old_pw or not new_pw:
        raise HTTPException(status_code=400, detail="请填写旧密码和新密码")
    if len(new_pw) < 4:
        raise HTTPException(status_code=400, detail="新密码至少4位")

    # 验证旧密码
    from backend.core.services import verify_password
    if not verify_password(old_pw, user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码错误")

    user.hashed_password = hash_password(new_pw)
    db.commit()
    return {"success": True, "message": "密码修改成功"}


@router.get("/notify-settings")
def get_notify_settings(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """获取当前用户的通知设置。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user = get_current_user(authorization[7:], db)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")
    import json
    config = json.loads(user.notify_config or "{}")
    return {"success": True, "data": config}


@router.put("/notify-settings")
def update_notify_settings(
    data: dict,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """更新当前用户的通知设置。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user = get_current_user(authorization[7:], db)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")
    import json
    user.notify_config = json.dumps(data, ensure_ascii=False)
    db.commit()
    return {"success": True, "data": data}
