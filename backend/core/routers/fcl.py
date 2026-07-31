"""整柜 FCL 订单路由"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.models.fcl_order import FCLOrder

router = APIRouter(prefix="/api/fcl", tags=["fcl"])

# FCL 14步流程（与前端一致）
STEPS = [
    {"key": "received", "label": "接单审单", "order": 0},
    {"key": "so_release", "label": "放舱", "order": 1},
    {"key": "trucking", "label": "拖车报关", "order": 2},
    {"key": "bl_draft", "label": "核对提单", "order": 3},
    {"key": "si_vgm", "label": "补料/VGM", "order": 4},
    {"key": "ams_isf", "label": "AMS/ISF", "order": 5},
    {"key": "sailing", "label": "开船", "order": 6},
    {"key": "reconciled", "label": "对账", "order": 7},
    {"key": "payment", "label": "收款", "order": 8},
    {"key": "release", "label": "放单", "order": 9},
    {"key": "arrived", "label": "确认到港", "order": 10},
    {"key": "delivery", "label": "提柜", "order": 11},
    {"key": "empty_return", "label": "还空", "order": 12},
    {"key": "closed", "label": "结单", "order": 13},
]

STEP_KEYS = [s["key"] for s in STEPS]


def _calc_progress(status: str) -> int:
    idx = STEP_KEYS.index(status) if status in STEP_KEYS else -1
    if idx < 0:
        return 0
    return int((idx + 1) / len(STEP_KEYS) * 100)


def _add_log(order: FCLOrder, action: str, detail: str = ""):
    logs = json.loads(order.logs or "[]")
    logs.append({
        "time": datetime.now().isoformat(),
        "action": action,
        "detail": detail,
    })
    order.logs = json.dumps(logs, ensure_ascii=False)


def _order_to_dict(o: FCLOrder) -> dict:
    return {
        "id": o.id,
        "orderNo": o.order_no,
        "origin": o.origin,
        "dest": o.dest,
        "route": o.route,
        "containerType": o.container_type,
        "containerNo": o.container_no,
        "grossWeight": o.gross_weight,
        "pieces": o.pieces,
        "volume": o.volume,
        "carrier": o.carrier,
        "vessel": o.vessel,
        "vesselName": o.vessel_name,
        "voyage": o.voyage,
        "blNo": o.bl_no,
        "sealNo": o.seal_no,
        "terminal": o.terminal,
        "etd": o.etd,
        "eta": o.eta,
        "direction": o.direction,
        "status": o.status,
        "progress": o.progress,
        "logs": json.loads(o.logs or "[]"),
        "createdAt": o.created_at.isoformat() if o.created_at else "",
        "updatedAt": o.updated_at.isoformat() if o.updated_at else "",
    }


@router.get("/orders")
def list_orders(search: str = "", status: str = "", container_type: str = "",
                db: Session = Depends(get_db)):
    q = db.query(FCLOrder)
    if search:
        like = f"%{search}%"
        q = q.filter(
            FCLOrder.order_no.like(like) |
            FCLOrder.container_no.like(like) |
            FCLOrder.bl_no.like(like) |
            FCLOrder.vessel_name.like(like)
        )
    if status:
        q = q.filter(FCLOrder.status == status)
    if container_type:
        q = q.filter(FCLOrder.container_type == container_type)
    orders = q.order_by(FCLOrder.id.desc()).limit(100).all()
    return {"success": True, "orders": [_order_to_dict(o) for o in orders]}


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(FCLOrder).filter(FCLOrder.id == order_id).first()
    if not order:
        return {"success": False, "error": "订单不存在"}
    return {"success": True, "order": _order_to_dict(order)}


@router.post("/orders")
def create_order(data: dict, db: Session = Depends(get_db)):
    import random
    order_no = data.get("orderNo") or f"FCL-{datetime.now().strftime('%y%m%d')}-{random.randint(100,999)}"
    order = FCLOrder(
        order_no=order_no,
        origin=data.get("origin", ""),
        dest=data.get("dest", ""),
        route=data.get("route", ""),
        container_type=data.get("containerType", ""),
        container_no=data.get("containerNo", ""),
        gross_weight=float(data.get("grossWeight", 0)),
        pieces=int(data.get("pieces", 0)),
        volume=float(data.get("volume", 0)),
        carrier=data.get("carrier", ""),
        vessel=data.get("vessel", ""),
        vessel_name=data.get("vesselName", ""),
        voyage=data.get("voyage", ""),
        bl_no=data.get("blNo", ""),
        seal_no=data.get("sealNo", ""),
        terminal=data.get("terminal", ""),
        etd=data.get("etd", ""),
        eta=data.get("eta", ""),
        direction=data.get("direction", ""),
        status="received",
        progress=_calc_progress("received"),
    )
    _add_log(order, "创建订单", f"单号 {order_no}（来自RPA同步）")
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"success": True, "order": _order_to_dict(order)}


@router.post("/orders/{order_id}/advance")
def advance_order(order_id: int, data: dict = {}, db: Session = Depends(get_db)):
    """推进或更新到指定状态"""
    order = db.query(FCLOrder).filter(FCLOrder.id == order_id).first()
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

    # 同时更新可选字段
    for field in ("container_no", "vessel", "vessel_name", "voyage", "bl_no", "etd", "eta", "gross_weight", "pieces", "volume", "carrier"):
        if field in data:
            setattr(order, field, data[field])

    db.commit()
    return {"success": True, "order": _order_to_dict(order)}
