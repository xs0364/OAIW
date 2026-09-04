"""
集装箱查询结果标准化记录模型

每次「箱查询标准化」成功落库一条，保留全部历史（同柜号不覆盖）。fields_json 存
18 个标准字段 JSON（LLM 结果，手改后为更新值）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.database import Base


class ContainerStandardize(Base):
    __tablename__ = "container_standardize"

    id = Column(Integer, primary_key=True, index=True)
    port_name = Column(String(50), default="")
    container_no = Column(String(50), default="", index=True)
    raw_text = Column(Text, default="")
    fields_json = Column(Text, default="{}")
    summary = Column(String(255), default="")
    created_by = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
