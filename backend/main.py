"""
OAIW 操作部AI工作台 — 后端入口 (FastAPI)
"""
from __future__ import annotations

import os
import sys

# 确保 D:\OAIW 在 sys.path 中
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # D:\OAIW
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import Base, engine
from backend.core.models import User  # noqa — 确保模型注册
from backend.core.routers import auth
from backend.core.routers.users import router as users_router
from backend.addons.llm.routers.chat import router as chat_router
from backend.addons.llm.routers.chat_history import router as chat_history_router
from backend.addons.llm.routers.chat_history import ChatConversation, ChatMessage  # noqa — 注册模型到Base元数据，确保建表
from backend.core.routers.rpa import router as rpa_router
from backend.core.routers.docs import router as docs_router
from backend.core.routers.settings import router as settings_router
from backend.core.routers.air_freight import router as air_freight_router
from backend.core.routers.fcl import router as fcl_router
from backend.core.routers.sea_freight import router as sea_freight_router
from backend.core.routers.merge import router as merge_router
from backend.core.models.setting import Setting  # noqa
from backend.addons.rag.routers import router as knowledge_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时自动建表。"""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="OAIW 操作部AI工作台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 注册路由 =====
app.include_router(auth.router)
app.include_router(users_router)
app.include_router(chat_router)
app.include_router(chat_history_router)
app.include_router(rpa_router)
app.include_router(docs_router)
app.include_router(settings_router)
app.include_router(knowledge_router)
app.include_router(air_freight_router)
app.include_router(fcl_router)
app.include_router(sea_freight_router)
app.include_router(merge_router)


@app.get("/api/health")
def health():
    redis_status = {}
    if settings.REDIS_ENABLED:
        from backend.addons.llm.redis_cache import health_check
        redis_status = health_check()
    return {
        "status": "ok",
        "version": "1.0.0",
        "llm_enabled": settings.LLM_ENABLED,
        "redis": redis_status,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=7999, reload=True)
