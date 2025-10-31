"""
Authentication endpoints
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, RateLimitError, ValidationError
from app.core.logging import log_security_audit_event
from app.middleware.rate_limit import (
    check_auth_lockout,
    clear_auth_failures,
    get_user_id_or_ip,
    rate_limit,
    record_auth_failure,
)
from app.schemas.auth import (
    MagicLinkRequest,
    MagicLinkResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/magic-link", response_model=MagicLinkResponse)
@rate_limit("3/hour")  # Per-user/IP rate limit: 3/hr with progressive backoff
async def request_magic_link(
    http_request: Request,
    request: MagicLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request a magic link for passwordless authentication"""
    correlation_id = http_request.headers.get("X-Request-ID", "unknown")
    ip = http_request.client.host if http_request.client else "unknown"
    identifier = get_user_id_or_ip(http_request)

    # Check for auth lockout
    lockout = await check_auth_lockout(identifier)
    if lockout:
        log_security_audit_event(
            event_type="auth_attempt",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/magic-link",
            resource="auth",
            action="request_magic_link",
            outcome="denied",
            details={"reason": "account_locked", "lockout_minutes": int(lockout.total_seconds() / 60)}
        )
        raise RateLimitError(
            f"Account temporarily locked due to multiple failed authentication attempts. "
            f"Please try again in {int(lockout.total_seconds() / 60)} minutes."
        )

    try:
        auth_service = AuthService(db)
        result = await auth_service.send_magic_link(request.email)
        # Clear auth failures on successful request
        await clear_auth_failures(identifier)

        # Audit log successful magic link request
        log_security_audit_event(
            event_type="auth_attempt",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/magic-link",
            resource="auth",
            action="request_magic_link",
            outcome="success",
            details={"email": request.email}
        )

        return result
    except ValidationError as e:
        log_security_audit_event(
            event_type="auth_attempt",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/magic-link",
            resource="auth",
            action="request_magic_link",
            outcome="failure",
            details={"reason": "validation_error", "error": str(e)}
        )
        raise
    except Exception as e:
        log_security_audit_event(
            event_type="auth_attempt",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/magic-link",
            resource="auth",
            action="request_magic_link",
            outcome="failure",
            details={"reason": "internal_error", "error": str(e)}
        )
        raise AuthenticationError("Failed to send magic link")


@router.post("/verify-magic-link", response_model=TokenResponse)
@rate_limit("10/hour")  # Per-user/IP rate limit: 10/hr
async def verify_magic_link(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify magic link token and return access token"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    identifier = get_user_id_or_ip(request)

    # Check for auth lockout
    lockout = await check_auth_lockout(identifier)
    if lockout:
        log_security_audit_event(
            event_type="auth_attempt",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/verify-magic-link",
            resource="auth",
            action="verify_magic_link",
            outcome="denied",
            details={"reason": "account_locked", "lockout_minutes": int(lockout.total_seconds() / 60)}
        )
        raise RateLimitError(
            f"Account temporarily locked due to multiple failed authentication attempts. "
            f"Please try again in {int(lockout.total_seconds() / 60)} minutes."
        )

    try:
        auth_service = AuthService(db)
        result = await auth_service.verify_magic_link(token)
        # Clear auth failures on successful verification
        await clear_auth_failures(identifier)

        # Extract user_id from result if available
        user_id = None
        if isinstance(result, dict) and "user" in result:
            user_id = result["user"].get("id")

        # Audit log successful verification
        log_security_audit_event(
            event_type="auth_success",
            correlation_id=correlation_id,
            user_id=user_id,
            ip=ip,
            endpoint="/api/v1/auth/verify-magic-link",
            resource="auth",
            action="verify_magic_link",
            outcome="success"
        )

        return result
    except AuthenticationError as e:
        # Record failed auth attempt
        await record_auth_failure(identifier)

        log_security_audit_event(
            event_type="auth_failure",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/verify-magic-link",
            resource="auth",
            action="verify_magic_link",
            outcome="failure",
            details={"reason": str(e)}
        )

        raise
    except Exception as e:
        log_security_audit_event(
            event_type="auth_failure",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/verify-magic-link",
            resource="auth",
            action="verify_magic_link",
            outcome="failure",
            details={"reason": "internal_error", "error": str(e)}
        )
        raise AuthenticationError("Failed to verify magic link")


@router.post("/refresh", response_model=TokenResponse)
@rate_limit("20/hour")  # Per-user/IP rate limit: 20/hr
async def refresh_token(
    request: Request,
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    identifier = get_user_id_or_ip(request)

    # Check for auth lockout
    lockout = await check_auth_lockout(identifier)
    if lockout:
        log_security_audit_event(
            event_type="token_refresh",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/refresh",
            resource="auth",
            action="refresh_token",
            outcome="denied",
            details={"reason": "account_locked", "lockout_minutes": int(lockout.total_seconds() / 60)}
        )
        raise RateLimitError(
            f"Account temporarily locked due to multiple failed authentication attempts. "
            f"Please try again in {int(lockout.total_seconds() / 60)} minutes."
        )

    try:
        auth_service = AuthService(db)
        result = await auth_service.refresh_token(refresh_token)
        # Clear auth failures on successful refresh
        await clear_auth_failures(identifier)

        # Extract user_id from result if available
        user_id = None
        if isinstance(result, dict) and "user" in result:
            user_id = result["user"].get("id")

        # Audit log successful token refresh
        log_security_audit_event(
            event_type="token_refresh",
            correlation_id=correlation_id,
            user_id=user_id,
            ip=ip,
            endpoint="/api/v1/auth/refresh",
            resource="auth",
            action="refresh_token",
            outcome="success"
        )

        return result
    except AuthenticationError as e:
        # Record failed auth attempt
        await record_auth_failure(identifier)

        log_security_audit_event(
            event_type="token_refresh",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/refresh",
            resource="auth",
            action="refresh_token",
            outcome="failure",
            details={"reason": str(e)}
        )

        raise
    except Exception as e:
        log_security_audit_event(
            event_type="token_refresh",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/refresh",
            resource="auth",
            action="refresh_token",
            outcome="failure",
            details={"reason": "internal_error", "error": str(e)}
        )
        raise AuthenticationError("Failed to refresh token")


@router.post("/logout")
@rate_limit("5/minute")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Logout user and invalidate session"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            log_security_audit_event(
                event_type="logout",
                correlation_id=correlation_id,
                ip=ip,
                endpoint="/api/v1/auth/logout",
                resource="auth",
                action="logout",
                outcome="failure",
                details={"reason": "invalid_authorization_header"}
            )
            raise AuthenticationError("Invalid authorization header")

        token = auth_header.split(" ")[1]
        auth_service = AuthService(db)
        user_id = await auth_service.logout(token)

        # Audit log successful logout
        log_security_audit_event(
            event_type="logout",
            correlation_id=correlation_id,
            user_id=user_id,
            ip=ip,
            endpoint="/api/v1/auth/logout",
            resource="auth",
            action="logout",
            outcome="success"
        )

        return {"message": "Successfully logged out"}
    except AuthenticationError:
        raise
    except Exception as e:
        log_security_audit_event(
            event_type="logout",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/logout",
            resource="auth",
            action="logout",
            outcome="failure",
            details={"reason": "internal_error", "error": str(e)}
        )
        raise AuthenticationError("Failed to logout")


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current user information"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            log_security_audit_event(
                event_type="user_lookup",
                correlation_id=correlation_id,
                ip=ip,
                endpoint="/api/v1/auth/me",
                resource="user",
                action="read",
                outcome="failure",
                details={"reason": "invalid_authorization_header"}
            )
            raise AuthenticationError("Invalid authorization header")

        token = auth_header.split(" ")[1]
        auth_service = AuthService(db)
        user = await auth_service.get_current_user(token)

        # Audit log successful user lookup
        user_id = user.get("id") if isinstance(user, dict) else None
        log_security_audit_event(
            event_type="user_lookup",
            correlation_id=correlation_id,
            user_id=user_id,
            ip=ip,
            endpoint="/api/v1/auth/me",
            resource="user",
            action="read",
            outcome="success"
        )

        return user
    except AuthenticationError:
        raise
    except Exception as e:
        log_security_audit_event(
            event_type="user_lookup",
            correlation_id=correlation_id,
            ip=ip,
            endpoint="/api/v1/auth/me",
            resource="user",
            action="read",
            outcome="failure",
            details={"reason": "internal_error", "error": str(e)}
        )
        raise AuthenticationError("Failed to get user information")
