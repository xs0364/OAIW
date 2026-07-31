"""
OAIW 文档上传与解析路由
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import settings
from backend.core.services import get_current_user
from backend.parser import extract_text

router = APIRouter(prefix="/api/docs", tags=["docs"])

UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "docs")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """上传文档并自动提取内容。"""
    if authorization:
        user = get_current_user(authorization.replace("Bearer ", ""), db)
        if not user:
            return {"success": False, "error": "未登录"}

    # 保存文件
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    file_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    content_bytes = await file.read()
    with open(save_path, "wb") as f:
        f.write(content_bytes)

    # 提取文本
    text = extract_text(save_path)

    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content_bytes),
        "text_preview": text[:2000] if text else "(空)",
        "text_length": len(text),
        "path": f"/uploads/docs/{file_id}{ext}",
    }


@router.post("/merge-invoices")
async def merge_invoices(
    doc_ids: list[str] = Form(...),
    authorization: Optional[str] = Header(None),
):
    """合并多份箱单发票。"""
    texts = []
    for doc_id in doc_ids:
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(doc_id):
                path = os.path.join(UPLOAD_DIR, fname)
                text = extract_text(path)
                texts.append(f"=== {fname} ===\n{text}")
                break

    if not texts:
        return {"success": False, "error": "未找到文档"}

    merged = "\n\n".join(texts)
    return {"success": True, "merged_text": merged, "file_count": len(texts)}


@router.get("/files")
async def list_docs():
    """列出所有已上传文档。"""
    if not os.path.isdir(UPLOAD_DIR):
        return {"success": True, "files": []}
    files = []
    for fname in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, fname)
        if os.path.isfile(path):
            ext = os.path.splitext(fname)[1]
            file_id = os.path.splitext(fname)[0]
            files.append({
                "file_id": file_id,
                "filename": fname,
                "size": os.path.getsize(path),
                "ext": ext,
            })
    return {"success": True, "files": sorted(files, key=lambda x: x["filename"])}


@router.get("/files/{file_id}")
async def get_doc(file_id: str):
    """获取文档详情和文本预览。"""
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            path = os.path.join(UPLOAD_DIR, fname)
            text = extract_text(path)
            return {
                "success": True,
                "file_id": file_id,
                "filename": fname,
                "size": os.path.getsize(path),
                "text_preview": text[:5000] if text else "(空)",
                "text_length": len(text),
            }
    return {"success": False, "error": "未找到文档"}


@router.delete("/files/{file_id}")
async def delete_doc(file_id: str):
    """删除文档。"""
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            path = os.path.join(UPLOAD_DIR, fname)
            os.remove(path)
            return {"success": True, "deleted": fname}
    return {"success": False, "error": "未找到文档"}
