"""
OAIW 操作部AI工作台 — Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field

from backend.config import settings


# ========== User Schemas ==========
class UserLogin(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "operator"
    email: str = ""


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    email: str
    is_active: int
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None

    @computed_field
    @property
    def online(self) -> bool:
        """在线判定:now - last_active ≤ ONLINE_WINDOW_SECONDS;last_active 为空视为离线。"""
        la = self.last_active
        return bool(la) and (datetime.now() - la).total_seconds() <= settings.ONLINE_WINDOW_SECONDS

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
