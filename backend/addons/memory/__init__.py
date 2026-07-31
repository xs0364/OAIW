"""
OAIW 记忆系统 — JSON 文件向量存储（替代 ChromaDB）

提供 RAG 检索和自动记忆存储功能。
兼容 ChromaDB API 接口，数据存储在 JSON 文件中。
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Optional

# 数据存储路径
_DATA_DIR = "D:/OAIW/oaiw_data"
_MEMORY_FILE = os.path.join(_DATA_DIR, "memory_store.json")
_KNOWLEDGE_FILE = os.path.join(_DATA_DIR, "knowledge_store.json")

os.makedirs(_DATA_DIR, exist_ok=True)


class JsonCollection:
    """简单的 JSON 文件集合，模拟 ChromaDB Collection 接口。"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._data = self._load()

    def _load(self) -> list:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def count(self) -> int:
        return len(self._data)

    def add(self, documents: list[str], metadatas: list[dict], ids: list[str]):
        for i, doc_id in enumerate(ids):
            self._data.append({
                "id": doc_id,
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
            })
        self._save()

    def get(self, include: Optional[list[str]] = None, where: Optional[dict] = None):
        """获取数据，支持按条件过滤。"""
        items = self._data
        if where:
            for key, val in where.items():
                items = [it for it in items if it.get("metadata", {}).get(key) == val]

        result = {"ids": [it["id"] for it in items]}
        if include and "metadatas" in include:
            result["metadatas"] = [it["metadata"] for it in items]
        if include and "documents" in include:
            result["documents"] = [it["document"] for it in items]
        return result

    def query(self, query_texts: list[str], n_results: int = 5) -> dict:
        """检索（简单关键词匹配，后续可升级为向量检索）。"""
        query = query_texts[0].lower() if query_texts else ""
        scored = []
        for item in self._data:
            doc = item.get("document", "")
            score = 0
            # 简单关键词匹配
            if query:
                q_words = [w for w in query.split() if len(w) > 1]
                for w in q_words:
                    score += doc.lower().count(w) * 0.01
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_results]

        return {
            "documents": [[t[1]["document"] for t in top]],
            "metadatas": [[t[1]["metadata"] for t in top]],
            "distances": [[1 - t[0] for t in top]],
            "ids": [[t[1]["id"] for t in top]],
        }

    def delete(self, ids: list[str]):
        self._data = [it for it in self._data if it["id"] not in ids]
        self._save()


# ===== 单例集合 =====
_memory_collection: Optional[JsonCollection] = None
_knowledge_collection: Optional[JsonCollection] = None


def get_memory_collection() -> JsonCollection:
    global _memory_collection
    if _memory_collection is None:
        _memory_collection = JsonCollection(_MEMORY_FILE)
    return _memory_collection


def get_knowledge_collection() -> JsonCollection:
    global _knowledge_collection
    if _knowledge_collection is None:
        _knowledge_collection = JsonCollection(_KNOWLEDGE_FILE)
    return _knowledge_collection


# ===== ChromaDB 兼容接口（给旧代码用）=====
_chroma_client = None


def get_chroma_client():
    """兼容旧接口 — 返回一个伪装成 ChromaDB client 的对象。"""
    global _chroma_client
    if _chroma_client is None:
        class _FakeChromaClient:
            def get_collection(self, name):
                if name == "oaiw_knowledge":
                    return get_knowledge_collection()
                return get_memory_collection()
            def create_collection(self, name, metadata=None):
                return self.get_collection(name)
        _chroma_client = _FakeChromaClient()
    return _chroma_client


def get_or_create_collection(name: str = "oaiw_memory"):
    """兼容旧接口。"""
    return get_memory_collection() if name == "oaiw_memory" else get_knowledge_collection()


def add_memory(text: str, metadata: Optional[dict] = None, doc_id: Optional[str] = None):
    """存入一条记忆。"""
    collection = get_memory_collection()
    collection.add(
        documents=[text],
        metadatas=[metadata or {}],
        ids=[doc_id or str(uuid.uuid4())],
    )


def search_memory(query: str, top_k: int = 3) -> list[str]:
    """检索相关记忆。"""
    collection = get_memory_collection()
    try:
        results = collection.query(query_texts=[query], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        return docs if docs else []
    except Exception:
        return []


def delete_memory(doc_id: str):
    """删除一条记忆。"""
    collection = get_memory_collection()
    try:
        collection.delete(ids=[doc_id])
    except Exception:
        pass
