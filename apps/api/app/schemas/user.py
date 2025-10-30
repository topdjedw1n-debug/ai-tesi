"""
User schemas for API requests and responses
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


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
    preferred_language: Optional[str] = None
    timezone: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user API responses"""
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    total_tokens_used: int
    total_cost: int
    
    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile with additional information"""
    documents_count: int = 0
    recent_activity: Optional[datetime] = None
