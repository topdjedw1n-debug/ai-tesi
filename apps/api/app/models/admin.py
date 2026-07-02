"""
Admin-related models
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AdminAuditLog(Base):
    """Аудит лог адміністративних дій"""

    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("idx_audit_admin", "admin_id"),
        Index("idx_audit_date", "created_at"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    # Дія
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # user, document, payment, settings, refund
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Зміни
    old_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Any] = mapped_column(JSON, nullable=True)

    # Метадані
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )  # IPv6 compatible
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # для трейсингу

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=True
    )

    # Relationships
    admin = relationship("User")

    def __repr__(self) -> str:
        return f"<AdminAuditLog(id={self.id}, admin_id={self.admin_id}, action={self.action})>"


class SystemSetting(Base):
    """Системні налаштування з версіонуванням"""

    __tablename__ = "system_settings"
    __table_args__ = (Index("idx_settings_category", "category"),)

    key: Mapped[str] = mapped_column(
        String(100), primary_key=True
    )  # Наприклад: "pricing.price_per_page"
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # pricing, ai, limits, maintenance

    # Версіонування та аудит
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    updated_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    updater = relationship("User")

    def __repr__(self) -> str:
        return f"<SystemSetting(key={self.key}, category={self.category})>"


class AdminSession(Base):
    """Сесії адміністраторів з відстеженням активності"""

    __tablename__ = "admin_sessions"
    __table_args__ = (
        Index("idx_admin_sessions_admin", "admin_id"),
        Index("idx_admin_sessions_token", "session_token"),
        Index("idx_admin_sessions_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    session_token: Mapped[str] = mapped_column(
        String(512), unique=True, nullable=False, index=True
    )

    # Метадані
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    forced_logout: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=True
    )  # для примусового виходу

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Relationships
    admin = relationship("User")

    def __repr__(self) -> str:
        return f"<AdminSession(id={self.id}, admin_id={self.admin_id}, active={self.is_active})>"


class AdminPermission(Base):
    """Гранулярні дозволи для адмінів"""

    __tablename__ = "admin_permissions"
    __table_args__ = (
        Index("idx_admin_permissions_user", "user_id"),
        Index("ix_admin_permission_user_perm", "user_id", "permission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    permission: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # VIEW_USERS, EDIT_USERS, etc.

    # Аудит
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    granted_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    granter = relationship("User", foreign_keys=[granted_by])
    revoker = relationship("User", foreign_keys=[revoked_by])

    def __repr__(self) -> str:
        return f"<AdminPermission(id={self.id}, user_id={self.user_id}, permission={self.permission})>"


class EmailTemplate(Base):
    """Email шаблони для різних мов"""

    __tablename__ = "email_templates"
    __table_args__ = (Index("ix_email_template_name_lang", "name", "language"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # welcome, refund_approved, etc.
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    # Контент
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )  # список доступних змінних: ["user_name", "document_title"]

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=True)

    # Аудит
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    updated_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    def __repr__(self) -> str:
        return (
            f"<EmailTemplate(id={self.id}, name={self.name}, language={self.language})>"
        )
