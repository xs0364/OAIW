"""海运散货 LCL 订单路由"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.models.fcl_order import SeaFreightOrder

router = APIRouter(prefix="/api/sea-freight", tags=["sea-freight"])

# LCL 13步流程（与前端一致）
STEPS = [
    {"key": "booking", "label": "订舱", "order": 0},
    {"key": "pickup", "label": "安排提货", "order": 1},
    {"key": "warehouse", "label": "进仓", "order": 2},
    {"key": "cargo_check", "label": "核对进仓数据", "order": 3},
    {"key": "bl_check", "label": "核对提单", "order": 4},
    {"key": "filing", "label": "补料", "order": 5},
    {"key": "sailing", "label": "开船", "order": 6},
    {"key": "bl_invoice", "label": "发提单账单", "order": 7},
    {"key": "payment", "label": "收款", "order": 8},
    {"key": "release", "label": "放单", "order": 9},
    {"key": "arrived", "label": "到港", "order": 10},
    {"key": "delivery", "label": "提货", "order": 11},
    {"key": "closed", "label": "结单", "order": 12},
]

STEP_KEYS = [s["key"] for s in STEPS]


def _calc_progress(status: str) -> int:
    idx = STEP_KEYS.index(status) if status in STEP_KEYS else -1
    if idx < 0:
        return 0
    return int((idx + 1) / len(STEP_KEYS) * 100)


def _add_log(order: SeaFreightOrder, action: str, detail: str = ""):
    logs = json.loads(order.logs or "[]")
    logs.append({
        "time": datetime.now().isoformat(),
        "action": action,
        "detail": detail,
    })
    order.logs = json.dumps(logs, ensure_ascii=False)


def _order_to_dict(o: SeaFreightOrder) -> dict:
    return {
        "id": o.id,
        "orderNo": o.order_no,
        "origin": o.origin,
        "dest": o.dest,
        "route": o.route,
        "pieces": o.pieces,
        "grossWeight": o.gross_weight,
        "volume": o.volume,
        "carrier": o.carrier,
        "masterBl": o.master_bl,
        "houseBl": o.house_bl,
        "etd": o.etd,
        "eta": o.eta,
        "cutoffTime": o.cutoff_time,
        "status": o.status,
        "progress": o.progress,
        "logs": json.loads(o.logs or "[]"),
        "createdAt": o.created_at.isoformat() if o.created_at else "",
        "updatedAt": o.updated_at.isoformat() if o.updated_at else "",
    }


@router.get("/orders")
def list_orders(search: str = "", status: str = "", db: Session = Depends(get_db)):
    q = db.query(SeaFreightOrder)
    if search:
        like = f"%{search}%"
        q = q.filter(
            SeaFreightOrder.order_no.like(like) |
            SeaFreightOrder.master_bl.like(like) |
            SeaFreightOrder.house_bl.like(like)
        )
    if status:
        q = q.filter(SeaFreightOrder.status == status)
    orders = q.order_by(SeaFreightOrder.id.desc()).limit(100).all()
    return {"success": True, "orders": [_order_to_dict(o) for o in orders]}


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(SeaFreightOrder).filter(SeaFreightOrder.id == order_id).first()
    if not order:
        return {"success": False, "error": "订单不存在"}
    return {"success": True, "order": _order_to_dict(order)}


@router.post("/orders")
def create_order(data: dict, db: Session = Depends(get_db)):
    import random
    order_no = data.get("orderNo") or f"LCL-{datetime.now().strftime('%y%m%d')}-{random.randint(100,999)}"
    order = SeaFreightOrder(
        order_no=order_no,
        origin=data.get("origin", ""),
        dest=data.get("dest", ""),
        route=data.get("route", ""),
        pieces=int(data.get("pieces", 0)),
        gross_weight=float(data.get("grossWeight", 0)),
        volume=float(data.get("volume", 0)),
        carrier=data.get("carrier", ""),
        master_bl=data.get("masterBl", ""),
        house_bl=data.get("houseBl", ""),
        etd=data.get("etd", ""),
        eta=data.get("eta", ""),
        cutoff_time=data.get("cutoffTime", ""),
        status="booking",
        progress=_calc_progress("booking"),
    )
    _add_log(order, "创建订单", f"单号 {order_no}（来自RPA同步）")
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"success": True, "order": _order_to_dict(order)}


@router.post("/orders/{order_id}/advance")
def advance_order(order_id: int, data: dict = {}, db: Session = Depends(get_db)):
    order = db.query(SeaFreightOrder).filter(SeaFreightOrder.id == order_id).first()
    if not order:
        return {"success": False, "error": "订单不存在"}

    target = data.get("status", "")
    if not target:
        return {"success": False, "error": "请指定目标状态"}
    if target not in STEP_KEYS:
        return {"success": False, "error": f"未知状态: {target}"}

    order.status = target
    order.progress = _calc_progress(target)
    label = next((s["label"] for s in STEPS if s["key"] == target), target)
    note = data.get("note", "")
    _add_log(order, f"推进: {label}", note)

    for field in ("pieces", "gross_weight", "volume", "carrier", "master_bl", "house_bl", "etd", "eta", "cutoff_time"):
        if field in data:
            setattr(order, field, data[field])

    db.commit()
    return {"success": True, "order": _order_to_dict(order)}
