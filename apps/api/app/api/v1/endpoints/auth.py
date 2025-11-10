"""
Authentication endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.auth import (
    MagicLinkRequest,
    MagicLinkResponse,
    TokenResponse,
    UserResponse,
    RefreshTokenRequest
)
from app.services.auth_service import AuthService
from app.core.exceptions import AuthenticationError, ValidationError
from app.middleware.rate_limit import limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/magic-link", response_model=MagicLinkResponse)
@limiter.limit("5/minute")
async def request_magic_link(
    request: Request,
    magic_link_request: MagicLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request a magic link for passwordless authentication"""
    try:
        auth_service = AuthService(db)
        result = await auth_service.send_magic_link(magic_link_request.email)
        return result
    except ValidationError as e:
        logger.warning(f"Validation error in magic-link: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except AuthenticationError as e:
        logger.warning(f"Authentication error in magic-link: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in magic-link endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send magic link: {str(e)}"
        )


@router.post("/verify-magic-link", response_model=TokenResponse)
@limiter.limit("5/minute")
async def verify_magic_link(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify magic link token and return access token"""
    try:
        auth_service = AuthService(db)
        result = await auth_service.verify_magic_link(token)
        return result
    except AuthenticationError as e:
        logger.warning(f"Authentication error in verify-magic-link: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in verify-magic-link endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify magic link: {str(e)}"
        )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("5/minute")
async def refresh_token(
    request: Request,
    refresh_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        auth_service = AuthService(db)
        result = await auth_service.refresh_token(refresh_request.refresh_token)
        return result
    except AuthenticationError as e:
        logger.warning(f"Authentication error in refresh-token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in refresh-token endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        )


@router.post("/logout")
@limiter.limit("5/minute")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Logout user and invalidate session"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )

        token = auth_header.split(" ")[1]
        auth_service = AuthService(db)
        await auth_service.logout(token)

        return {"message": "Successfully logged out"}
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.warning(f"Authentication error in logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in logout endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to logout: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current user information"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        auth_service = AuthService(db)
        user = await auth_service.get_current_user(token)
        return user
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.warning(f"Authentication error in get-current-user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get-current-user endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user information: {str(e)}"
        )
