"""
OAIW RAG 知识检索服务 — ChromaDB 数据飞轮

职责:
1. 文档 → 分块 → 向量化 → 存入知识库
2. 用户问题 → 检索相关知识 → 注入 Agent Prompt
3. 用户反馈 → 优化检索权重 (数据飞轮闭环)
"""
from __future__ import annotations

import uuid
import hashlib
from typing import Optional

from backend.addons.memory import get_knowledge_collection as _get_kc


def get_knowledge_collection():
    """获取知识库集合（JSON 文件存储）。"""
    return _get_kc()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """将长文本切分成重叠的块，保证检索精度。"""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # 尽量在句号/换行处断开
        if end < len(text):
            for sep in ["\n\n", "\n", "。", ".", "；", ";"]:
                cut = text.rfind(sep, start + chunk_size // 2, end)
                if cut > start:
                    end = cut + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else end
    return chunks


def ingest_document(
    text: str,
    filename: str = "",
    metadata: Optional[dict] = None,
    doc_id: Optional[str] = None,
) -> int:
    """将文档内容解析、分块后存入知识库。

    Args:
        text: 文档全文
        filename: 源文件名
        metadata: 额外元数据
        doc_id: 文档ID（不传则自动生成）

    Returns:
        存入的块数
    """
    collection = get_knowledge_collection()
    chunks = chunk_text(text)
    if not chunks:
        return 0

    base_meta = {
        "source": filename or "unknown",
        "doc_id": doc_id or str(uuid.uuid4()),
    }
    if metadata:
        base_meta.update(metadata)

    ids = []
    documents = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.md5(f"{base_meta['doc_id']}_{i}".encode()).hexdigest()
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({**base_meta, "chunk_index": i, "total_chunks": len(chunks)})

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    return len(chunks)


def search_knowledge(query: str, top_k: int = 5) -> list[dict]:
    """检索知识库，返回最相关的文档块及元数据。

    Args:
        query: 用户问题
        top_k: 返回条数

    Returns:
        [{"content": "...", "source": "...", "score": 0.xx}, ...]
    """
    collection = get_knowledge_collection()
    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, 20),
        )
        docs = results.get("documents", [[]])[0] or []
        metas = results.get("metadatas", [[]])[0] or []
        distances = results.get("distances", [[]])[0] or []

        output = []
        for i in range(len(docs)):
            score = 1 - distances[i] if i < len(distances) else 0
            meta = metas[i] if i < len(metas) else {}
            output.append({
                "content": docs[i],
                "source": meta.get("source", "unknown"),
                "doc_id": meta.get("doc_id", ""),
                "chunk": f"{meta.get('chunk_index', 0)+1}/{meta.get('total_chunks', 1)}",
                "score": round(score, 3),
            })
        return output
    except Exception as e:
        return []


def format_knowledge_context(results: list[dict], max_chars: int = 3000) -> str:
    """将检索结果格式化为可注入Prompt的上下文文本。"""
    if not results:
        return ""

    parts = ["【以下是从知识库检索到的相关信息】"]
    total = 0
    seen_sources = set()
    for r in results:
        source_info = f"来源: {r['source']}" if r['source'] not in seen_sources else ""
        seen_sources.add(r['source'])
        snippet = f"\n--- {source_info} ---\n{r['content']}" if source_info else f"\n{r['content']}"
        if total + len(snippet) > max_chars:
            break
        parts.append(snippet)
        total += len(snippet)

    parts.append("\n【请参考以上信息回答用户问题，如信息不充分则基于自身知识回答】")
    return "\n".join(parts)


def delete_document(doc_id: str) -> int:
    """从知识库删除指定文档的所有块。"""
    collection = get_knowledge_collection()
    try:
        results = collection.get(where={"doc_id": doc_id})
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)
        return len(ids)
    except Exception:
        return 0


def get_knowledge_stats() -> dict:
    """获取知识库统计信息。"""
    collection = get_knowledge_collection()
    try:
        count = collection.count()
        # 获取所有源文件列表
        all_data = collection.get(include=["metadatas"])
        sources = set()
        for m in (all_data.get("metadatas") or []):
            if m and m.get("source"):
                sources.add(m["source"])
        return {"chunks": count, "documents": len(sources), "sources": sorted(sources)}
    except Exception:
        return {"chunks": 0, "documents": 0, "sources": []}
