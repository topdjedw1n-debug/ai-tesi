"""Payment service for Stripe integration"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.payment import Payment
from app.models.user import User

logger = logging.getLogger(__name__)

# Initialize Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY
else:
    logger.warning("⚠️ Stripe not configured")


class PaymentService:
    """Service for Stripe payment operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_payment_ownership(
        self, payment_id: int, user_id: int
    ) -> Payment:
        """
        Check if payment exists and belongs to user.
        Returns Payment object or raises ValueError.
        
        This function ensures IDOR protection by returning 404
        instead of 403 to avoid revealing existence of payments.
        """
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment or payment.user_id != user_id:
            raise ValueError("Payment not found")
        
        return payment

    async def create_payment_intent(
        self,
        user_id: int,
        amount: Decimal,
        currency: str = "EUR",
        document_id: int | None = None,
        discount_code: str | None = None
    ) -> dict[str, Any]:
        """
        Create Stripe payment intent

        Returns:
            dict with client_secret, payment_intent_id, amount, currency
        """
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe not configured")

        try:
            # 1. Get user
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")

            # 2. Apply discount (TODO: implement logic)
            final_amount = amount
            discount_amount = Decimal(0)

            # 3. Get/create Stripe customer
            customer_id = await self._get_or_create_customer(user)

            # 4. Create Payment Intent with idempotency key
            intent = stripe.PaymentIntent.create(
                amount=int(final_amount * 100),  # Convert EUR to cents
                currency=currency.lower(),
                customer=customer_id,
                metadata={
                    "user_id": str(user_id),
                    "user_email": user.email,
                    "document_id": str(document_id) if document_id else "",
                    "discount_code": discount_code or ""
                },
                # CRITICAL: Idempotency key prevents duplicates
                idempotency_key=f"intent_{user_id}_{document_id or 'nodoc'}_{int(datetime.utcnow().timestamp() * 1000)}"
            )

            # 5. Save payment record
            payment = Payment(
                user_id=user_id,
                document_id=document_id,
                stripe_payment_intent_id=intent.id,
                stripe_customer_id=customer_id,
                amount=final_amount,
                currency=currency,
                status="pending",
                discount_code=discount_code,
                discount_amount=discount_amount
            )

            self.db.add(payment)
            await self.db.commit()
            await self.db.refresh(payment)

            logger.info(f"✅ Payment intent created: {intent.id}")

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": float(final_amount),
                "currency": currency
            }

        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe error: {e}")
            raise ValueError(f"Payment creation failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await self.db.rollback()
            raise

    async def _get_or_create_customer(self, user: User) -> str:
        """Get or create Stripe customer"""
        if user.stripe_customer_id:
            try:
                stripe.Customer.retrieve(user.stripe_customer_id)
                return user.stripe_customer_id
            except stripe.error.InvalidRequestError:
                logger.warning(f"Customer {user.stripe_customer_id} not found")

        # Create new customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or user.email,
            metadata={"user_id": str(user.id)}
        )

        user.stripe_customer_id = customer.id
        await self.db.commit()

        logger.info(f"✅ Created Stripe customer: {customer.id}")
        return customer.id

    async def handle_webhook(self, payload: bytes, signature: str) -> Payment | None:
        """
        Handle Stripe webhook with idempotency check

        IMPORTANT: Implements idempotency (see CRITICAL_BUGFIXES_v2_2.md Bug #4)
        """
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ValueError("Webhook secret not configured")

        try:
            # Verify signature
            event = stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )

            event_type = event['type']
            logger.info(f"📨 Webhook: {event_type}")

            # Route to handler
            if event_type == 'payment_intent.succeeded':
                return await self._handle_payment_success(event)
            elif event_type == 'payment_intent.payment_failed':
                return await self._handle_payment_failed(event)
            elif event_type == 'payment_intent.canceled':
                return await self._handle_payment_canceled(event)
            else:
                logger.warning(f"⚠️ Unhandled event: {event_type}")
                return None

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"❌ Invalid signature: {e}")
            raise ValueError("Invalid webhook signature") from e
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")
            raise

    async def _handle_payment_success(self, event: dict) -> Payment:
        """Handle payment success with idempotency check"""
        intent = event['data']['object']
        payment_intent_id = intent['id']

        # Find payment
        result = await self.db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == payment_intent_id
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise ValueError(f"Payment not found: {payment_intent_id}")

        # ✅ IDEMPOTENCY: Skip if already completed
        if payment.status == "completed":
            logger.warning(f"⚠️ Payment {payment.id} already completed (idempotent)")
            return payment

        # Update payment
        payment.status = "completed"
        payment.completed_at = datetime.utcnow()
        payment.payment_method = intent.get('payment_method_types', [None])[0]

        # Update document status if exists
        if payment.document_id:
            doc_result = await self.db.execute(
                select(Document).where(Document.id == payment.document_id)
            )
            document = doc_result.scalar_one_or_none()
            if document and document.status == "payment_pending":
                document.status = "generating"

        await self.db.commit()
        await self.db.refresh(payment)

        logger.info(f"✅ Payment {payment.id} completed")
        return payment

    async def _handle_payment_failed(self, event: dict) -> Payment:
        """Handle payment failure"""
        intent = event['data']['object']
        payment_intent_id = intent['id']

        result = await self.db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == payment_intent_id
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise ValueError(f"Payment not found: {payment_intent_id}")

        payment.status = "failed"
        payment.failure_reason = intent.get('last_payment_error', {}).get('message', 'Unknown')

        if payment.document_id:
            doc_result = await self.db.execute(
                select(Document).where(Document.id == payment.document_id)
            )
            document = doc_result.scalar_one_or_none()
            if document:
                document.status = "payment_failed"

        await self.db.commit()
        await self.db.refresh(payment)

        logger.warning(f"⚠️ Payment {payment.id} failed")
        return payment

    async def _handle_payment_canceled(self, event: dict) -> Payment | None:
        """Handle payment cancelation"""
        intent = event['data']['object']
        payment_intent_id = intent['id']

        result = await self.db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == payment_intent_id
            )
        )
        payment = result.scalar_one_or_none()

        if payment:
            payment.status = "canceled"
            await self.db.commit()
            await self.db.refresh(payment)
            logger.info(f"🚫 Payment {payment.id} canceled")

        return payment

    async def get_user_payments(self, user_id: int, limit: int = 50) -> list[Payment]:
        """Get payment history"""
        result = await self.db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

