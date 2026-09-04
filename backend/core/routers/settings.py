"""
OAIW 系统设置读写路由
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.models.setting import Setting
from backend.core.services import get_current_user_required, require_admin

# 敏感设置键（在 list 中脱敏显示）：包含这些关键词的 key 值会显示为 ******
# 含 "key" 覆盖 agent_key_* / llm_api_key 等密钥型设置；不含 "_key" 的普通键不受影响
_SENSITIVE_KEYWORDS = ("password", "passwd", "secret", "token", "apikey", "api_key", "key", "authorization")


def _mask_sensitive_value(key: str, value: str) -> str:
    """设置项脱敏：敏感键只显示首尾各 2 位，中间用 * 填充。"""
    if any(k in key.lower() for k in _SENSITIVE_KEYWORDS) and value:
        if len(value) <= 4:
            return "******"
        return value[:2] + "******" + value[-2:]
    return value

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SetSettingRequest(BaseModel):
    key: str
    value: str = ""
    description: str = ""


@router.get("/get/{key}")
def get_setting(key: str, db: Session = Depends(get_db),
                _auth_user=Depends(get_current_user_required)):
    """读取单个设置项。"""
    s = db.query(Setting).filter(Setting.key == key).first()
    if not s:
        return {"success": True, "key": key, "value": "", "exists": False}
    return {"success": True, "key": key, "value": s.value, "description": s.description, "exists": True}


@router.post("/set")
def set_setting(req: SetSettingRequest, db: Session = Depends(get_db),
                _auth_user=Depends(require_admin)):
    """写入设置项 (不存在则创建, 存在则更新)。仅管理员。"""
    s = db.query(Setting).filter(Setting.key == req.key).first()
    if s:
        s.value = req.value
        if req.description:
            s.description = req.description
    else:
        s = Setting(key=req.key, value=req.value, description=req.description)
        db.add(s)
    db.commit()
    return {"success": True, "key": req.key}


@router.post("/set-multi")
def set_multi_settings(items: list[SetSettingRequest], db: Session = Depends(get_db),
                       _auth_user=Depends(require_admin)):
    """批量写入设置项。仅管理员。"""
    for item in items:
        s = db.query(Setting).filter(Setting.key == item.key).first()
        if s:
            s.value = item.value
            if item.description:
                s.description = item.description
        else:
            s = Setting(key=item.key, value=item.value, description=item.description)
            db.add(s)
    db.commit()
    return {"success": True, "count": len(items)}


@router.get("/list")
def list_settings(db: Session = Depends(get_db),
                  _auth_user=Depends(get_current_user_required)):
    """列出所有设置项（登录可读，敏感键脱敏）。"""
    settings = db.query(Setting).all()
    return {
        "success": True,
        "settings": [
            {
                "key": s.key,
                "value": _mask_sensitive_value(s.key, s.value[:100] + "..." if len(s.value) > 100 else s.value),
                "description": s.description,
            }
            for s in settings
        ],
    }


class SmtpTestRequest(BaseModel):
    to_email: str = ""
    host: str = ""
    port: int = 465
    user: str = ""
    password: str = ""
    from_email: str = ""


@router.post("/test-email")
def test_email_config(
    req: SmtpTestRequest,
    db: Session = Depends(get_db),
    _auth_user=Depends(require_admin),
):
    """测试全局 SMTP 邮箱配置 — 发送测试邮件。仅管理员。"""
    from backend.utils.email import SmtpConfig, send_email

    config = SmtpConfig(
        host=req.host,
        port=req.port,
        user=req.user,
        password=req.password,
        from_email=req.from_email,
    )

    to = req.to_email or req.user
    if not to:
        return {"success": False, "error": "未指定收件人邮箱"}

    success, err = send_email(
        to_email=to,
        subject="[OAIW] SMTP 配置测试",
        html_body="<h2 style='color:#67c23a'>SMTP 配置测试成功</h2><p>如果您收到此邮件，说明 SMTP 配置正确，邮件通知功能正常工作。</p>",
        text_body="SMTP 配置测试成功。如果您收到此邮件，说明 SMTP 配置正确，邮件通知功能正常工作。",
        config=config,
    )

    if success:
        return {"success": True, "message": f"测试邮件已发送至 {to}，请查收"}
    else:
        return {"success": False, "error": err}
