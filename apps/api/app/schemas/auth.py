"""
Authentication schemas for API requests and responses
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class MagicLinkRequest(BaseModel):
    """Schema for magic link authentication request"""
    email: EmailStr


class MagicLinkResponse(BaseModel):
    """Schema for magic link response"""
    message: str
    email: str
    expires_in: int
    magic_link: Optional[str] = None  # Only for development


class MagicLinkVerify(BaseModel):
    """Schema for magic link verification"""
    token: str


class TokenResponse(BaseModel):
    """Schema for authentication token response"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: dict


class LoginResponse(BaseModel):
    """Schema for login response"""
    success: bool
    message: str
    user: Optional[dict] = None
    token: Optional[str] = None


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
    full_name: Optional[str]
    is_verified: bool
    is_admin: bool
    preferred_language: str
    timezone: str
    total_tokens_used: int
    total_documents_created: int
    created_at: str
    last_login: Optional[str]


class SessionInfo(BaseModel):
    """Schema for session information"""
    session_id: str
    created_at: datetime
    last_activity: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    is_active: bool
