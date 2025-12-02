"""
Refund service for managing refund requests and processing refunds
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import stripe
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.payment import Payment
from app.models.refund import RefundRequest

logger = logging.getLogger(__name__)

# Initialize Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY
else:
    logger.warning("⚠️ Stripe not configured")


class RefundService:
    """Service for refund operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_refund_request(
        self,
        user_id: int,
        payment_id: int,
        reason: str,
        reason_category: str,
        screenshots: list[str] | None = None,
    ) -> RefundRequest:
        """
        Create a refund request for a user.

        Args:
            user_id: User ID creating the request
            payment_id: Payment ID to refund
            reason: Reason for refund
            reason_category: Category of reason
            screenshots: Optional list of screenshot URLs

        Returns:
            RefundRequest object

        Raises:
            ValueError: If payment not found, already refunded, or invalid
        """
        # Verify payment exists and belongs to user
        result = await self.db.execute(
            select(Payment).where(
                and_(
                    Payment.id == payment_id,
                    Payment.user_id == user_id,
                )
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise ValueError("Payment not found")

        # Check if payment is completed
        if payment.status != "completed":
            raise ValueError("Can only refund completed payments")

        # Check if already refunded
        if payment.status == "refunded":
            raise ValueError("Payment already refunded")

        # Check if refund request already exists
        existing_result = await self.db.execute(
            select(RefundRequest).where(
                and_(
                    RefundRequest.payment_id == payment_id,
                    RefundRequest.status == "pending",
                )
            )
        )
        if existing_result.scalar_one_or_none():
            raise ValueError("Refund request already exists for this payment")

        # Create refund request
        refund_request = RefundRequest(
            user_id=user_id,
            payment_id=payment_id,
            reason=reason,
            reason_category=reason_category,
            screenshots=screenshots or [],
            status="pending",
        )

        self.db.add(refund_request)
        await self.db.commit()
        await self.db.refresh(refund_request)

        logger.info(
            f"Refund request created: id={refund_request.id}, payment_id={payment_id}"
        )
        return refund_request

    async def get_refund_request(self, refund_id: int) -> RefundRequest:
        """
        Get refund request by ID with relationships.

        Args:
            refund_id: Refund request ID

        Returns:
            RefundRequest object

        Raises:
            ValueError: If refund request not found
        """
        result = await self.db.execute(
            select(RefundRequest)
            .options(
                selectinload(RefundRequest.user),
                selectinload(RefundRequest.payment),
                selectinload(RefundRequest.reviewer),
            )
            .where(RefundRequest.id == refund_id)
        )
        refund_request = result.scalar_one_or_none()

        if not refund_request:
            raise ValueError("Refund request not found")

        return refund_request

    async def get_refunds_list(
        self,
        status: str | None = None,
        user_id: int | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """
        Get list of refund requests with filters and pagination.

        Args:
            status: Filter by status (pending, approved, rejected)
            user_id: Filter by user ID
            page: Page number
            per_page: Items per page

        Returns:
            Dictionary with refunds list and pagination info
        """
        # Build query
        query = select(RefundRequest)

        if status:
            query = query.where(RefundRequest.status == status)
        if user_id:
            query = query.where(RefundRequest.user_id == user_id)

        # Get total count
        count_query = select(func.count()).select_from(
            query.subquery() if status or user_id else RefundRequest
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * per_page
        query = (
            query.order_by(RefundRequest.submitted_at.desc())
            .offset(offset)
            .limit(per_page)
        )

        result = await self.db.execute(query)
        refunds = result.scalars().all()

        return {
            "refunds": list(refunds),
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if per_page > 0 else 1,
        }

    async def approve_refund(
        self,
        refund_id: int,
        admin_id: int,
        admin_comment: str,
        refund_amount: Decimal | None = None,
    ) -> RefundRequest:
        """
        Approve a refund request and process Stripe refund.

        Args:
            refund_id: Refund request ID
            admin_id: Admin user ID approving the refund
            admin_comment: Admin comment
            refund_amount: Partial refund amount (None = full refund)

        Returns:
            Updated RefundRequest object

        Raises:
            ValueError: If refund request not found, already processed, or Stripe error
        """
        refund_request = await self.get_refund_request(refund_id)

        if refund_request.status != "pending":
            raise ValueError("Refund request already processed")

        # Get payment
        payment = refund_request.payment
        if not payment:
            raise ValueError("Payment not found")

        # Determine refund amount
        refund_amount_decimal = refund_amount if refund_amount else payment.amount

        # Validate refund amount
        if refund_amount_decimal > payment.amount:
            raise ValueError("Refund amount cannot exceed payment amount")

        try:
            # Process Stripe refund
            if not payment.stripe_payment_intent_id:
                raise ValueError("Payment does not have Stripe payment intent ID")

            # Create refund in Stripe
            stripe_refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent_id,
                amount=int(refund_amount_decimal * 100),  # Convert to cents
                reason="requested_by_customer",
                metadata={
                    "refund_request_id": str(refund_id),
                    "admin_id": str(admin_id),
                    "refund_category": refund_request.reason_category or "other",
                },
            )

            # Update refund request
            refund_request.status = "approved"
            refund_request.reviewed_at = datetime.utcnow()
            refund_request.reviewed_by = admin_id
            refund_request.admin_comment = admin_comment
            refund_request.refund_amount = refund_amount_decimal

            # Update payment status
            if refund_amount_decimal == payment.amount:
                payment.status = "refunded"
            else:
                # Partial refund - keep as completed but note the refund
                payment.status = "completed"  # Stripe handles partial refunds

            await self.db.commit()
            await self.db.refresh(refund_request)

            logger.info(
                f"Refund approved: id={refund_id}, amount={refund_amount_decimal}, "
                f"stripe_refund_id={stripe_refund.id}"
            )

            # TODO: Send email notification to user

            return refund_request

        except stripe.error.StripeError as e:
            await self.db.rollback()
            logger.error(f"Stripe refund error: {e}")
            raise ValueError(f"Stripe refund failed: {str(e)}") from e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Refund approval error: {e}")
            raise

    async def reject_refund(
        self,
        refund_id: int,
        admin_id: int,
        admin_comment: str,
    ) -> RefundRequest:
        """
        Reject a refund request.

        Args:
            refund_id: Refund request ID
            admin_id: Admin user ID rejecting the refund
            admin_comment: Admin comment explaining rejection

        Returns:
            Updated RefundRequest object

        Raises:
            ValueError: If refund request not found or already processed
        """
        refund_request = await self.get_refund_request(refund_id)

        if refund_request.status != "pending":
            raise ValueError("Refund request already processed")

        # Update refund request
        refund_request.status = "rejected"
        refund_request.reviewed_at = datetime.utcnow()
        refund_request.reviewed_by = admin_id
        refund_request.admin_comment = admin_comment

        await self.db.commit()
        await self.db.refresh(refund_request)

        logger.info(f"Refund rejected: id={refund_id}, admin_id={admin_id}")

        # TODO: Send email notification to user

        return refund_request

    async def analyze_refund_risk(self, refund_id: int) -> dict[str, Any]:
        """
        Analyze refund request for risk (AI-powered, optional).

        Args:
            refund_id: Refund request ID

        Returns:
            Dictionary with risk_score and recommendation

        Raises:
            ValueError: If refund request not found
        """
        refund_request = await self.get_refund_request(refund_id)

        # Get user history
        user = refund_request.user
        if not user:
            raise ValueError("User not found")

        # Count previous refunds
        previous_refunds_result = await self.db.execute(
            select(func.count(RefundRequest.id)).where(
                and_(
                    RefundRequest.user_id == user.id,
                    RefundRequest.status == "approved",
                    RefundRequest.id != refund_id,
                )
            )
        )
        previous_refunds = previous_refunds_result.scalar() or 0

        # Get payment amount
        payment = refund_request.payment
        payment_amount = payment.amount if payment else Decimal(0)

        # Simple risk calculation (can be enhanced with ML)
        risk_score = 0.0
        if previous_refunds > 2:
            risk_score += 0.3
        if payment_amount > Decimal("100"):
            risk_score += 0.2
        if refund_request.reason_category == "technical_issue":
            risk_score += 0.1

        # Determine recommendation
        if risk_score < 0.3:
            recommendation = "approve"
        elif risk_score < 0.6:
            recommendation = "review"
        else:
            recommendation = "reject"

        # Update refund request with AI analysis
        refund_request.risk_score = risk_score
        refund_request.ai_recommendation = recommendation
        await self.db.commit()

        return {
            "risk_score": risk_score,
            "recommendation": recommendation,
            "factors": {
                "previous_refunds": previous_refunds,
                "payment_amount": float(payment_amount),
                "reason_category": refund_request.reason_category,
            },
        }

    async def get_refund_stats(self) -> dict[str, Any]:
        """
        Get statistics about refunds.

        Returns:
            Dictionary with refund statistics
        """
        # Total requests
        total_result = await self.db.execute(select(func.count(RefundRequest.id)))
        total_requests = total_result.scalar() or 0

        # By status
        pending_result = await self.db.execute(
            select(func.count(RefundRequest.id)).where(
                RefundRequest.status == "pending"
            )
        )
        pending = pending_result.scalar() or 0

        approved_result = await self.db.execute(
            select(func.count(RefundRequest.id)).where(
                RefundRequest.status == "approved"
            )
        )
        approved = approved_result.scalar() or 0

        rejected_result = await self.db.execute(
            select(func.count(RefundRequest.id)).where(
                RefundRequest.status == "rejected"
            )
        )
        rejected = rejected_result.scalar() or 0

        # Total refunded amount
        total_refunded_result = await self.db.execute(
            select(func.sum(RefundRequest.refund_amount)).where(
                RefundRequest.status == "approved"
            )
        )
        total_refunded = total_refunded_result.scalar() or Decimal(0)

        # Average processing time
        avg_time_result = await self.db.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch", RefundRequest.reviewed_at - RefundRequest.submitted_at
                    )
                    / 3600
                )
            ).where(
                and_(
                    RefundRequest.status.in_(["approved", "rejected"]),
                    RefundRequest.reviewed_at.isnot(None),
                )
            )
        )
        avg_processing_time = avg_time_result.scalar()
        avg_processing_time_hours = (
            float(avg_processing_time) if avg_processing_time else None
        )

        # Approval rate
        approval_rate = (approved / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "total_requests": total_requests,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_refunded_amount": total_refunded,
            "average_processing_time_hours": avg_processing_time_hours,
            "approval_rate": round(approval_rate, 2),
        }

