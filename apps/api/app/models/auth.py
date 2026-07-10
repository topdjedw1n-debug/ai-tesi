"""
Authentication related models
"""

from sqlalchemy import (
    DDL,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """User model"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)

    # Password hash for admin login (nullable for regular users who use magic links)
    password_hash = Column(String(255), nullable=True)

    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_super_admin = Column(Boolean, default=False)  # Super admin has all permissions
    # Durable privacy intent. Once set, every generation enqueue path must
    # refuse new work even when the actual storage cleanup needs a later retry.
    deletion_requested_at = Column(DateTime(timezone=True), nullable=True)

    # Preferences
    preferred_language = Column(String(10), default="en")
    timezone = Column(String(50), default="UTC")

    # Usage tracking
    total_tokens_used = Column(Integer, default=0)
    total_documents_created = Column(Integer, default=0)
    total_cost = Column(Integer, default=0)  # Cost in cents

    # Stripe
    stripe_customer_id = Column(String(255), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login = Column(DateTime(timezone=True))

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

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=False)

    # Token state
    is_used = Column(Boolean, default=False)
    is_expired = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))

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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(
        String(512), unique=True, index=True, nullable=False
    )  # Increased for JWT tokens

    # Session state
    is_active = Column(Boolean, default=True)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(String(500))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


class UserConsent(Base):
    """GDPR consent tracking"""

    __tablename__ = "user_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    consent_type = Column(
        String(100), nullable=False
    )  # e.g., "data_processing", "marketing"
    consented = Column(Boolean, default=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserConsent(id={self.id}, user_id={self.user_id}, type={self.consent_type})>"


# Production receives equivalent PostgreSQL triggers from migration 023. Tests
# and local SQLite databases need the same invariant or a race regression could
# pass locally while allowing an enqueue for an account already being deleted.
event.listen(
    Base.metadata,
    "after_create",
    DDL(
        """
        CREATE TRIGGER IF NOT EXISTS trg_generation_job_block_deleting_user_insert
        BEFORE INSERT ON ai_generation_jobs
        FOR EACH ROW
        WHEN NEW.status IN ('queued', 'running')
          AND EXISTS (
              SELECT 1 FROM users
              WHERE id = NEW.user_id AND deletion_requested_at IS NOT NULL
          )
        BEGIN
            SELECT RAISE(ABORT, 'generation blocked: account deletion requested');
        END
        """
    ).execute_if(dialect="sqlite"),
)
event.listen(
    Base.metadata,
    "after_create",
    DDL(
        """
        CREATE TRIGGER IF NOT EXISTS trg_generation_job_block_deleting_user_update
        BEFORE UPDATE OF user_id, status ON ai_generation_jobs
        FOR EACH ROW
        WHEN NEW.status IN ('queued', 'running')
          AND OLD.status NOT IN ('queued', 'running')
          AND EXISTS (
              SELECT 1 FROM users
              WHERE id = NEW.user_id AND deletion_requested_at IS NOT NULL
          )
        BEGIN
            SELECT RAISE(ABORT, 'generation blocked: account deletion requested');
        END
        """
    ).execute_if(dialect="sqlite"),
)
