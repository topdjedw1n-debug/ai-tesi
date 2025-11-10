"""
Payment webhook schemas
"""

from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal


class WebhookRequest(BaseModel):
    """Payment webhook request"""
    webhook_id: str = Field(..., min_length=1, max_length=255, description="Unique webhook identifier (idempotency key)")
    user_id: int = Field(..., gt=0, description="User ID")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_method: Optional[str] = Field(default=None, max_length=50)


class WebhookResponse(BaseModel):
    """Payment webhook response"""
    status: str
    message: str
    webhook_id: str
    job_id: Optional[int] = None
    user_id: Optional[int] = None
    amount: Optional[float] = None
    processed_at: Optional[str] = None
    race_condition: Optional[bool] = None


class WebhookStatusResponse(BaseModel):
    """Webhook status response"""
    webhook_id: str
    status: str
    is_processed: Optional[bool] = None
    processed_at: Optional[str] = None
    created_at: Optional[str] = None


class PaymentJobResponse(BaseModel):
    """Payment job response"""
    job_id: Optional[int] = None
    webhook_id: str
    user_id: Optional[int] = None
    amount: Optional[float] = None
    status: str
    created_at: Optional[str] = None
