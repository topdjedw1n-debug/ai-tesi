"""Payment API endpoints"""
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentIntentResponse, PaymentResponse
from app.services.background_jobs import (  # noqa: F401 - legacy patch surface
    BackgroundJobService,
)
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/create-checkout")
async def create_checkout(
    document_id: int,
    pages: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Create Stripe checkout session for document generation

    CRITICAL: Payment must be completed BEFORE generation starts
    Price: Dynamic pricing from PricingService (configurable via admin panel)
    """
    try:
        service = PaymentService(db)
        result = await service.create_checkout_session(
            user_id=int(current_user.id), document_id=document_id, pages=pages
        )
        return {
            "checkout_url": result["checkout_url"],
            "session_id": result["session_id"],
            "amount": result["amount"],
            "currency": result["currency"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Checkout creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Checkout creation failed") from e


@router.post("/create-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentIntentResponse:
    """Create Stripe payment intent"""
    try:
        service = PaymentService(db)
        result = await service.create_payment_intent(
            user_id=int(current_user.id),
            amount=payment_data.amount,
            currency=payment_data.currency,
            document_id=payment_data.document_id,
            discount_code=payment_data.discount_code,
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
    background_tasks: BackgroundTasks,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Stripe webhook endpoint
    - No auth (Stripe signs requests)
    - Must be public
    - CRITICAL: Triggers document generation after payment completion
    """
    if not stripe_signature:
        raise HTTPException(400, "Missing Stripe-Signature")

    try:
        payload = await request.body()
        service = PaymentService(db)
        payment = await service.handle_webhook(payload, stripe_signature)

        # CRITICAL: Start document generation if payment completed with document
        if payment and payment.status == "completed" and payment.document_id:
            # Sales are disabled in the narrow MVP. A stray/legacy Stripe
            # webhook may record payment, but must never open a second start
            # path around the methodology and single-owner contract.
            if settings.MVP_FREE_GENERATION_ENABLED:
                return {"status": "payment_recorded", "generation": "manual_start"}

            # Import here to avoid circular imports
            from sqlalchemy import select
            from sqlalchemy.exc import IntegrityError

            from app.api.v1.endpoints.generate import (
                _delete_superseded_artifacts,
                _enforce_generation_gate,
                _invalidate_previous_generation_evidence,
            )
            from app.models.auth import User
            from app.models.document import AIGenerationJob, Document, ProductionCase
            from app.services.generation_contract import generation_contract_sha256

            owner = (
                await db.execute(
                    select(User)
                    .where(User.id == int(payment.user_id))
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if owner is None or owner.deletion_requested_at is not None:
                return {"status": "payment_recorded", "generation": "blocked"}

            document = (
                await db.execute(
                    select(Document)
                    .where(Document.id == payment.document_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if document is None:
                return {"status": "payment_recorded", "generation": "document_missing"}

            production_case = (
                await db.execute(
                    select(ProductionCase)
                    .where(ProductionCase.document_id == payment.document_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()

            prior_job = (
                await db.execute(
                    select(AIGenerationJob)
                    .where(
                        AIGenerationJob.document_id == payment.document_id,
                        AIGenerationJob.job_type == "full_document",
                    )
                    .order_by(AIGenerationJob.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if prior_job is not None:
                return {
                    "status": "payment_recorded",
                    "generation": "already_triggered",
                    "job_id": int(prior_job.id),
                }

            if production_case is None:
                production_case = ProductionCase(
                    document_id=int(document.id),
                    client_user_id=int(document.user_id),
                    citation_style=str(document.citation_style or "apa"),
                    generation_status="not_started",
                    payment_status="completed",
                )
                db.add(production_case)
                await db.flush()

            try:
                await _enforce_generation_gate(db, document, int(payment.user_id))
            except HTTPException as gate_error:
                document.status = "draft"
                await db.commit()
                logger.warning(
                    "Paid document %s remains blocked from generation: %s",
                    payment.document_id,
                    gate_error.detail,
                )
                return {"status": "payment_recorded", "generation": "blocked"}

            run_requirements = (
                str(production_case.requirements_text)
                if production_case.requirements_text
                else None
            )
            contract_sha256 = generation_contract_sha256(
                document,
                production_case,
                run_requirements,
            )
            superseded_paths = await _invalidate_previous_generation_evidence(
                db,
                int(payment.document_id),
                contract_sha256=contract_sha256,
            )

            try:
                job = AIGenerationJob(
                    user_id=payment.user_id,
                    document_id=payment.document_id,
                    job_type="full_document",
                    status="queued",
                    progress=0,
                    request_payload={
                        "additional_requirements": run_requirements,
                        "generation_contract_sha256": contract_sha256,
                        "superseded_artifact_paths": superseded_paths,
                    },
                    max_attempts=settings.GENERATION_JOB_MAX_ATTEMPTS,
                )
                db.add(job)
                await db.flush()
                document.status = "generating"
                await db.commit()
                await _delete_superseded_artifacts(superseded_paths)
                logger.info(
                    "Queued durable generation for document %s after payment %s, job_id=%s",
                    payment.document_id,
                    payment.id,
                    job.id,
                )

            except IntegrityError as e:
                # Handle race condition if it still occurs (e.g., unique constraint violation)
                await db.rollback()
                logger.warning(
                    f"⚠️ Race condition detected for document {payment.document_id}: {e}"
                )
                # Re-check for the winner after rollback.
                existing_job_result = await db.execute(
                    select(AIGenerationJob).where(
                        AIGenerationJob.document_id == payment.document_id,
                        AIGenerationJob.job_type == "full_document",
                        AIGenerationJob.status.in_(["queued", "running"]),
                    )
                )
                existing_job = existing_job_result.scalar_one_or_none()
                if existing_job:
                    logger.info(
                        f"⚠️ Found existing job {existing_job.id} after race condition, skipping duplicate"
                    )
                else:
                    # Re-raise if it's a different integrity error
                    logger.error(f"❌ Unexpected IntegrityError: {e}")
                    raise
            except Exception as e:
                await db.rollback()
                logger.error(f"❌ Error creating generation job: {e}", exc_info=True)
                raise

        return {"status": "success", "payment_id": payment.id if payment else None}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.error(f"Webhook failed: {e}", exc_info=True)
        raise HTTPException(500, "Webhook processing failed") from e


@router.get("/verify")
async def verify_payment(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Verify payment status after Stripe checkout redirect

    Used by frontend to check if payment was successful and get document_id
    """
    try:
        from sqlalchemy import select

        # Find payment by session_id
        result = await db.execute(
            select(Payment).where(Payment.stripe_session_id == session_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise HTTPException(404, "Payment not found for this session")

        # Verify ownership
        if payment.user_id != current_user.id:
            raise HTTPException(404, "Payment not found")

        # Return payment status and document_id
        return {
            "success": payment.status == "completed",
            "status": payment.status,
            "payment_id": payment.id,
            "document_id": payment.document_id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "created_at": payment.created_at.isoformat()
            if payment.created_at
            else None,
            "completed_at": payment.completed_at.isoformat()
            if payment.completed_at
            else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment verification failed: {e}", exc_info=True)
        raise HTTPException(500, "Failed to verify payment") from e


@router.get("/history", response_model=list[PaymentResponse])
async def get_payment_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentResponse]:
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
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
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
