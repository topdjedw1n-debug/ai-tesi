"""Payment model for Stripe integration"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Payment(Base):
    """Payment transactions via Stripe"""

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)

    # Stripe identifiers
    stripe_session_id = Column(
        String(255), unique=True, nullable=True, index=True
    )  # Checkout session ID
    stripe_payment_intent_id = Column(
        String(255), unique=True, nullable=True, index=True
    )  # Payment intent ID (from checkout session)
    stripe_customer_id = Column(String(255), nullable=True, index=True)

    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="EUR", nullable=False)
    status = Column(
        String(20), nullable=False, index=True
    )  # pending, completed, failed, refunded

    # Discount (optional)
    discount_code = Column(String(50), nullable=True)
    discount_amount = Column(Numeric(10, 2), default=0)

    # Metadata
    payment_method = Column(String(50), nullable=True)
    failure_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="payments")
    document = relationship("Document", back_populates="payment", uselist=False)

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, status={self.status})>"
