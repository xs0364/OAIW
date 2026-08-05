"""
字段级合并去重服务

柜号查询信息（FCLOrder，由 port_query 自动同步）+ 上传文件信息 → 按字段优先级合并：
- 件数/体积/品名：以上传文件为准
- 箱型/封条/总重/订舱号/船名等：以柜号查询为准
- 优先来源缺失 → 另一来源补齐；两者都无 → 该字段不输出

每个字段记录 provenance（实际落值来源）供预览确认与人工复核。
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime

from sqlalchemy.orm import Session

from backend.core.models.fcl_order import FCLOrder

# 字段合并规则：(canonical_key, FCLOrder列, 优先级, 中文标签)
# FCLOrder 列为 None 表示该字段只供佰信填写（不落 FCLOrder）
FIELD_RULES = [
    ("pieces",       "pieces",         "file",  "件数"),
    ("volume",       "volume",         "file",  "体积"),
    ("cargo_name",   None,             "file",  "品名"),
    ("container_no", "container_no",   "query", "柜号"),
    ("size_type",    "container_type", "query", "箱型"),
    ("seal",         "seal_no",        "query", "封条"),
    ("gross",        "gross_weight",   "query", "总重"),
    ("booking_no",   "bl_no",          "query", "订舱号"),
    ("vessel",       "vessel_name",    "query", "船名"),
    ("voyage",       "voyage",         "query", "航次"),
    ("terminal",     "terminal",       "query", "码头"),
    ("pol",          "origin",         "query", "装货港"),
    ("dest",         "dest",           "query", "目的港"),
    ("etd",          "etd",            "query", "ETD"),
    ("eta",          "eta",            "query", "ETA"),
    ("bl_no",        "bl_no",          "query", "提单号"),
]

RULE_BY_KEY = {k: (col, prio, label) for k, col, prio, label in FIELD_RULES}

MERGE_OUTPUT_DIR = r"D:\OAIW\_merge_outputs"

_NUMERIC_ZERO = {0, 0.0}


def _has_value(v) -> bool:
    """值是否有效：None / 空串 / 0 / 0.0 视为缺失。"""
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (int, float)):
        return v not in _NUMERIC_ZERO
    return True


def query_fields_from_order(order) -> dict:
    """FCLOrder 行 → 查询字段 dict（规范 key，0/空视为缺失）。"""
    if not order:
        return {}
    def nz(v):
        if v is None:
            return ""
        if isinstance(v, (int, float)) and v in _NUMERIC_ZERO:
            return ""
        return v
    return {
        "container_no": order.container_no or "",
        "size_type": order.container_type or "",
        "seal": order.seal_no or "",
        "gross": nz(order.gross_weight),
        "pieces": nz(order.pieces),
        "volume": nz(order.volume),
        "booking_no": order.bl_no or "",
        "bl_no": order.bl_no or "",
        "vessel": order.vessel_name or order.vessel or "",
        "voyage": order.voyage or "",
        "terminal": order.terminal or "",
        "pol": order.origin or "",
        "dest": order.dest or "",
        "etd": order.etd or "",
        "eta": order.eta or "",
        "cargo_name": "",
    }


def merge_fields(query_fields: dict, file_fields: dict) -> tuple[dict, dict]:
    """按优先级合并。返回 (merged, provenance)：
    provenance[key] = "query" | "file" | "query_fallback" | "file_fallback"
    """
    merged, provenance = {}, {}
    for key, _col, priority, _label in FIELD_RULES:
        primary = query_fields if priority == "query" else file_fields
        secondary = file_fields if priority == "query" else query_fields
        pv = primary.get(key)
        sv = secondary.get(key)
        if _has_value(pv):
            merged[key] = pv
            provenance[key] = priority  # "query" 或 "file"
        elif _has_value(sv):
            merged[key] = sv
            provenance[key] = "file_fallback" if priority == "query" else "query_fallback"
        # 两者都无 → 不输出
    return merged, provenance


def sync_fcl_order(db: Session, merged: dict, container_no: str,
                   booking_no: str = "") -> FCLOrder | None:
    """合并结果同步 FCLOrder：按柜号查重，有则覆盖非空字段，无则创建。不推进状态。"""
    ctn = (container_no or "").strip().upper()
    if not ctn:
        return None

    order = db.query(FCLOrder).filter(FCLOrder.container_no == ctn).first()
    if order:
        action = "佰信合并录入更新"
    else:
        order_no = (booking_no or "").strip() or f"FCL-{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"
        order = FCLOrder(order_no=order_no, container_no=ctn)
        db.add(order)
        action = "佰信合并录入创建"

    for key, col, _prio, _label in FIELD_RULES:
        if col is None or key not in merged:
            continue
        setattr(order, col, merged[key])

    from backend.core.routers.fcl import _add_log
    _add_log(order, action, f"柜号 {ctn} 文件+查询合并去重录入")
    db.commit()
    db.refresh(order)
    return order


def write_merge_output(order_no: str, booking_no: str, container_no: str,
                       merged: dict, provenance: dict) -> str:
    """写合并结果 JSON 到 _merge_outputs，供佰信填值脚本与人工复核。返回路径。"""
    os.makedirs(MERGE_OUTPUT_DIR, exist_ok=True)
    tag = (order_no or booking_no or "NO").strip()
    fname = f"{tag}_{container_no}.json"
    path = os.path.join(MERGE_OUTPUT_DIR, fname)

    fields = []
    for key, _col, _prio, label in FIELD_RULES:
        if key in merged:
            fields.append({
                "key": key,
                "label": label,
                "value": merged[key],
                "source": provenance.get(key, ""),
            })

    data = {
        "order_no": order_no,
        "booking_no": booking_no,
        "container_no": container_no,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "merged": merged,
        "provenance": provenance,
        "fields": fields,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
