"""空运订单管理路由"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.models.air_freight import AirFreightOrder

router = APIRouter(prefix="/api/air-freight", tags=["air-freight"])

# 11步流程定义（补料→报关 顺序已修正）
STEPS = [
    {"key": "booking", "label": "订舱", "order": 0},
    {"key": "waybill", "label": "面单", "order": 1},
    {"key": "so_release", "label": "放SO", "order": 2},
    {"key": "docs_confirm", "label": "对单", "order": 3},
    {"key": "filing", "label": "补料", "order": 4},
    {"key": "customs", "label": "报关", "order": 5},
    {"key": "insurance", "label": "保险", "order": 6},
    {"key": "bl", "label": "提单", "order": 7},
    {"key": "tracking", "label": "跟踪", "order": 8},
    {"key": "ap", "label": "应付", "order": 9},
    {"key": "closed", "label": "结单", "order": 10},
]

STEP_KEYS = [s["key"] for s in STEPS]


def _calc_progress(status: str) -> int:
    idx = STEP_KEYS.index(status) if status in STEP_KEYS else -1
    if idx < 0:
        return 0
    return int((idx + 1) / len(STEP_KEYS) * 100)


def _add_log(order: AirFreightOrder, action: str, detail: str = ""):
    logs = json.loads(order.logs or "[]")
    logs.append({
        "time": datetime.now().isoformat(),
        "action": action,
        "detail": detail,
    })
    order.logs = json.dumps(logs, ensure_ascii=False)


@router.get("/orders")
def list_orders(search: str = "", status: str = "", db: Session = Depends(get_db)):
    q = db.query(AirFreightOrder)
    if search:
        q = q.filter(AirFreightOrder.order_no.like(f"%{search}%"))
    if status:
        q = q.filter(AirFreightOrder.status == status)
    orders = q.order_by(AirFreightOrder.id.desc()).limit(100).all()
    return {
        "success": True,
        "orders": [
            {
                "id": o.id,
                "orderNo": o.order_no,
                "origin": o.origin,
                "dest": o.dest,
                "pieces": o.pieces,
                "weight": o.weight,
                "volume": o.volume,
                "cargoDesc": o.cargo_desc,
                "carrier": o.carrier,
                "flightNo": o.flight_no,
                "etd": o.etd,
                "sales": o.sales,
                "status": o.status,
                "progress": o.progress,
                "logs": json.loads(o.logs or "[]"),
                "createdAt": o.created_at.isoformat() if o.created_at else "",
                "updatedAt": o.updated_at.isoformat() if o.updated_at else "",
            }
            for o in orders
        ],
    }


@router.post("/orders")
def create_order(data: dict, db: Session = Depends(get_db)):
    import random
    order_no = data.get("orderNo") or f"AE-{datetime.now().strftime('%y%m%d')}-{random.randint(100,999)}"
    order = AirFreightOrder(
        order_no=order_no,
        origin=data.get("origin", ""),
        dest=data.get("dest", ""),
        pieces=int(data.get("pieces", 0)),
        weight=float(data.get("weight", 0)),
        volume=float(data.get("volume", 0)),
        cargo_desc=data.get("cargoDesc", ""),
        carrier=data.get("carrier", ""),
        flight_no=data.get("flightNo", ""),
        etd=data.get("etd", ""),
        sales=data.get("sales", ""),
        status="booking",
        progress=_calc_progress("booking"),
    )
    _add_log(order, "创建订单", f"单号 {order_no}")
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"success": True, "order": order}


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(AirFreightOrder).filter(AirFreightOrder.id == order_id).first()
    if not order:
        return {"success": False, "error": "订单不存在"}
    return {
        "success": True,
        "order": {
            "id": order.id,
            "orderNo": order.order_no,
            "origin": order.origin,
            "dest": order.dest,
            "pieces": order.pieces,
            "weight": order.weight,
            "volume": order.volume,
            "cargoDesc": order.cargo_desc,
            "carrier": order.carrier,
            "flightNo": order.flight_no,
            "etd": order.etd,
            "sales": order.sales,
            "status": order.status,
            "progress": order.progress,
            "logs": json.loads(order.logs or "[]"),
        },
    }


@router.post("/orders/{order_id}/advance")
def advance_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(AirFreightOrder).filter(AirFreightOrder.id == order_id).first()
    if not order:
        return {"success": False, "error": "订单不存在"}
    cur = order.status
    if cur not in STEP_KEYS:
        return {"success": False, "error": f"未知状态: {cur}"}
    idx = STEP_KEYS.index(cur)
    if idx >= len(STEP_KEYS) - 1:
        return {"success": False, "error": "已到最后状态"}
    next_status = STEP_KEYS[idx + 1]
    next_label = STEPS[idx + 1]["label"]

    order.status = next_status
    order.progress = _calc_progress(next_status)
    _add_log(order, f"推进: {next_label}")
    db.commit()
    return {"success": True, "order": order, "nextStatus": next_status, "nextLabel": next_label}


@router.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(AirFreightOrder).filter(AirFreightOrder.id == order_id).first()
    if not order:
        return {"success": False, "error": "订单不存在"}
    db.delete(order)
    db.commit()
    return {"success": True}
