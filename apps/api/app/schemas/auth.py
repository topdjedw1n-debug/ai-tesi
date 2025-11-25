"""
Authentication schemas for API requests and responses
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    """Schema for magic link authentication request"""

    email: EmailStr


class MagicLinkResponse(BaseModel):
    """Schema for magic link response"""

    message: str
    email: str
    expires_in: int
    expires_in_minutes: int
    magic_link: str


class MagicLinkVerify(BaseModel):
    """Schema for magic link verification"""

    token: str


class TokenResponse(BaseModel):
    """Schema for authentication token response"""

    access_token: str
    refresh_token: str | None = (
        None  # Optional for refresh endpoint (doesn't return new refresh token)
    )
    token_type: str = "bearer"
    expires_in: int
    user: dict


class LoginResponse(BaseModel):
    """Schema for login response"""

    success: bool
    message: str
    user: dict | None = None
    token: str | None = None


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request"""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Schema for logout request"""

    token: str


class SessionInfo(BaseModel):
    """Schema for session information"""

    session_id: str
    created_at: datetime
    last_activity: datetime
    ip_address: str | None
    user_agent: str | None
    is_active: bool
