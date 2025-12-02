"""
Simple admin authentication for testing (password-based)
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.auth import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter()


class AdminSimpleLoginRequest(BaseModel):
    """Simple admin login with email + password"""

    email: EmailStr
    password: str


class AdminSimpleLoginResponse(BaseModel):
    """Response with tokens"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/admin/simple-login", response_model=AdminSimpleLoginResponse)
async def admin_simple_login(
    request: Request,
    login_data: AdminSimpleLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Simple admin login for testing (no magic link required)
    
    For testing only! Uses plain password comparison.
    In production, use proper password hashing.
    """
    ip = request.client.host if request.client else "unknown"
    
    # Get admin user
    result = await db.execute(
        select(User).where(
            User.email == login_data.email,
            User.is_admin == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"Admin login failed: user not found or not admin - {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or not an admin",
        )
    
    # Verify password (bcrypt only - no fallback)
    if not user.password_hash:
        logger.error(f"Admin login failed: password_hash not set - {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin password not configured. Use scripts/set-admin-password.py",
        )
    
    # Production: use bcrypt verification
    if not AuthService.verify_password(login_data.password, user.password_hash):
        logger.warning(f"Admin login failed: invalid password - {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create token (using existing function from security.py)
    access_token = create_access_token(user.id)
    
    # For refresh token, create a long-lived access token (simplified for testing)
    # In production, implement proper refresh token logic
    refresh_token = access_token  # Simplified for MVP testing
    
    logger.info(f"Admin login successful: {user.email} from {ip}")
    
    return AdminSimpleLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_admin": user.is_admin,
            "is_super_admin": user.is_super_admin,
        },
    )


@router.get("/admin/check")
async def admin_check():
    """Health check for admin auth"""
    return {
        "status": "ok",
        "admin_auth": "available",
        "method": "simple-login",
    }
