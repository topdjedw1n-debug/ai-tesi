"""Durable, owner-scoped Telegram actions and support requests."""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class OperatorBotAction(Base):
    __tablename__ = "operator_bot_actions"

    id = Column(String(32), primary_key=True)
    telegram_user_id = Column(String(32), nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint = Column(String(64), nullable=False)
    last_job_id = Column(Integer, nullable=True)
    retry_reason = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OperatorSupportRequest(Base):
    __tablename__ = "operator_support_requests"

    id = Column(String(32), primary_key=True)
    telegram_user_id = Column(String(32), nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    summary = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False, default="pending_review")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
