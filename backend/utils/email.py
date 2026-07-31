"""
OAIW 邮件发送工具

支持通过 SMTP 发送 HTML/纯文本邮件。
SMTP 配置存储在系统 settings 表中，通过 Setting model 读写。

配置键:
  smtp_host      — SMTP 服务器地址 (如 smtp.qq.com)
  smtp_port      — SMTP 端口 (465 或 587)
  smtp_user      — SMTP 用户名 (完整邮箱地址)
  smtp_password  — SMTP 密码/授权码
  smtp_from_email — 发件人邮箱地址（不填则使用 smtp_user）
"""
from __future__ import annotations

import json
import smtplib
import threading
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from backend.database import SessionLocal


class SmtpConfig:
    """SMTP 配置。"""

    def __init__(
        self,
        host: str = "",
        port: int = 465,
        user: str = "",
        password: str = "",
        from_email: str = "",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email or user

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    @classmethod
    def from_db(cls) -> "SmtpConfig":
        """从数据库 settings 表读取 SMTP 配置。"""
        try:
            db = SessionLocal()
            try:
                from backend.core.models.setting import Setting

                def _get(key: str) -> str:
                    row = db.query(Setting).filter(Setting.key == key).first()
                    return row.value if row else ""

                return cls(
                    host=_get("smtp_host"),
                    port=int(_get("smtp_port") or "465"),
                    user=_get("smtp_user"),
                    password=_get("smtp_password"),
                    from_email=_get("smtp_from_email"),
                )
            finally:
                db.close()
        except Exception:
            return cls()

    def to_dict(self) -> dict:
        """返回配置字典（隐藏密码）。"""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": "******" if self.password else "",
            "from_email": self.from_email,
            "configured": self.is_configured,
        }


def _resolve_via_doh(hostname: str) -> list[str]:
    """
    通过 DNS over HTTPS (Google) 解析域名，绕过本地代理 DNS 劫持。
    """
    import json
    import urllib.request
    try:
        url = f"https://dns.google/resolve?name={hostname}&type=A"
        req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        ips = []
        for a in data.get("Answer", []):
            if a.get("type") == 1 and a.get("data"):
                ips.append(a["data"])
        return ips
    except Exception:
        return []


def _is_private_ip(ip: str) -> bool:
    """检查 IP 是否为私有/保留地址或代理虚拟 IP。"""
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return True
        # Clash 等代理使用的虚拟 IP 范围 (RFC 2544 benchmark)
        if ipaddress.ip_address(ip) in ipaddress.ip_network("198.18.0.0/15"):
            return True
        return False
    except ValueError:
        return True


def _create_smtp_connection(config: SmtpConfig):
    """
    创建 SMTP 连接。

    策略（按优先级）：
    1. 如果系统 DNS 被劫持（返回私有 IP），通过 DoH 获取真实 IP → 直接连接 587
    2. 直接连接（按配置端口）
    3. 如果直接连接失败，尝试通过系统 HTTP 代理 CONNECT 隧道
    """
    import socket as sock_mod

    def _try_connect_direct(host, port, smtp_hostname) -> smtplib.SMTP | None:
        """尝试直接 TCP 连接 + STARTTLS (端口 587)。"""
        server = None
        try:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo(smtp_hostname or host)
            if port == 587:
                if "starttls" not in server.esmtp_features:
                    server.quit()
                    return None
                server.starttls()
                server.ehlo(smtp_hostname or host)
            return server
        except Exception:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass
            return None

    smtp_hostname = config.host

    # --- 策略 1: 检测 DNS 劫持，用 DoH + 直接连接 587 ---
    try:
        direct_ip = sock_mod.getaddrinfo(config.host, 80)[0][4][0]
        if _is_private_ip(direct_ip):
            # DNS 被劫持，尝试 DoH
            real_ips = _resolve_via_doh(config.host)
            if real_ips:
                real_ip = real_ips[0]
                server = _try_connect_direct(real_ip, 587, config.host)
                if server is not None:
                    return server
    except Exception:
        pass

    # --- 策略 2: 直接连接（按配置端口）---
    try:
        if config.port == 465:
            return smtplib.SMTP_SSL(config.host, config.port, timeout=20)
        else:
            server = smtplib.SMTP(config.host, config.port, timeout=20)
            server.ehlo()
            server.starttls()
            return server
    except (smtplib.SMTPException, OSError):
        pass

    # --- 策略 3: 通过系统 HTTP 代理 CONNECT 隧道 ---
    try:
        proxy_host, proxy_port = ("127.0.0.1", 7890)
        s = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
        s.settimeout(25)
        s.connect((proxy_host, proxy_port))
        connect_req = (
            f"CONNECT {config.host}:{config.port} HTTP/1.1\r\n"
            f"Host: {config.host}:{config.port}\r\n"
            f"Connection: Keep-Alive\r\n\r\n"
        )
        s.sendall(connect_req.encode())
        resp = s.recv(4096).decode("utf-8", errors="replace")
        if "200" in resp:
            import ssl as ssl_mod
            context = ssl_mod.create_default_context()
            if config.port == 465:
                tls_sock = context.wrap_socket(s, server_hostname=config.host)
                server = smtplib.SMTP_SSL(config.host, config.port, timeout=25)
                server.sock = tls_sock
                return server
            else:
                server = smtplib.SMTP(config.host, config.port, timeout=25)
                server.sock = s
                server.ehlo()
                server.starttls()
                return server
        s.close()
    except Exception:
        try:
            s.close()
        except Exception:
            pass

    # 所有方法都失败
    raise smtplib.SMTPException(f"无法连接到 SMTP 服务器 {config.host}:{config.port}")


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    config: Optional[SmtpConfig] = None,
) -> tuple[bool, str]:
    """
    发送邮件。

    Args:
        to_email: 收件人邮箱
        subject:  邮件主题
        html_body: HTML 正文
        text_body: 纯文本正文（可选，不提供则从 HTML 简单提取）
        config:   SMTP 配置（不提供则从数据库读取）

    Returns:
        (success, error_message)
    """
    if config is None:
        config = SmtpConfig.from_db()

    if not config.is_configured:
        return False, "SMTP 未配置，请在系统设置中配置 SMTP"

    if not to_email:
        return False, "收件人邮箱为空"

    try:
        # 构建 MIME 消息
        msg = MIMEMultipart("alternative")
        msg["From"] = config.from_email
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8")

        # 纯文本部分
        if text_body is None:
            import re
            text_body = re.sub(r"<[^>]+>", "", html_body).strip()
        msg.attach(MIMEText(text_body, "plain", "utf-8"))

        # HTML 部分
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # 发送（自动处理代理）
        server = _create_smtp_connection(config)
        try:
            server.ehlo()
            server.login(config.user, config.password)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass

        return True, ""

    except smtplib.SMTPAuthenticationError:
        return False, "SMTP 认证失败，请检查用户名/密码（QQ邮箱请使用授权码）"
    except smtplib.SMTPException as e:
        return False, f"SMTP 错误: {str(e)[:200]}"
    except OSError as e:
        return False, f"网络错误: {str(e)[:200]}"
    except Exception as e:
        return False, f"发送失败: {str(e)[:200]}"


def send_notification_email(
    to_email: str,
    subject: str,
    content_text: str,
    content_html: Optional[str] = None,
    task_name: str = "",
) -> tuple[bool, str]:
    """
    发送通知邮件（带统一模板）。

    Args:
        to_email:     收件人
        subject:      邮件主题
        content_text: 正文纯文本
        content_html: 正文 HTML（自动包裹模板）
        task_name:    任务名称（用于标题前缀）

    Returns:
        (success, error_message)
    """
    prefix = f"[OAIW 工作台] "
    full_subject = f"{prefix}{subject}"

    if not content_html:
        # 纯文本转简单 HTML
        import html as htmlmod
        escaped = htmlmod.escape(content_text)
        content_html = f"<pre style='font-size:13px;line-height:1.6'>{escaped}</pre>"

    html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5;">
<div style="max-width: 680px; margin: 20px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden;">
<div style="background: linear-gradient(135deg, #409eff, #337ecc); padding: 24px 32px;">
<h1 style="color: #fff; font-size: 18px; margin: 0; font-weight: 500;">{'&#9881; ' + task_name if task_name else ''} OAIW 自动化通知</h1>
</div>
<div style="padding: 32px; color: #303133; font-size: 14px; line-height: 1.8;">
{content_html}
</div>
<div style="padding: 16px 32px; border-top: 1px solid #ebeef5; font-size: 12px; color: #c0c4cc; text-align: center;">
OAIW 操作部 AI 工作台 &mdash; 系统自动发送，请勿回复
</div>
</div>
</body>
</html>"""

    return send_email(to_email, full_subject, html_body, content_text)


# =============================================================================
# 异步发送
# =============================================================================

def send_email_async(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> None:
    """异步发送邮件（后台线程，不阻塞调用方）。"""
    threading.Thread(
        target=lambda: send_email(to_email, subject, html_body, text_body),
        daemon=True,
    ).start()


def send_notification_async(
    to_email: str,
    subject: str,
    content_text: str,
    content_html: Optional[str] = None,
    task_name: str = "",
) -> None:
    """异步发送通知邮件。"""
    threading.Thread(
        target=lambda: send_notification_email(to_email, subject, content_text, content_html, task_name),
        daemon=True,
    ).start()
