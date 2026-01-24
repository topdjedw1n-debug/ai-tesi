"""
Pydantic schemas for refund operations
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RefundRequestCreate(BaseModel):
    """Schema for creating a refund request (user endpoint)"""

    payment_id: int = Field(description="ID of payment to refund")
    reason: str = Field(min_length=10, max_length=5000, description="Reason for refund")
    reason_category: str = Field(
        pattern="^(quality|not_satisfied|technical_issue|other)$",
        description="Category of refund reason",
    )
    screenshots: list[str] = Field(
        default_factory=list, description="Array of screenshot URLs"
    )

    @field_validator("reason_category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate reason category"""
        allowed = ["quality", "not_satisfied", "technical_issue", "other"]
        if v not in allowed:
            raise ValueError(f"reason_category must be one of: {allowed}")
        return v


class RefundReviewRequest(BaseModel):
    """Schema for admin refund review decision"""

    decision: str = Field(
        ..., pattern="^(approve|reject)$", description="Admin decision"
    )
    admin_comment: str = Field(
        ..., min_length=5, max_length=5000, description="Admin comment"
    )
    refund_amount: Decimal | None = Field(
        None, gt=0, description="Partial refund amount (if less than full amount)"
    )

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        """Validate decision"""
        if v not in ["approve", "reject"]:
            raise ValueError("decision must be 'approve' or 'reject'")
        return v


class RefundResponse(BaseModel):
    """Schema for refund request response"""

    id: int
    user_id: int
    payment_id: int
    status: str  # pending, approved, rejected
    reason: str
    reason_category: str | None
    submitted_at: datetime
    reviewed_at: datetime | None
    reviewed_by: int | None
    admin_comment: str | None
    refund_amount: Decimal | None
    ai_recommendation: str | None  # approve, reject, review
    risk_score: float | None  # 0-1

    model_config = {"from_attributes": True}


class RefundDetailsResponse(RefundResponse):
    """Detailed refund response with user and payment info"""

    user: dict[str, Any]  # User info
    payment: dict[str, Any]  # Payment info
    screenshots: list[str] | None

    model_config = {"from_attributes": True}


class RefundListResponse(BaseModel):
    """Response for refund list with pagination"""

    refunds: list[RefundResponse]
    total: int
    page: int
    per_page: int
    pages: int


class RefundStatsResponse(BaseModel):
    """Statistics about refunds"""

    total_requests: int
    pending: int
    approved: int
    rejected: int
    total_refunded_amount: Decimal
    average_processing_time_hours: float | None
    approval_rate: float  # percentage
