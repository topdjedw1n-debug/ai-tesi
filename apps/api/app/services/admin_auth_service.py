"""
Admin authentication service for managing admin sessions
"""

import logging
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.admin import AdminSession
from app.models.auth import User

logger = logging.getLogger(__name__)


class AdminAuthService:
    """Service for managing admin authentication and sessions"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_admin_session(
        self,
        user_id: int,
        request: Request,
    ) -> AdminSession:
        """
        Create a new admin session.

        Args:
            user_id: Admin user ID
            request: FastAPI request object (for IP and user agent)

        Returns:
            AdminSession object

        Raises:
            HTTPException: If user is not admin or max sessions reached
        """
        # Verify user is admin
        user = await self.db.get(User, user_id)
        if not user or not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create admin sessions",
            )

        # Check max concurrent sessions
        active_sessions = await self.get_active_sessions(user_id)
        if len(active_sessions) >= settings.ADMIN_MAX_CONCURRENT_SESSIONS:
            # Force logout oldest session
            oldest = sorted(active_sessions, key=lambda s: s.last_activity)[0]
            await self.logout_admin_session(oldest.id)

        # Generate session token
        session_token = secrets.token_urlsafe(64)

        # Calculate expiration
        timeout_minutes = settings.ADMIN_SESSION_TIMEOUT_MINUTES
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)

        # Create session
        admin_session = AdminSession(
            admin_id=user_id,
            session_token=session_token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            is_active=True,
            forced_logout=False,
            expires_at=expires_at,
        )

        self.db.add(admin_session)
        await self.db.commit()
        await self.db.refresh(admin_session)

        logger.info(
            f"Admin session created: user_id={user_id}, session_id={admin_session.id}"
        )
        return admin_session

    async def validate_admin_session(
        self,
        session_token: str,
        request: Request | None = None,
    ) -> AdminSession:
        """
        Validate an admin session and update last_activity if configured.

        Args:
            session_token: Session token to validate
            request: Optional request object for IP tracking

        Returns:
            AdminSession object if valid

        Raises:
            HTTPException: If session is invalid, expired, or forced logout
        """
        # Find session
        result = await self.db.execute(
            select(AdminSession).where(AdminSession.session_token == session_token)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session token",
            )

        # Check if active
        if not session.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session is not active",
            )

        # Check if forced logout
        if session.forced_logout:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session was forced to logout",
            )

        # Check expiration
        now = datetime.utcnow()
        if session.expires_at < now:
            session.is_active = False
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
            )

        # Update last_activity if configured
        if settings.ADMIN_SESSION_UPDATE_ON_ACTIVITY:
            session.last_activity = datetime.utcnow()
            await self.db.commit()

        return session

    async def logout_admin_session(self, session_id: int) -> None:
        """
        Logout a specific admin session.

        Args:
            session_id: Session ID to logout
        """
        session = await self.db.get(AdminSession, session_id)
        if session:
            session.is_active = False
            await self.db.commit()
            logger.info(f"Admin session logged out: session_id={session_id}")

    async def logout_all_admin_sessions(self, user_id: int) -> int:
        """
        Logout all sessions for an admin user.

        Args:
            user_id: Admin user ID

        Returns:
            Number of sessions logged out
        """
        result = await self.db.execute(
            select(AdminSession).where(
                and_(
                    AdminSession.admin_id == user_id,
                    AdminSession.is_active == True,  # noqa: E712
                )
            )
        )
        sessions = result.scalars().all()

        count = 0
        for session in sessions:
            session.is_active = False
            count += 1

        await self.db.commit()
        logger.info(f"Logged out {count} sessions for admin user_id={user_id}")
        return count

    async def get_active_sessions(self, user_id: int) -> list[AdminSession]:
        """
        Get all active sessions for an admin user.

        Args:
            user_id: Admin user ID

        Returns:
            List of active AdminSession objects
        """
        now = datetime.utcnow()

        result = await self.db.execute(
            select(AdminSession).where(
                and_(
                    AdminSession.admin_id == user_id,
                    AdminSession.is_active == True,  # noqa: E712
                    AdminSession.expires_at > now,
                    AdminSession.forced_logout == False,  # noqa: E712
                )
            )
        )

        sessions = result.scalars().all()
        return list(sessions)

    async def force_logout_session(self, session_id: int, forced_by: int) -> None:
        """
        Force logout a specific session (by another admin).

        Args:
            session_id: Session ID to force logout
            forced_by: Admin user ID who is forcing the logout
        """
        session = await self.db.get(AdminSession, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify forced_by is admin
        admin = await self.db.get(User, forced_by)
        if not admin or not admin.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can force logout",
            )

        session.is_active = False
        session.forced_logout = True
        await self.db.commit()

        logger.warning(
            f"Admin session forced logout: session_id={session_id}, "
            f"forced_by={forced_by}, session_admin_id={session.admin_id}"
        )
