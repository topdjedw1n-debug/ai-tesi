"""
FastAPI dependencies for authentication and authorization
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.models.auth import User

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
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

    try:
        # Prepare JWT validation parameters from ENV
        # Use JWT_SECRET if available, fallback to SECRET_KEY for backwards compatibility
        secret_key = settings.JWT_SECRET if hasattr(settings, 'JWT_SECRET') and settings.JWT_SECRET else settings.SECRET_KEY
        algorithm = settings.JWT_ALG if hasattr(settings, 'JWT_ALG') else "HS256"

        # Decode and validate JWT token
        # Set leeway for clock skew (60 seconds)
        leeway = timedelta(seconds=60)
        datetime.utcnow()

        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_iss": hasattr(settings, 'JWT_ISS') and settings.JWT_ISS is not None,
            "verify_aud": hasattr(settings, 'JWT_AUD') and settings.JWT_AUD is not None,
            "require_exp": True,
            "require_nbf": False,  # nbf is optional
            "require_iat": True,
        }

        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options=decode_options,
            issuer=settings.JWT_ISS if hasattr(settings, 'JWT_ISS') and settings.JWT_ISS else None,
            audience=settings.JWT_AUD if hasattr(settings, 'JWT_AUD') and settings.JWT_AUD else None,
            leeway=leeway,
        )

        # Extract user ID from token (subject claim)
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token: missing subject claim")

        # Validate token type (must be access token)
        token_type = payload.get("type")
        if token_type != "access":
            raise AuthenticationError("Invalid token type")

        # Validate token type is integer or convertable
        try:
            user_id = int(user_id)
        except (ValueError, TypeError) as e:
            raise AuthenticationError("Invalid token: invalid user ID") from e

        # Query user from database
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError("User not found")

        # Enforce active status - CRITICAL security requirement
        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        return user

    except JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
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


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
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

