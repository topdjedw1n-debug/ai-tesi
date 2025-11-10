"""
Payment webhook related models
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric, Text, Index, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class PaymentWebhook(Base):
    """Payment webhook event tracking with race condition protection"""

    __tablename__ = "payment_webhooks"
    __table_args__ = (
        # Unique constraint on webhook_id to prevent duplicate processing
        UniqueConstraint('webhook_id', name='uq_payment_webhooks_webhook_id'),
        Index("ix_payment_webhooks_user_id", "user_id"),
        Index("ix_payment_webhooks_status", "status"),
        Index("ix_payment_webhooks_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Webhook identification (idempotency key)
    webhook_id = Column(String(255), unique=True, nullable=False, index=True)

    # Payment details
    user_id = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    payment_method = Column(String(50))

    # Processing status
    status = Column(String(20), default="pending")  # pending, processed, failed
    is_processed = Column(Boolean, default=False)

    # Metadata
    raw_payload = Column(Text)  # Store raw webhook payload for debugging
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<PaymentWebhook(id={self.id}, webhook_id={self.webhook_id}, status={self.status})>"


class PaymentJob(Base):
    """Payment processing job - the resource protected from race conditions"""

    __tablename__ = "payment_jobs"
    __table_args__ = (
        # Ensure one job per webhook
        UniqueConstraint('webhook_id', name='uq_payment_jobs_webhook_id'),
        Index("ix_payment_jobs_user_id", "user_id"),
        Index("ix_payment_jobs_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="pending")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<PaymentJob(id={self.id}, webhook_id={self.webhook_id}, status={self.status})>"
