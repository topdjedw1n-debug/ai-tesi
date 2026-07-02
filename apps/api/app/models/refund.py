"""
Refund request models
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class RefundRequest(Base):
    """Модель для запитів на повернення коштів"""

    __tablename__ = "refund_requests"
    __table_args__ = (
        Index("idx_refund_status", "status"),
        Index("idx_refund_user", "user_id"),
        Index("idx_refund_payment", "payment_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payments.id"), nullable=False, index=True
    )

    # Причина повернення
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reason_category: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # quality, not_satisfied, technical_issue, other
    screenshots: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )  # масив URL до скріншотів

    # Статус
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, default="pending"
    )  # pending, approved, rejected
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    # Розгляд
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # admin_id
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )  # для часткового повернення

    # AI рекомендації (опційно)
    ai_recommendation: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # approve, reject, review
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    payment = relationship("Payment")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<RefundRequest(id={self.id}, user_id={self.user_id}, status={self.status})>"
