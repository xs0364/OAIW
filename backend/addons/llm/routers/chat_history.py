"""
OAIW 聊天历史持久化 — 保存/加载对话记录

模型表名: chat_conversations, chat_messages
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, relationship

from backend.database import Base, get_db
from backend.config import settings

# ===== Models =====

class ChatConversation(Base):
    """对话会话。"""
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), default="新对话")
    agent_mode = Column(String(50), default="auto")  # auto | nim_gpt | nim_qwen | nim_minimax | parallel
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """单条聊天消息。"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, default="")
    agent_name = Column(String(50), default="")    # 哪个Agent回复的
    agent_label = Column(String(100), default="")  # 显示名称
    model_name = Column(String(100), default="")   # 模型名
    created_at = Column(DateTime, default=datetime.now)

    conversation = relationship("ChatConversation", back_populates="messages")


# ===== Schemas =====

class CreateConversationRequest(BaseModel):
    title: str = "新对话"
    agent_mode: str = "auto"


class SaveMessageRequest(BaseModel):
    role: str
    content: str = ""
    agent_name: str = ""
    agent_label: str = ""
    model_name: str = ""


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    agent_mode: Optional[str] = None


# ===== Router =====

router = APIRouter(prefix="/api/chat", tags=["chat_history"])


def _get_user_id(authorization: str, db: Session) -> int:
    """从token解析user_id。"""
    from backend.core.services import get_current_user
    token = authorization.replace("Bearer ", "") if authorization else ""
    user = get_current_user(token, db)
    if not user:
        raise PermissionError("未登录")
    return user.id


@router.get("/conversations")
def list_conversations(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """列出当前用户的所有对话。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    convs = (
        db.query(ChatConversation)
        .filter(ChatConversation.user_id == user_id)
        .order_by(ChatConversation.updated_at.desc())
        .all()
    )
    return {
        "success": True,
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "agent_mode": c.agent_mode,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            }
            for c in convs
        ],
    }


@router.post("/conversations")
def create_conversation(
    req: CreateConversationRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """创建新对话。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    conv = ChatConversation(
        user_id=user_id,
        title=req.title,
        agent_mode=req.agent_mode,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {
        "success": True,
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "agent_mode": conv.agent_mode,
        },
    }


@router.patch("/conversations/{conv_id}")
def update_conversation(
    conv_id: int,
    req: UpdateConversationRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """更新对话（标题、模式）。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conv_id,
        ChatConversation.user_id == user_id,
    ).first()
    if not conv:
        return {"success": False, "error": "对话不存在"}
    if req.title is not None:
        conv.title = req.title
    if req.agent_mode is not None:
        conv.agent_mode = req.agent_mode
    conv.updated_at = datetime.now()
    db.commit()
    return {"success": True}


@router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """删除对话及其所有消息。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conv_id,
        ChatConversation.user_id == user_id,
    ).first()
    if not conv:
        return {"success": False, "error": "对话不存在"}
    db.delete(conv)
    db.commit()
    return {"success": True}


@router.get("/conversations/{conv_id}/messages")
def get_messages(
    conv_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """获取指定对话的所有消息。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conv_id,
        ChatConversation.user_id == user_id,
    ).first()
    if not conv:
        return {"success": False, "error": "对话不存在"}
    return {
        "success": True,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "agent_name": m.agent_name,
                "agent_label": m.agent_label,
                "model_name": m.model_name,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in conv.messages
        ],
    }


@router.post("/conversations/{conv_id}/messages")
def save_message(
    conv_id: int,
    req: SaveMessageRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """保存一条消息到对话中。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conv_id,
        ChatConversation.user_id == user_id,
    ).first()
    if not conv:
        return {"success": False, "error": "对话不存在"}
    msg = ChatMessage(
        conversation_id=conv_id,
        role=req.role,
        content=req.content,
        agent_name=req.agent_name,
        agent_label=req.agent_label,
        model_name=req.model_name,
    )
    db.add(msg)
    conv.message_count = (conv.message_count or 0) + 1
    conv.updated_at = datetime.now()
    db.commit()
    db.refresh(msg)
    return {
        "success": True,
        "message": {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content[:100],
        },
    }


@router.delete("/conversations/{conv_id}/messages/{msg_id}")
def delete_message(
    conv_id: int,
    msg_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """删除单条消息。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    # Verify conversation ownership
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conv_id,
        ChatConversation.user_id == user_id,
    ).first()
    if not conv:
        return {"success": False, "error": "对话不存在"}
    msg = db.query(ChatMessage).filter(
        ChatMessage.id == msg_id,
        ChatMessage.conversation_id == conv_id,
    ).first()
    if not msg:
        return {"success": False, "error": "消息不存在"}
    db.delete(msg)
    conv.message_count = max(0, (conv.message_count or 0) - 1)
    conv.updated_at = datetime.now()
    db.commit()
    return {"success": True}


@router.post("/conversations/{conv_id}/messages-batch")
def save_messages_batch(
    conv_id: int,
    messages: list[SaveMessageRequest],
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """批量保存消息（用于保存整个对话记录）。"""
    try:
        user_id = _get_user_id(authorization or "", db)
    except PermissionError:
        return {"success": False, "error": "未登录"}
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conv_id,
        ChatConversation.user_id == user_id,
    ).first()
    if not conv:
        return {"success": False, "error": "对话不存在"}
    for req in messages:
        msg = ChatMessage(
            conversation_id=conv_id,
            role=req.role,
            content=req.content,
            agent_name=req.agent_name,
            agent_label=req.agent_label,
            model_name=req.model_name,
        )
        db.add(msg)
    conv.message_count = (conv.message_count or 0) + len(messages)
    conv.updated_at = datetime.now()
    db.commit()
    return {"success": True, "count": len(messages)}
