"""
OAIW 操作部AI工作台 — 配置管理
"""
from __future__ import annotations

import os
import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///D:/OAIW/oaiw.db"

    # JWT
    SECRET_KEY: str = os.getenv("OAIW_SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # LLM
    LLM_ENABLED: bool = True
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    OLLAMA_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "gemma4:latest"

    # RPA
    HEADLESS: bool = False
    RPA_TIMEOUT: int = 30000

    # Upload
    UPLOAD_DIR: str = "./uploads"

    # Redis
    REDIS_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_LLM_CACHE_TTL: int = 3600       # LLM 缓存有效期（秒）
    REDIS_RPA_CACHE_TTL: int = 300        # RPA 缓存有效期（秒）
    REDIS_RATE_LIMIT_MAX: int = 30        # 每分钟最大请求数
    REDIS_RATE_LIMIT_WINDOW: int = 60     # 速率限制时间窗口

    class Config:
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)


settings = Settings()
