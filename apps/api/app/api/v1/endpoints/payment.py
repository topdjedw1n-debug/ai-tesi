"""
Payment webhook endpoints with race condition protection
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.payment import (
    WebhookRequest,
    WebhookResponse,
    WebhookStatusResponse,
    PaymentJobResponse
)
from app.services.payment_service import PaymentService
from app.core.exceptions import ValidationError
from app.middleware.rate_limit import limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook", response_model=WebhookResponse)
@limiter.limit("100/minute")
async def process_webhook(
    request: Request,
    webhook_request: WebhookRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Process payment webhook with comprehensive race condition protection

    Protection mechanisms:
    - SELECT FOR UPDATE: Locks webhook/job rows during processing
    - Idempotency: Checks if webhook already processed before creating job
    - IntegrityError handling: Catches race conditions at database level
    - Duplicate logging: Logs all duplicate processing attempts

    This endpoint is designed to handle concurrent webhook deliveries safely.
    """
    try:
        payment_service = PaymentService(db)

        webhook_data = {
            "webhook_id": webhook_request.webhook_id,
            "user_id": webhook_request.user_id,
            "amount": webhook_request.amount,
            "currency": webhook_request.currency,
            "payment_method": webhook_request.payment_method
        }

        result = await payment_service.process_webhook(webhook_data)

        # Return 200 for both success and duplicate (idempotent behavior)
        return WebhookResponse(**result)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


@router.get("/webhook/{webhook_id}", response_model=WebhookStatusResponse)
async def get_webhook_status(
    webhook_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get webhook processing status"""
    try:
        payment_service = PaymentService(db)
        result = await payment_service.get_webhook_status(webhook_id)
        return WebhookStatusResponse(**result)
    except Exception as e:
        logger.error(f"Error getting webhook status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get webhook status"
        )


@router.get("/job/{webhook_id}", response_model=PaymentJobResponse)
async def get_payment_job(
    webhook_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get payment job by webhook ID"""
    try:
        payment_service = PaymentService(db)
        result = await payment_service.get_job_by_webhook(webhook_id)
        return PaymentJobResponse(**result)
    except Exception as e:
        logger.error(f"Error getting payment job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get payment job"
        )
