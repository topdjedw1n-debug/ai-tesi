"""Payment API endpoints"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentIntentResponse, PaymentResponse
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/create-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create Stripe payment intent"""
    try:
        service = PaymentService(db)
        result = await service.create_payment_intent(
            user_id=current_user.id,
            amount=payment_data.amount,
            currency=payment_data.currency,
            document_id=payment_data.document_id,
            discount_code=payment_data.discount_code
        )
        return PaymentIntentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Payment creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Payment failed") from e


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Stripe webhook endpoint
    - No auth (Stripe signs requests)
    - Must be public
    """
    if not stripe_signature:
        raise HTTPException(400, "Missing Stripe-Signature")

    try:
        payload = await request.body()
        service = PaymentService(db)
        payment = await service.handle_webhook(payload, stripe_signature)

        return {"status": "success", "payment_id": payment.id if payment else None}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.error(f"Webhook failed: {e}", exc_info=True)
        raise HTTPException(500, "Webhook processing failed") from e


@router.get("/history", response_model=list[PaymentResponse])
async def get_payment_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user payment history"""
    try:
        service = PaymentService(db)
        payments = await service.get_user_payments(current_user.id, limit)

        # ✅ Pydantic v2: use model_validate
        return [PaymentResponse.model_validate(p) for p in payments]
    except Exception as e:
        logger.error(f"History fetch failed: {e}", exc_info=True)
        raise HTTPException(500, "Failed to fetch payments") from e


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get single payment"""
    try:
        service = PaymentService(db)
        # Check ownership using helper function
        payment = await service.check_payment_ownership(payment_id, current_user.id)
        return PaymentResponse.model_validate(payment)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        logger.error(f"Payment fetch failed: {e}", exc_info=True)
        raise HTTPException(500, "Failed to fetch payment") from e

