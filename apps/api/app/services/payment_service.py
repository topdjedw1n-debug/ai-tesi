"""
Payment webhook service with race condition protection
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.payment import PaymentWebhook, PaymentJob
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for processing payment webhooks with race condition protection"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process payment webhook with comprehensive race condition protection

        Protection mechanisms:
        1. SELECT FOR UPDATE - locks the webhook row for concurrent updates
        2. Idempotency check - prevents duplicate job creation
        3. IntegrityError handling - catches race conditions at DB level
        4. Duplicate logging - logs all duplicate attempts

        Args:
            webhook_data: Webhook payload containing webhook_id, user_id, amount, etc.

        Returns:
            Dict with processing result
        """
        webhook_id = webhook_data.get("webhook_id")
        user_id = webhook_data.get("user_id")
        amount = webhook_data.get("amount")

        if not webhook_id or not user_id or not amount:
            raise ValidationError("Missing required fields: webhook_id, user_id, amount")

        try:
            # Step 1: Idempotency check - check if webhook already exists
            logger.info(f"Processing webhook {webhook_id} for user {user_id}")

            existing_webhook = await self.db.execute(
                select(PaymentWebhook)
                .where(PaymentWebhook.webhook_id == webhook_id)
                .with_for_update()  # SELECT FOR UPDATE - locks row
            )
            webhook = existing_webhook.scalar_one_or_none()

            if webhook and webhook.is_processed:
                # Duplicate webhook - already processed
                logger.warning(
                    f"Duplicate webhook attempt detected: {webhook_id}. "
                    f"Already processed at {webhook.processed_at}"
                )
                return {
                    "status": "duplicate",
                    "message": "Webhook already processed",
                    "webhook_id": webhook_id,
                    "processed_at": webhook.processed_at.isoformat() if webhook.processed_at else None
                }

            # Step 2: Create or update webhook record
            if not webhook:
                # Convert Decimal to float for JSON serialization
                payload_copy = webhook_data.copy()
                if isinstance(payload_copy.get("amount"), Decimal):
                    payload_copy["amount"] = float(payload_copy["amount"])

                webhook = PaymentWebhook(
                    webhook_id=webhook_id,
                    user_id=user_id,
                    amount=Decimal(str(amount)),
                    currency=webhook_data.get("currency", "USD"),
                    payment_method=webhook_data.get("payment_method", "unknown"),
                    raw_payload=json.dumps(payload_copy),
                    status="pending"
                )
                self.db.add(webhook)
                await self.db.flush()

            # Step 3: Idempotency check for PaymentJob - verify no job exists yet
            existing_job = await self.db.execute(
                select(PaymentJob)
                .where(PaymentJob.webhook_id == webhook_id)
                .with_for_update()  # SELECT FOR UPDATE - locks row
            )
            job = existing_job.scalar_one_or_none()

            if job:
                # Job already exists - this is a duplicate
                logger.warning(
                    f"Duplicate job creation attempt blocked: {webhook_id}. "
                    f"Job {job.id} already exists (status: {job.status})"
                )
                webhook.status = "duplicate"
                await self.db.commit()

                return {
                    "status": "duplicate",
                    "message": "Payment job already exists",
                    "webhook_id": webhook_id,
                    "job_id": job.id
                }

            # Step 4: Create payment job (protected by unique constraint)
            try:
                job = PaymentJob(
                    webhook_id=webhook_id,
                    user_id=user_id,
                    amount=Decimal(str(amount)),
                    status="pending"
                )
                self.db.add(job)
                await self.db.flush()

                # Mark webhook as processed
                webhook.is_processed = True
                webhook.processed_at = datetime.utcnow()
                webhook.status = "processed"

                await self.db.commit()

                logger.info(
                    f"Payment job created successfully: webhook_id={webhook_id}, "
                    f"job_id={job.id}, user_id={user_id}, amount={amount}"
                )

                return {
                    "status": "success",
                    "message": "Payment job created",
                    "webhook_id": webhook_id,
                    "job_id": job.id,
                    "user_id": user_id,
                    "amount": float(amount)
                }

            except IntegrityError as e:
                # Step 5: IntegrityError handling - catch race conditions
                await self.db.rollback()

                logger.warning(
                    f"IntegrityError caught - race condition detected for webhook {webhook_id}. "
                    f"Another request created the job first. Error: {str(e)}"
                )

                # Query existing job
                existing_job_result = await self.db.execute(
                    select(PaymentJob).where(PaymentJob.webhook_id == webhook_id)
                )
                existing_job = existing_job_result.scalar_one_or_none()

                return {
                    "status": "duplicate",
                    "message": "Payment job already created by concurrent request",
                    "webhook_id": webhook_id,
                    "job_id": existing_job.id if existing_job else None,
                    "race_condition": True
                }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error processing webhook {webhook_id}: {str(e)}", exc_info=True)

            # Update webhook status to failed
            try:
                if webhook:
                    webhook.status = "failed"
                    webhook.error_message = str(e)
                    await self.db.commit()
            except:
                pass

            raise

    async def get_webhook_status(self, webhook_id: str) -> Dict[str, Any]:
        """Get webhook processing status"""
        result = await self.db.execute(
            select(PaymentWebhook).where(PaymentWebhook.webhook_id == webhook_id)
        )
        webhook = result.scalar_one_or_none()

        if not webhook:
            return {"status": "not_found", "webhook_id": webhook_id}

        return {
            "webhook_id": webhook_id,
            "status": webhook.status,
            "is_processed": webhook.is_processed,
            "processed_at": webhook.processed_at.isoformat() if webhook.processed_at else None,
            "created_at": webhook.created_at.isoformat() if webhook.created_at else None
        }

    async def get_job_by_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Get payment job by webhook ID"""
        result = await self.db.execute(
            select(PaymentJob).where(PaymentJob.webhook_id == webhook_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return {"status": "not_found", "webhook_id": webhook_id}

        return {
            "job_id": job.id,
            "webhook_id": job.webhook_id,
            "user_id": job.user_id,
            "amount": float(job.amount),
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None
        }
