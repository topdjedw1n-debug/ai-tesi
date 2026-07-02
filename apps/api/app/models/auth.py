"""
Authentication related models
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """User model"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Password hash for admin login (nullable for regular users who use magic links)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=True
    )  # Super admin has all permissions

    # Preferences
    preferred_language: Mapped[str] = mapped_column(
        String(10), default="en", nullable=True
    )
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=True)

    # Usage tracking
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    total_documents_created: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )
    total_cost: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )  # Cost in cents

    # Stripe
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    payments = relationship("Payment", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, active={self.is_active})>"


class MagicLinkToken(Base):
    """Magic link tokens for passwordless authentication"""

    __tablename__ = "magic_link_tokens"
    __table_args__ = (
        Index("ix_magic_link_tokens_email", "email"),
        Index("ix_magic_link_tokens_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Token state
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<MagicLinkToken(id={self.id}, email={self.email}, used={self.is_used})>"
        )


class UserSession(Base):
    """User session tracking"""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    session_token: Mapped[str] = mapped_column(
        String(512), unique=True, index=True, nullable=False
    )  # Increased for JWT tokens

    # Session state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )  # IPv6 compatible
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


class UserConsent(Base):
    """GDPR consent tracking"""

    __tablename__ = "user_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    consent_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "data_processing", "marketing"
    consented: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<UserConsent(id={self.id}, user_id={self.user_id}, type={self.consent_type})>"
