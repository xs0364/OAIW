"""
OAIW 数据库初始化脚本 — 创建初始管理员用户
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Base, engine, SessionLocal
from backend.core.models import User
from backend.core.services import hash_password


def seed():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                hashed_password=hash_password(os.getenv("OAIW_ADMIN_PASSWORD", "admin123")),
                display_name="系统管理员",
                role="admin",
            )
            db.add(admin)
            db.commit()
            print("Admin user created: admin / admin123")
        else:
            print("Admin user already exists")

        # 创建演示操作员
        op = db.query(User).filter(User.username == "operator").first()
        if not op:
            op = User(
                username="operator",
                hashed_password=hash_password(os.getenv("OAIW_OP_PASSWORD", "op123")),
                display_name="操作员",
                role="operator",
            )
            db.add(op)
            db.commit()
            print("Operator user created: operator / op123")
        else:
            print("Operator user already exists")

        print("Seed completed!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
