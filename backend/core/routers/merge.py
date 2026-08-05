"""
合并去重录入路由

柜号查询信息（FCLOrder）+ 上传文件信息 → 字段级合并预览 → 确认同步 FCLOrder + 写佰信填值 JSON。
文件可新上传或复用 Documents 已上传（doc_ids）。
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.core.services import get_current_user
from backend.core.models.fcl_order import FCLOrder
from backend.rpa.file_extract import extract_fields_from_file
from backend.rpa import merge_service

router = APIRouter(prefix="/api/merge", tags=["merge"])

MERGE_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "merge")
os.makedirs(MERGE_UPLOAD_DIR, exist_ok=True)
DOCS_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "docs")


def _resolve_doc_path(file_id: str) -> Optional[str]:
    """从 uploads/docs 按 file_id 前缀找到文件路径。"""
    if not os.path.isdir(DOCS_UPLOAD_DIR):
        return None
    for fname in os.listdir(DOCS_UPLOAD_DIR):
        if fname.startswith(file_id):
            return os.path.join(DOCS_UPLOAD_DIR, fname)
    return None


@router.post("/preview")
async def preview(
    container_no: str = Form(...),
    booking_no: str = Form(""),
    order_no: str = Form(""),
    files: list[UploadFile] = File([]),
    doc_ids: str = Form(""),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """上传文件(或复用Documents) + 柜号 → 合并预览。"""
    if authorization:
        user = get_current_user(authorization.replace("Bearer ", ""), db)
        if not user:
            return {"success": False, "error": "未登录"}

    ctn = container_no.strip().upper()
    warnings = []

    # 1. 收集文件路径（新上传 + 复用 Documents）
    paths = []
    for f in files:
        ext = os.path.splitext(f.filename or "file")[1] or ".bin"
        save_path = os.path.join(MERGE_UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
        with open(save_path, "wb") as fh:
            fh.write(await f.read())
        paths.append(save_path)
    for doc_id in [d.strip() for d in doc_ids.split(",") if d.strip()]:
        p = _resolve_doc_path(doc_id)
        if p:
            paths.append(p)
        else:
            warnings.append(f"文档 {doc_id} 未找到")

    # 2. 查询字段（FCLOrder，由 port_query 自动同步）
    order = db.query(FCLOrder).filter(FCLOrder.container_no == ctn).first()
    if order:
        query_fields = merge_service.query_fields_from_order(order)
    else:
        query_fields = {}
        warnings.append("FCLOrder 中未找到该柜号的查询数据，仅预览文件字段")

    # 3. 文件字段（多文件时后者不覆盖已提取的非空项）
    file_fields = {}
    for p in paths:
        flds, fwarns = await extract_fields_from_file(p, ctn, db)
        warnings.extend(fwarns)
        for k, v in flds.items():
            if k == "source":
                continue
            if k not in file_fields or not file_fields[k]:
                file_fields[k] = v
    file_fields["source"] = "file"

    # 4. 合并
    merged, provenance = merge_service.merge_fields(query_fields, file_fields)

    # 5. 组装预览表
    fields_table = []
    for key, _col, _prio, label in merge_service.FIELD_RULES:
        fields_table.append({
            "key": key,
            "label": label,
            "query_value": query_fields.get(key),
            "file_value": file_fields.get(key),
            "merged_value": merged.get(key),
            "source": provenance.get(key, ""),
        })

    return {
        "success": True,
        "container_no": ctn,
        "booking_no": booking_no,
        "order_no": order_no or (order.order_no if order else ""),
        "warning": "; ".join(warnings),
        "query_fields": query_fields,
        "file_fields": file_fields,
        "merged": merged,
        "provenance": provenance,
        "fields_table": fields_table,
    }


class ConfirmBody(BaseModel):
    container_no: str
    booking_no: str = ""
    order_no: str = ""
    merged: dict
    provenance: dict = {}


@router.post("/confirm")
async def confirm(
    body: ConfirmBody,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """确认合并：同步 FCLOrder + 写佰信填值 JSON。"""
    if authorization:
        user = get_current_user(authorization.replace("Bearer ", ""), db)
        if not user:
            return {"success": False, "error": "未登录"}

    ctn = body.container_no.strip().upper()
    order = merge_service.sync_fcl_order(db, body.merged, ctn, body.booking_no)
    output_path = merge_service.write_merge_output(
        body.order_no, body.booking_no, ctn, body.merged, body.provenance)

    return {
        "success": True,
        "order_no": body.order_no,
        "container_no": ctn,
        "fcl_order_no": order.order_no if order else "",
        "output_path": output_path,
        "message": "已同步 FCLOrder 并生成合并 JSON",
    }
