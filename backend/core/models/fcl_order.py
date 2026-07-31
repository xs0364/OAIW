"""
整柜 FCL 订单模型
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, Float

from backend.database import Base


class FCLOrder(Base):
    __tablename__ = "fcl_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(50), unique=True, nullable=False, index=True, comment="业务单号/提单号")
    origin = Column(String(50), default="", comment="起运港")
    dest = Column(String(50), default="", comment="目的港")
    route = Column(String(100), default="", comment="航线显示")
    container_type = Column(String(20), default="", comment="箱型 20GP/40HQ/45GP")
    container_no = Column(String(20), default="", index=True, comment="柜号")
    gross_weight = Column(Float, default=0, comment="毛重(KGS)")
    pieces = Column(Integer, default=0, comment="件数")
    volume = Column(Float, default=0, comment="体积(CBM)")
    carrier = Column(String(50), default="", comment="船司")
    vessel = Column(String(100), default="", comment="船名航次")
    vessel_name = Column(String(50), default="", comment="英文船名")
    voyage = Column(String(30), default="", comment="航次")
    bl_no = Column(String(50), default="", comment="提单号")
    seal_no = Column(String(50), default="", comment="铅封号")
    terminal = Column(String(50), default="", comment="码头")
    etd = Column(String(20), default="", comment="预计开船/离港时间")
    eta = Column(String(20), default="", comment="预计到港时间")
    direction = Column(String(10), default="", comment="航向 进口/出口")

    status = Column(String(30), default="received", comment="当前状态key")
    progress = Column(Integer, default=0, comment="进度百分比")
    logs = Column(Text, default="[]", comment="操作日志JSON")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SeaFreightOrder(Base):
    __tablename__ = "sea_freight_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(50), unique=True, nullable=False, index=True, comment="业务单号/HB/L")
    origin = Column(String(50), default="", comment="起运港")
    dest = Column(String(50), default="", comment="目的港")
    route = Column(String(100), default="", comment="航线显示")
    pieces = Column(Integer, default=0, comment="件数")
    gross_weight = Column(Float, default=0, comment="毛重(KGS)")
    volume = Column(Float, default=0, comment="体积(CBM)")
    carrier = Column(String(50), default="", comment="船司")
    master_bl = Column(String(50), default="", comment="主单号MBL")
    house_bl = Column(String(50), default="", comment="分单号HBL")
    etd = Column(String(20), default="", comment="预计开船时间")
    eta = Column(String(20), default="", comment="预计到港时间")
    cutoff_time = Column(String(20), default="", comment="截仓时间")

    status = Column(String(30), default="booking", comment="当前状态key")
    progress = Column(Integer, default=0, comment="进度百分比")
    logs = Column(Text, default="[]", comment="操作日志JSON")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
