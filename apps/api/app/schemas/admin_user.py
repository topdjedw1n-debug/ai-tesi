"""
Pydantic schemas for admin user management operations
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BlockUserRequest(BaseModel):
    """Schema for blocking a user"""

    reason: str = Field(
        ..., min_length=5, max_length=500, description="Reason for blocking"
    )


class UserDetailsResponse(BaseModel):
    """Detailed user information for admin view"""

    id: int
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    is_admin: bool
    is_super_admin: bool
    preferred_language: str
    timezone: str
    total_tokens_used: int
    total_documents_created: int
    total_cost: int  # in cents
    stripe_customer_id: str | None
    created_at: datetime
    updated_at: datetime | None
    last_login: datetime | None

    model_config = {"from_attributes": True}


class UserWithStatsResponse(UserDetailsResponse):
    """User details with additional statistics"""

    documents_count: int = 0
    payments_count: int = 0
    total_paid: Decimal = Decimal("0")
    last_payment_at: datetime | None = None
    last_document_at: datetime | None = None


class BulkUserActionRequest(BaseModel):
    """Schema for bulk user operations"""

    user_ids: list[int] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., pattern="^(block|unblock|delete)$")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action"""
        if v not in ["block", "unblock", "delete"]:
            raise ValueError("action must be one of: block, unblock, delete")
        return v


class BulkUserActionResult(BaseModel):
    """Result of bulk user operation"""

    action: str
    total_requested: int
    successful: int
    failed: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class MakeAdminRequest(BaseModel):
    """Schema for making user admin or revoking admin rights"""

    is_admin: bool = Field(..., description="True to make admin, False to revoke")
    is_super_admin: bool | None = Field(
        None,
        description="True to make super admin (optional, requires super admin permission)",
    )


class UserListResponse(BaseModel):
    """Response for user list with pagination"""

    users: list[UserDetailsResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class SendEmailRequest(BaseModel):
    """Schema for sending email to user"""

    subject: str = Field(..., min_length=1, max_length=500, description="Email subject")
    message: str = Field(
        ..., min_length=1, description="Email message (HTML or plain text)"
    )


class SendEmailResponse(BaseModel):
    """Response for sending email"""

    user_id: int
    email: str
    subject: str
    sent: bool
    sent_at: str
