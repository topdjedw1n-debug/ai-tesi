"""
User schemas for API requests and responses
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    preferred_language: str = "en"
    timezone: str = "UTC"


class UserCreate(UserBase):
    """Schema for creating a new user"""
    pass


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    preferred_language: str | None = None
    timezone: str | None = None


class UserResponse(UserBase):
    """Schema for user API responses"""
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime | None
    last_login: datetime | None
    total_tokens_used: int
    total_cost: int

    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile with additional information"""
    documents_count: int = 0
    recent_activity: datetime | None = None
