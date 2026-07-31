"""
OAIW 系统设置模型
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text

from backend.database import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, default="")
    description = Column(String(255), default="")
