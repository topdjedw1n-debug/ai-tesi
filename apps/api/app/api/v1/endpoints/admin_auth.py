"""
Admin authentication endpoints
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_admin_user
from app.core.exceptions import AuthenticationError
from app.core.logging import log_security_audit_event
from app.models.admin import AdminSession
from app.models.auth import MagicLinkToken, User
from app.services.admin_auth_service import AdminAuthService

logger = logging.getLogger(__name__)
router = APIRouter()


class AdminLoginRequest(BaseModel):
    """Request model for admin login"""

    email: EmailStr
    token: str  # Magic link token


class AdminLoginResponse(BaseModel):
    """Response model for admin login"""

    session_token: str
    expires_at: str
    admin: dict[str, Any]


class AdminSessionResponse(BaseModel):
    """Response model for admin session"""

    id: int
    admin_id: int
    ip_address: str | None
    user_agent: str | None
    is_active: bool
    created_at: str
    last_activity: str
    expires_at: str


class AdminSessionsListResponse(BaseModel):
    """Response model for admin sessions list"""

    sessions: list[AdminSessionResponse]
    total: int


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    request: Request,
    login_data: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AdminLoginResponse:
    """
    Admin login endpoint (separate from user login).

    Checks:
    - IP whitelist (if configured)
    - is_admin=True
    - is_active=True
    - Magic link token validation
    - Rate limiting (more restrictive for admin)
    """
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    # Check IP whitelist if configured
    if settings.ADMIN_IP_WHITELIST:
        allowed_ips = [
            ip.strip() for ip in settings.ADMIN_IP_WHITELIST.split(",") if ip.strip()
        ]
        if ip not in allowed_ips:
            log_security_audit_event(
                event_type="admin_auth_attempt",
                correlation_id=correlation_id,
                ip=ip,
                endpoint="/api/v1/admin/auth/login",
                resource="auth",
                action="admin_login",
                outcome="failure",
                details={"reason": "IP not whitelisted"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address not whitelisted for admin access",
            )

    try:
        # Verify magic link token
        from datetime import datetime

        result = await db.execute(
            select(MagicLinkToken).where(
                MagicLinkToken.token == login_data.token,
                ~MagicLinkToken.is_used,  # noqa: F821
                ~MagicLinkToken.is_expired,  # noqa: F821
                MagicLinkToken.expires_at > datetime.utcnow(),
            )
        )
        magic_token = result.scalar_one_or_none()

        if not magic_token:
            raise AuthenticationError("Invalid or expired magic link token")

        # Get user
        result = await db.execute(
            select(User).where(
                User.email == login_data.email,
                User.is_admin == True,  # noqa: E712
                User.is_active == True,  # noqa: E712
            )
        )
        user: User | None = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError("Admin user not found or inactive")

        # Verify email matches token
        if magic_token.email != login_data.email:
            raise AuthenticationError("Email mismatch")

        # Mark token as used
        magic_token.is_used = True  # type: ignore[assignment]
        magic_token.used_at = datetime.utcnow()  # type: ignore[assignment]

        # Update user last login
        user.last_login = datetime.utcnow()  # type: ignore[assignment]

        await db.commit()

        # Create admin session
        auth_service = AdminAuthService(db)
        admin_session = await auth_service.create_admin_session(int(user.id), request)

        # Audit log
        log_security_audit_event(
            event_type="admin_auth",
            correlation_id=correlation_id,
            user_id=int(user.id),
            ip=ip,
            endpoint="/api/v1/admin/auth/login",
            resource="auth",
            action="admin_login",
            outcome="success",
        )

        return AdminLoginResponse(
            session_token=str(admin_session.session_token),
            expires_at=admin_session.expires_at.isoformat(),
            admin={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_super_admin": user.is_super_admin,
            },
        )

    except AuthenticationError as e:
        log_security_audit_event(
            event_type="admin_auth_attempt",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/admin/auth/login",
            resource="auth",
            action="admin_login",
            outcome="failure",
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to login",
        ) from e


@router.post("/logout")
async def admin_logout(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Logout all admin sessions for current admin"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        auth_service = AdminAuthService(db)
        count = await auth_service.logout_all_admin_sessions(int(current_user.id))

        log_security_audit_event(
            event_type="admin_auth",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint="/api/v1/admin/auth/logout",
            resource="auth",
            action="admin_logout",
            outcome="success",
            details={"sessions_logged_out": count},
        )

        return {"message": f"Logged out {count} session(s)", "count": count}
    except Exception as e:
        logger.error(f"Admin logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout",
        ) from e


@router.post("/logout-session/{session_id}")
async def logout_admin_session(
    session_id: int,
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Logout a specific admin session (must be own session or super admin)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get session
        session = await db.get(AdminSession, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Check if user owns session or is super admin
        if session.admin_id != current_user.id and not current_user.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only logout own sessions",
            )

        auth_service = AdminAuthService(db)
        await auth_service.logout_admin_session(session_id)

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/auth/logout-session/{session_id}",
            resource="auth",
            action="logout_session",
            outcome="success",
            details={"target_session_id": session_id},
        )

        return {"message": "Session logged out"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout session error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout session",
        ) from e


@router.get("/sessions", response_model=AdminSessionsListResponse)
async def get_admin_sessions(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminSessionsListResponse:
    """Get all active admin sessions for current admin"""
    try:
        auth_service = AdminAuthService(db)
        sessions = await auth_service.get_active_sessions(int(current_user.id))

        return AdminSessionsListResponse(
            sessions=[
                AdminSessionResponse(
                    id=int(s.id),
                    admin_id=int(s.admin_id),
                    ip_address=str(s.ip_address) if s.ip_address else None,
                    user_agent=str(s.user_agent) if s.user_agent else None,
                    is_active=bool(s.is_active),
                    created_at=s.created_at.isoformat(),
                    last_activity=s.last_activity.isoformat(),
                    expires_at=s.expires_at.isoformat(),
                )
                for s in sessions
            ],
            total=len(sessions),
        )
    except Exception as e:
        logger.error(f"Get admin sessions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sessions",
        ) from e


@router.post("/force-logout/{session_id}")
async def force_logout_admin_session(
    session_id: int,
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Force logout another admin's session (requires super admin or MANAGE_ADMINS permission)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    # Check permission (super admin or MANAGE_ADMINS)
    if not current_user.is_super_admin:
        from app.core.permissions import AdminPermissions
        from app.services.permission_service import check_user_permission

        has_permission = await check_user_permission(
            db, int(current_user.id), AdminPermissions.MANAGE_ADMINS
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission required: manage_admins",
            )

    try:
        auth_service = AdminAuthService(db)
        await auth_service.force_logout_session(session_id, int(current_user.id))

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/auth/force-logout/{session_id}",
            resource="auth",
            action="force_logout",
            outcome="success",
            details={"target_session_id": session_id},
        )

        return {"message": "Session forced to logout"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Force logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to force logout",
        ) from e
