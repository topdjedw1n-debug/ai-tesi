"""
Refund request models
"""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)

    # Причина повернення
    reason = Column(Text, nullable=False)
    reason_category = Column(
        String(50)
    )  # quality, not_satisfied, technical_issue, other
    screenshots = Column(JSON)  # масив URL до скріншотів

    # Статус
    status = Column(
        String(20), nullable=False, index=True, default="pending"
    )  # pending, approved, rejected
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Розгляд
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # admin_id
    admin_comment = Column(Text, nullable=True)
    refund_amount = Column(Numeric(10, 2), nullable=True)  # для часткового повернення

    # AI рекомендації (опційно)
    ai_recommendation = Column(String(20), nullable=True)  # approve, reject, review
    risk_score = Column(Float, nullable=True)  # 0-1

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    payment = relationship("Payment")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self):
        return f"<RefundRequest(id={self.id}, user_id={self.user_id}, status={self.status})>"
