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
    magic_link: str | None = None  # Only for development


class MagicLinkVerify(BaseModel):
    """Schema for magic link verification"""
    token: str


class TokenResponse(BaseModel):
    """Schema for authentication token response"""
    access_token: str
    refresh_token: str | None = None
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


class UserResponse(BaseModel):
    """Schema for user information response"""
    id: int
    email: str
    full_name: str | None
    is_verified: bool
    is_admin: bool
    preferred_language: str
    timezone: str
    total_tokens_used: int
    total_documents_created: int
    created_at: str
    last_login: str | None


class SessionInfo(BaseModel):
    """Schema for session information"""
    session_id: str
    created_at: datetime
    last_activity: datetime
    ip_address: str | None
    user_agent: str | None
    is_active: bool
