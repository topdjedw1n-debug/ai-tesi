"""
Admin-related models
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
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

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Дія
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50))  # user, document, payment, settings, refund
    target_id = Column(Integer, nullable=True)

    # Зміни
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

    # Метадані
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    correlation_id = Column(String(100))  # для трейсингу

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    admin = relationship("User")

    def __repr__(self):
        return f"<AdminAuditLog(id={self.id}, admin_id={self.admin_id}, action={self.action})>"


class SystemSetting(Base):
    """Системні налаштування з версіонуванням"""

    __tablename__ = "system_settings"
    __table_args__ = (Index("idx_settings_category", "category"),)

    key = Column(String(100), primary_key=True)  # Наприклад: "pricing.price_per_page"
    value = Column(JSON, nullable=False)
    category = Column(
        String(50), nullable=False, index=True
    )  # pricing, ai, limits, maintenance

    # Версіонування та аудит
    version = Column(Integer, default=1)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    updater = relationship("User")

    def __repr__(self):
        return f"<SystemSetting(key={self.key}, category={self.category})>"


class AdminSession(Base):
    """Сесії адміністраторів з відстеженням активності"""

    __tablename__ = "admin_sessions"
    __table_args__ = (
        Index("idx_admin_sessions_admin", "admin_id"),
        Index("idx_admin_sessions_token", "session_token"),
        Index("idx_admin_sessions_expires", "expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(String(512), unique=True, nullable=False, index=True)

    # Метадані
    ip_address = Column(String(45))
    user_agent = Column(Text)

    # Статус
    is_active = Column(Boolean, default=True)
    forced_logout = Column(Boolean, default=False)  # для примусового виходу

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    admin = relationship("User")

    def __repr__(self):
        return f"<AdminSession(id={self.id}, admin_id={self.admin_id}, active={self.is_active})>"


class AdminPermission(Base):
    """Гранулярні дозволи для адмінів"""

    __tablename__ = "admin_permissions"
    __table_args__ = (
        Index("idx_admin_permissions_user", "user_id"),
        Index("ix_admin_permission_user_perm", "user_id", "permission"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    permission = Column(String(50), nullable=False)  # VIEW_USERS, EDIT_USERS, etc.

    # Аудит
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    granter = relationship("User", foreign_keys=[granted_by])
    revoker = relationship("User", foreign_keys=[revoked_by])

    def __repr__(self):
        return f"<AdminPermission(id={self.id}, user_id={self.user_id}, permission={self.permission})>"


class EmailTemplate(Base):
    """Email шаблони для різних мов"""

    __tablename__ = "email_templates"
    __table_args__ = (Index("ix_email_template_name_lang", "name", "language"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # welcome, refund_approved, etc.
    language = Column(String(10), nullable=False, default="en")

    # Контент
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=True)
    variables = Column(
        JSON
    )  # список доступних змінних: ["user_name", "document_title"]

    # Статус
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)

    # Аудит
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    def __repr__(self):
        return (
            f"<EmailTemplate(id={self.id}, name={self.name}, language={self.language})>"
        )
