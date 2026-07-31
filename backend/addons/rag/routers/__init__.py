"""
OAIW 知识库管理路由 — 上传文档 → 解析 → 分块 → 存入知识库
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
from backend.parser import extract_text
from backend.addons.rag import (
    ingest_document,
    search_knowledge,
    delete_document,
    get_knowledge_stats,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "knowledge")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    category: str = Form("general"),
    authorization: Optional[str] = Header(None),
):
    """上传文档到知识库：保存 → 解析 → 分块 → 向量化存储。"""
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    doc_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # 解析文本
    text = extract_text(save_path)
    if not text or len(text.strip()) < 10:
        return {"success": False, "error": "文档内容为空或无法解析", "doc_id": doc_id}

    # 分块存入知识库
    metadata = {"category": category, "file_ext": ext}
    chunks = ingest_document(
        text=text,
        filename=file.filename or "unknown",
        metadata=metadata,
        doc_id=doc_id,
    )

    return {
        "success": True,
        "doc_id": doc_id,
        "filename": file.filename,
        "category": category,
        "size": len(content),
        "text_length": len(text),
        "chunks": chunks,
        "preview": text[:500],
    }


@router.post("/search")
def search(req: SearchRequest):
    """检索知识库。"""
    results = search_knowledge(req.query, top_k=req.top_k)
    context = "\n\n".join(
        f"[{r['source']} 第{r['chunk']}] (相关度:{r['score']})\n{r['content']}"
        for r in results
    )
    return {
        "success": True,
        "query": req.query,
        "results": results,
        "context": context,
        "result_count": len(results),
    }


@router.delete("/{doc_id}")
def delete(doc_id: str):
    """从知识库删除文档。"""
    deleted = delete_document(doc_id)
    return {"success": True, "deleted_chunks": deleted}


@router.get("/stats")
def stats():
    """知识库统计。"""
    return {"success": True, **get_knowledge_stats()}
