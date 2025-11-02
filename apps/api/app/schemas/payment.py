"""Pydantic schemas for payment operations (Pydantic v2)"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class PaymentCreate(BaseModel):
    """Request to create payment intent"""

    amount: Decimal = Field(..., gt=0, le=10000, description="Amount in EUR")
    currency: str = Field(default="EUR", pattern="^[A-Z]{3}$")
    document_id: int | None = None
    discount_code: str | None = Field(None, max_length=50)

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount has max 2 decimal places"""
        if v.as_tuple().exponent < -2:
            raise ValueError('Amount cannot have more than 2 decimal places')
        return v


class PaymentIntentResponse(BaseModel):
    """Stripe payment intent response for frontend"""

    client_secret: str = Field(..., description="Stripe client secret for Elements")
    payment_intent_id: str
    amount: Decimal
    currency: str


class PaymentResponse(BaseModel):
    """Payment record response"""

    id: int
    user_id: int
    document_id: int | None
    stripe_payment_intent_id: str
    amount: Decimal
    currency: str
    status: str
    discount_code: str | None
    discount_amount: Decimal
    created_at: datetime
    completed_at: datetime | None

    # Pydantic v2 config
    model_config = {"from_attributes": True}


class WebhookEvent(BaseModel):
    """Stripe webhook event (for validation)"""

    type: str
    data: dict

