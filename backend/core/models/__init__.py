"""
OAIW 操作部AI工作台 — 数据模型
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.database import Base
from backend.core.models.setting import Setting  # noqa — 注册 Setting 模型
from backend.core.models.air_freight import AirFreightOrder  # noqa — 注册空运订单模型
from backend.core.models.fcl_order import FCLOrder, SeaFreightOrder  # noqa — 注册海运订单模型


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), default="")
    role = Column(String(20), default="operator")  # admin | supervisor | operator
    email = Column(String(100), default="")
    avatar = Column(String(255), default="")
    is_active = Column(Integer, default=1)
    notify_config = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
