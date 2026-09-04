# -*- coding: utf-8 -*-
"""用户各自的 SMTP 邮箱配置（独立表，各账号管理各自的）。

每个账号在侧边栏【邮箱设置】中配置自己的 SMTP，发送邮件时用当前用户配置；
未配置邮箱的账号在 AI 助手等发邮件场景提示"未配置"，不自动回退全局配置。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from backend.database import Base


class UserSmtpConfig(Base):
    __tablename__ = "user_smtp_config"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    smtp_host = Column(String(255), default="")
    smtp_port = Column(Integer, default=465)
    smtp_user = Column(String(255), default="")
    smtp_password = Column(String(255), default="")
    smtp_from_email = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)
