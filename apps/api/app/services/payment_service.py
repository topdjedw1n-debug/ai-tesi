"""Payment service for Stripe integration"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import stripe
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.payment import Payment
from app.models.user import User
from app.services.pricing_service import PricingService

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

    async def check_payment_ownership(self, payment_id: int, user_id: int) -> Payment:
        """
        Check if payment exists and belongs to user.
        Returns Payment object or raises ValueError.

        This function ensures IDOR protection by returning 404
        instead of 403 to avoid revealing existence of payments.
        """
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
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
        discount_code: str | None = None,
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
            result = await self.db.execute(select(User).where(User.id == user_id))
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
                    "discount_code": discount_code or "",
                },
                # CRITICAL: Idempotency key prevents duplicates
                idempotency_key=f"intent_{user_id}_{document_id or 'nodoc'}_{int(datetime.utcnow().timestamp() * 1000)}",
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
                discount_amount=discount_amount,
            )

            self.db.add(payment)
            await self.db.commit()
            await self.db.refresh(payment)

            logger.info(f"✅ Payment intent created: {intent.id}")

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": float(final_amount),
                "currency": currency,
            }

        except stripe.error.StripeError as e:  # type: ignore[attr-defined]
            logger.error(f"❌ Stripe error: {e}")
            raise ValueError(f"Payment creation failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await self.db.rollback()
            raise

    async def create_checkout_session(
        self,
        user_id: int,
        document_id: int,
        pages: int,
    ) -> dict[str, Any]:
        """
        Create Stripe checkout session for document generation

        CRITICAL: Payment must be completed BEFORE generation starts

        Returns:
            dict with checkout_url
        """
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe not configured")

        try:
            # 1. Get user and document
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_id} not found")

            doc_result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = doc_result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")
            if document.user_id != user_id:
                raise ValueError("Document ownership mismatch")

            # 2. Calculate price using dynamic pricing service
            pricing_service = PricingService(self.db)
            total_amount = await pricing_service.calculate_amount(pages)
            amount_cents = int(total_amount * 100)  # Convert EUR to cents

            # 3. Get/create Stripe customer
            customer_id = await self._get_or_create_customer(user)

            # 4. Get frontend URL
            frontend_url = settings.FRONTEND_URL

            # 5. Create Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "eur",
                            "product_data": {
                                "name": f"Документ: {document.title}",
                                "description": f"Генерація документа на {pages} сторінок",
                            },
                            "unit_amount": amount_cents,  # Already in cents
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=f"{frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{frontend_url}/payment/cancel",
                customer=customer_id,
                metadata={
                    "user_id": str(user_id),
                    "document_id": str(document_id),
                    "pages": str(pages),
                    "title": document.title[:100],  # Limit metadata length
                },
                # Idempotency key for duplicate prevention
                idempotency_key=f"checkout_{user_id}_{document_id}_{int(datetime.utcnow().timestamp() * 1000)}",
            )

            # 6. Save payment record with checkout session
            payment = Payment(
                user_id=user_id,
                document_id=document_id,
                stripe_session_id=session.id,
                stripe_customer_id=customer_id,
                amount=Decimal(amount_cents) / 100,  # Convert cents to EUR
                currency="EUR",
                status="pending",
            )

            self.db.add(payment)

            # 7. Update document status to payment_pending
            document.status = "payment_pending"  # type: ignore[assignment]

            await self.db.commit()
            await self.db.refresh(payment)

            logger.info(
                f"✅ Checkout session created: {session.id} for document {document_id}"
            )

            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "amount": float(payment.amount),
                "currency": "EUR",
            }

        except stripe.error.StripeError as e:  # type: ignore[attr-defined]
            logger.error(f"❌ Stripe error: {e}")
            await self.db.rollback()
            raise ValueError(f"Checkout creation failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"❌ Error creating checkout: {e}")
            await self.db.rollback()
            raise

    async def _get_or_create_customer(self, user: User) -> str:
        """Get or create Stripe customer"""
        if user.stripe_customer_id:
            try:
                stripe.Customer.retrieve(str(user.stripe_customer_id))
                return str(user.stripe_customer_id)
            except stripe.error.InvalidRequestError:  # type: ignore[attr-defined]
                logger.warning(f"Customer {user.stripe_customer_id} not found")

        # Create new customer
        customer = stripe.Customer.create(
            email=str(user.email),
            name=str(user.full_name or user.email),
            metadata={"user_id": str(user.id)},
        )

        user.stripe_customer_id = customer.id  # type: ignore[assignment]
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

            event_type = event["type"]
            logger.info(f"📨 Webhook: {event_type}")

            # Route to handler
            if event_type == "checkout.session.completed":
                # CRITICAL: Handle checkout completion - trigger generation
                return await self._handle_checkout_completed(event)
            elif event_type == "payment_intent.succeeded":
                return await self._handle_payment_success(event)
            elif event_type == "payment_intent.payment_failed":
                return await self._handle_payment_failed(event)
            elif event_type == "payment_intent.canceled":
                return await self._handle_payment_canceled(event)
            else:
                logger.warning(f"⚠️ Unhandled event: {event_type}")
                return None

        except stripe.error.SignatureVerificationError as e:  # type: ignore[attr-defined]
            logger.error(f"❌ Invalid signature: {e}")
            raise ValueError("Invalid webhook signature") from e
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")
            raise

    async def _handle_checkout_completed(self, event: dict) -> Payment:
        """
        Handle checkout.session.completed event

        CRITICAL: This triggers document generation AFTER payment is confirmed
        """
        session = event["data"]["object"]
        session_id = session["id"]
        payment_intent_id = session.get(
            "payment_intent"
        )  # May be None if not yet created

        # Find payment by session_id
        result = await self.db.execute(
            select(Payment).where(Payment.stripe_session_id == session_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            logger.error(f"❌ Payment not found for session: {session_id}")
            raise ValueError(f"Payment not found for session: {session_id}")

        # ✅ IDEMPOTENCY: Skip if already completed
        if payment.status == "completed":
            logger.warning(f"⚠️ Payment {payment.id} already completed (idempotent)")
            return payment

        # Update payment with payment intent ID and status
        payment.status = "completed"  # type: ignore[assignment]
        payment.completed_at = datetime.utcnow()  # type: ignore[assignment]
        if payment_intent_id:
            payment.stripe_payment_intent_id = payment_intent_id

        # Update document status to generating
        if payment.document_id:
            doc_result = await self.db.execute(
                select(Document).where(Document.id == payment.document_id)
            )
            document = doc_result.scalar_one_or_none()
            if document:
                # Mark document as ready for generation
                document.status = "generating"  # type: ignore[assignment]
                logger.info(
                    f"✅ Document {document.id} ready for generation after payment"
                )

        await self.db.commit()
        await self.db.refresh(payment)

        logger.info(
            f"✅ Checkout completed: payment {payment.id}, document {payment.document_id}"
        )

        # NOTE: Document generation will be triggered by the webhook endpoint
        # which has access to BackgroundTasks
        return payment

    async def _handle_payment_success(self, event: dict) -> Payment:
        """Handle payment success with idempotency check"""
        intent = event["data"]["object"]
        payment_intent_id = intent["id"]

        # Find payment
        result = await self.db.execute(
            select(Payment).where(Payment.stripe_payment_intent_id == payment_intent_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise ValueError(f"Payment not found: {payment_intent_id}")

        # ✅ IDEMPOTENCY: Skip if already completed
        if payment.status == "completed":
            logger.warning(f"⚠️ Payment {payment.id} already completed (idempotent)")
            return payment

        # Update payment
        payment.status = "completed"  # type: ignore[assignment]
        payment.completed_at = datetime.utcnow()  # type: ignore[assignment]
        payment.payment_method = intent.get("payment_method_types", [None])[0]

        # Update document status if exists
        if payment.document_id:
            doc_result = await self.db.execute(
                select(Document).where(Document.id == payment.document_id)
            )
            document = doc_result.scalar_one_or_none()
            if document and document.status == "payment_pending":
                document.status = "generating"  # type: ignore[assignment]

        await self.db.commit()
        await self.db.refresh(payment)

        logger.info(f"✅ Payment {payment.id} completed")
        return payment

    async def _handle_payment_failed(self, event: dict) -> Payment:
        """Handle payment failure"""
        intent = event["data"]["object"]
        payment_intent_id = intent["id"]

        result = await self.db.execute(
            select(Payment).where(Payment.stripe_payment_intent_id == payment_intent_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise ValueError(f"Payment not found: {payment_intent_id}")

        payment.status = "failed"  # type: ignore[assignment]
        payment.failure_reason = intent.get("last_payment_error", {}).get(
            "message", "Unknown"
        )

        if payment.document_id:
            doc_result = await self.db.execute(
                select(Document).where(Document.id == payment.document_id)
            )
            document = doc_result.scalar_one_or_none()
            if document:
                document.status = "payment_failed"  # type: ignore[assignment]

        await self.db.commit()
        await self.db.refresh(payment)

        logger.warning(f"⚠️ Payment {payment.id} failed")
        return payment

    async def _handle_payment_canceled(self, event: dict) -> Payment | None:
        """Handle payment cancelation"""
        intent = event["data"]["object"]
        payment_intent_id = intent["id"]

        result = await self.db.execute(
            select(Payment).where(Payment.stripe_payment_intent_id == payment_intent_id)
        )
        payment = result.scalar_one_or_none()

        if payment:
            payment.status = "canceled"  # type: ignore[assignment]
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

    async def check_payment_timeouts(self) -> dict[str, Any]:
        """
        Check and expire pending payments older than 10 minutes

        This should be called periodically (e.g., every 10 minutes via cron or scheduler)
        Returns dict with expired_count and deleted_documents_count
        """
        try:
            # Find payments pending for more than 10 minutes
            expired_threshold = datetime.utcnow() - timedelta(minutes=10)

            result = await self.db.execute(
                select(Payment).where(
                    Payment.status == "pending", Payment.created_at < expired_threshold
                )
            )
            expired_payments = list(result.scalars().all())

            expired_count = 0
            deleted_documents = 0

            for payment in expired_payments:
                # Mark payment as expired
                payment.status = "expired"  # type: ignore[assignment]
                expired_count += 1

                # Delete draft document if exists
                if payment.document_id:
                    doc_result = await self.db.execute(
                        select(Document).where(Document.id == payment.document_id)
                    )
                    document = doc_result.scalar_one_or_none()
                    if document and document.status == "payment_pending":
                        # Delete document
                        await self.db.execute(
                            delete(Document).where(Document.id == payment.document_id)
                        )
                        deleted_documents += 1
                        logger.info(
                            f"🗑️ Deleted expired draft document {document.id} for payment {payment.id}"
                        )

            if expired_count > 0:
                await self.db.commit()
                logger.info(
                    f"⏰ Expired {expired_count} pending payments, deleted {deleted_documents} draft documents"
                )

            return {
                "expired_count": expired_count,
                "deleted_documents_count": deleted_documents,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Error checking payment timeouts: {e}", exc_info=True)
            await self.db.rollback()
            return {
                "expired_count": 0,
                "deleted_documents_count": 0,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
