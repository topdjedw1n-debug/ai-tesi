"""Payment model for Stripe integration"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Payment(Base):
    """Payment transactions via Stripe"""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=True, index=True
    )

    # Stripe identifiers
    stripe_session_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )  # Checkout session ID
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )  # Payment intent ID (from checkout session)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Payment details
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # pending, completed, failed, refunded

    # Discount (optional)
    discount_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, nullable=True
    )

    # Metadata
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="payments")
    document = relationship("Document", back_populates="payment", uselist=False)

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user_id={self.user_id}, status={self.status})>"
