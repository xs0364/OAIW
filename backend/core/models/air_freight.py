"""空运订单模型"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, Float

from backend.database import Base


class AirFreightOrder(Base):
    __tablename__ = "air_freight_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(50), unique=True, nullable=False, index=True, comment="业务单号")
    origin = Column(String(50), default="", comment="起运港")
    dest = Column(String(50), default="", comment="目的港")
    pieces = Column(Integer, default=0, comment="件数")
    weight = Column(Float, default=0, comment="毛重(kg)")
    volume = Column(Float, default=0, comment="体积(cbm)")
    cargo_desc = Column(String(200), default="", comment="品名")
    carrier = Column(String(50), default="", comment="航司")
    flight_no = Column(String(50), default="", comment="航班号")
    etd = Column(String(20), default="", comment="预计出运日")
    sales = Column(String(50), default="", comment="业务员")
    status = Column(String(30), default="booking", comment="当前状态key")
    progress = Column(Integer, default=0, comment="进度百分比")
    logs = Column(Text, default="[]", comment="操作日志JSON")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
