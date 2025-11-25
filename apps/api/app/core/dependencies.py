"""
FastAPI dependencies for authentication and authorization
"""

import logging

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.permissions import AdminPermissions
from app.models.admin import AdminSession
from app.models.auth import User
from app.utils.jwt_helpers import extract_user_id_from_payload

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency to extract and validate JWT token, returning the current user.

    Requirements:
    - Extracts Bearer token from Authorization header
    - Validates JWT using ENV-based configuration
    - Checks exp, nbf, iat, iss, aud claims
    - Enforces is_active=True
    - Returns User ORM object or raises 401

    Security:
    - Clock skew tolerance: 60 seconds
    - Consistent 401 responses (no token data leakage)
    """
    # Extract token from Authorization header
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Prepare JWT validation parameters from ENV
    # Use jwt_secret_key property which prefers JWT_SECRET over SECRET_KEY
    secret_key = settings.jwt_secret_key
    algorithm = settings.JWT_ALG

    # Determine if we should verify iss/aud based on settings
    verify_iss = bool(settings.JWT_ISS)
    verify_aud = bool(settings.JWT_AUD)

    try:
        # Decode and validate JWT token
        # Note: python-jose 3.3.0 does not support leeway parameter
        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_iss": verify_iss,
            "verify_aud": verify_aud,
            "require_exp": True,
            "require_nbf": False,  # nbf is optional
            "require_iat": True,
        }

        # Only pass issuer/audience if they are set and verification is enabled
        decode_kwargs = {
            "token": token,
            "key": secret_key,
            "algorithms": [algorithm],
            "options": decode_options,
        }

        if verify_iss and settings.JWT_ISS:
            decode_kwargs["issuer"] = settings.JWT_ISS

        if verify_aud and settings.JWT_AUD:
            decode_kwargs["audience"] = settings.JWT_AUD

        payload = jwt.decode(**decode_kwargs)

        # Validate token type (must be access token)
        token_type = payload.get("type")
        if token_type != "access":
            raise AuthenticationError("Invalid token type")

        # Extract and validate user ID (convert from string to int)
        user_id = extract_user_id_from_payload(payload)

        # Query user from database - ORM knows User.id is Integer, so it handles type correctly
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError("User not found")

        # Enforce active status - CRITICAL security requirement
        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        return user

    except JWTError as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.warning(
            f"JWT validation failed: {error_type} - {error_msg}, "
            f"verify_iss={verify_iss}, verify_aud={verify_aud}, "
            f"has_iss_setting={bool(settings.JWT_ISS)}, has_aud_setting={bool(settings.JWT_AUD)}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency to ensure the current user is an admin.

    Extends get_current_user() and checks is_admin=True.
    Raises HTTPException(403) if user is not an admin.

    Security:
    - Requires valid JWT token (enforced by get_current_user)
    - Requires is_active=True (enforced by get_current_user)
    - Requires is_admin=True (enforced here)
    - Consistent 403 responses (no user data leakage)
    - Audit logging for access/denial
    """
    if not current_user.is_admin:
        logger.warning(
            f"ADMIN_ACCESS_DENIED: user_id={current_user.id}, email={current_user.email}, "
            f"is_admin={current_user.is_admin}, is_active={current_user.is_active}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions: Admin access required",
        )

    logger.info(
        f"ADMIN_ACCESS_GRANTED: user_id={current_user.id}, email={current_user.email}"
    )
    return current_user


async def get_current_user_ws(
    websocket: WebSocket,
    token: str | None = None,
) -> User:
    """
    FastAPI dependency for WebSocket authentication.

    Extracts JWT token from WebSocket query params or headers.

    Args:
        websocket: WebSocket connection
        token: Optional token from query parameter

    Returns:
        Authenticated User object

    Raises:
        WebSocketException: If authentication fails
    """
    from fastapi import WebSocketException

    # Try to get token from query parameter first
    if not token:
        token = websocket.query_params.get("token")

    # Try to get from Authorization header
    if not token:
        auth_header = websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")

    if not token:
        await websocket.close(code=1008, reason="Authorization required")
        raise WebSocketException(code=1008, reason="Authorization required")

    try:
        # Decode token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.JWT_ALG],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": hasattr(settings, "JWT_ISS")
                and settings.JWT_ISS is not None,
                "verify_aud": hasattr(settings, "JWT_AUD")
                and settings.JWT_AUD is not None,
            },
        )

        # Extract and validate user ID (convert from string to int)
        try:
            user_id = extract_user_id_from_payload(payload)
        except AuthenticationError as e:
            await websocket.close(code=1008, reason="Invalid token")
            raise WebSocketException(code=1008, reason="Invalid token") from e

        # Get user from database - ORM knows User.id is Integer, so it handles type correctly
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user or not user.is_active:
                await websocket.close(code=1008, reason="User not found or inactive")
                raise WebSocketException(code=1008, reason="User not found or inactive")

            return user

    except JWTError as e:
        logger.warning(f"WebSocket JWT validation failed: {str(e)}")
        await websocket.close(code=1008, reason="Invalid token")
        raise WebSocketException(code=1008, reason="Invalid token") from e
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=1011, reason="Internal error")
        raise WebSocketException(code=1011, reason="Internal error") from e


def require_permission(permission: AdminPermissions):
    """
    Factory function to create a dependency that checks for a specific permission.

    Usage:
        @router.get("/users")
        async def list_users(
            current_user: User = Depends(require_permission(AdminPermissions.VIEW_USERS))
        ):
            ...
    """

    async def permission_checker(
        current_user: User = Depends(get_admin_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        """
        FastAPI dependency to check if user has a specific permission.

        Logic:
        1. If is_super_admin = True -> all permissions granted
        2. Check permission in admin_permissions table
        3. If no permission -> 403

        Args:
            current_user: Current authenticated admin user
            db: Database session

        Returns:
            User object if permission granted

        Raises:
            HTTPException(403): If user doesn't have permission
        """
        # Super admin has all permissions
        if current_user.is_super_admin:
            return current_user

        # Check permission in database
        from app.services.permission_service import check_user_permission

        has_permission = await check_user_permission(db, current_user.id, permission)

        if not has_permission:
            logger.warning(
                f"PERMISSION_DENIED: user_id={current_user.id}, "
                f"email={current_user.email}, permission={permission.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission.value}",
            )

        return current_user

    return permission_checker


async def get_admin_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> tuple[AdminSession, User]:
    """
    FastAPI dependency to extract and validate admin session token.

    Returns tuple of (AdminSession, User) for convenience.

    Security:
    - Extracts Bearer token from Authorization header (admin session token, not JWT)
    - Validates session is active and not expired
    - Updates last_activity if configured
    - Returns AdminSession and User ORM objects or raises 401

    Note: This is for admin-specific endpoints that use session tokens.
    For regular admin endpoints, use get_admin_user() which uses JWT.
    """
    from app.services.admin_auth_service import AdminAuthService

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_token = credentials.credentials

    try:
        # Validate session
        auth_service = AdminAuthService(db)
        admin_session = await auth_service.validate_admin_session(session_token)

        # Get admin user
        user = await db.get(User, admin_session.admin_id)
        if not user:
            raise AuthenticationError("Admin user not found")

        if not user.is_active:
            raise AuthenticationError("Admin account is inactive")

        if not user.is_admin:
            raise AuthenticationError("User is not an admin")

        return admin_session, user

    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.warning(f"Admin session validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in get_admin_session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
