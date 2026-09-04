"""
OAIW 用户邮箱(SMTP)配置路由 — 各账号管理各自的邮箱配置

- GET  /api/email-config      读取当前用户配置（密码脱敏）
- PUT  /api/email-config      保存当前用户配置（不存在则创建）
- POST /api/email-config/test 用当前用户配置发送测试邮件

所有接口按当前登录用户(user.id)严格隔离，不涉及全局 Setting 表。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.models import User
from backend.core.models.user_smtp_config import UserSmtpConfig
from backend.core.services import get_current_user_required

router = APIRouter(prefix="/api/email-config", tags=["email-config"])

MASKED_PASSWORD = "******"


class EmailConfigRequest(BaseModel):
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""


def _get_or_create(db: Session, user_id: int) -> UserSmtpConfig:
    row = db.query(UserSmtpConfig).filter(UserSmtpConfig.user_id == user_id).first()
    if row is None:
        row = UserSmtpConfig(user_id=user_id)
        db.add(row)
    return row


def _to_dict(row: UserSmtpConfig) -> dict:
    """序列化为前端展示结构（密码始终脱敏）。"""
    return {
        "smtp_host": row.smtp_host or "",
        "smtp_port": row.smtp_port or 465,
        "smtp_user": row.smtp_user or "",
        "smtp_password": MASKED_PASSWORD if row.smtp_password else "",
        "smtp_from_email": row.smtp_from_email or "",
        "configured": row.is_configured,
    }


@router.get("")
def get_email_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
):
    """读取当前登录用户的邮箱配置（密码脱敏）。"""
    row = _get_or_create(db, user.id)
    db.commit()
    return {"success": True, **(_to_dict(row))}


@router.put("")
def save_email_config(
    req: EmailConfigRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
):
    """保存当前登录用户的邮箱配置（不存在则创建，按 user_id 唯一）。"""
    row = _get_or_create(db, user.id)

    # 密码未变更（空 或 仍为掩码）则保留原密码
    if req.smtp_password and req.smtp_password != MASKED_PASSWORD:
        row.smtp_password = req.smtp_password

    row.smtp_host = req.smtp_host or ""
    row.smtp_port = req.smtp_port or 465
    row.smtp_user = req.smtp_user or ""
    row.smtp_from_email = req.smtp_from_email or ""

    db.commit()
    return {"success": True, **_to_dict(row)}


@router.post("/test")
def test_email_config(
    req: EmailConfigRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
):
    """用当前登录用户的邮箱配置发送测试邮件（不保存）。"""
    from backend.utils.email import SmtpConfig, send_email

    row = _get_or_create(db, user.id)
    password = req.smtp_password
    if not password or password == MASKED_PASSWORD:
        password = row.smtp_password or ""

    config = SmtpConfig(
        host=req.smtp_host or row.smtp_host or "",
        port=req.smtp_port or row.smtp_port or 465,
        user=req.smtp_user or row.smtp_user or "",
        password=password,
        from_email=req.smtp_from_email or row.smtp_from_email or "",
    )

    if not config.is_configured:
        return {"success": False, "error": "邮箱尚未配置完整（SMTP 服务器/账号/授权码必填）"}

    to = req.smtp_user or row.smtp_user or ""
    if not to:
        return {"success": False, "error": "未指定收件人邮箱"}

    success, err = send_email(
        to_email=to,
        subject="[OAIW] 邮箱配置测试",
        html_body=(
            "<h2 style='color:#67c23a'>邮箱配置测试成功</h2>"
            "<p>如果您收到此邮件，说明您的邮箱 SMTP 配置正确，AI 助手邮件功能可正常使用。</p>"
        ),
        text_body="邮箱配置测试成功。如果您收到此邮件，说明您的邮箱 SMTP 配置正确。",
        config=config,
    )

    if success:
        return {"success": True, "message": f"测试邮件已发送至 {to}，请查收"}
    return {"success": False, "error": err}
