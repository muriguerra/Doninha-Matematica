"""
db/models.py - Modelos ORM (sessoes de chat e mensagens)
=========================================================
Reconstruido a partir do bytecode em __pycache__/models.cpython-312.pyc
apos a migracao Windows -> Linux. Inclui a coluna device_id usada pelo backend.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)
    device_id = Column(String, default="unknown", index=True)
    created_at = Column(DateTime, default=_utcnow)

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String)        # system | user | assistant
    content = Column(Text)

    session = relationship("ChatSession", back_populates="messages")
