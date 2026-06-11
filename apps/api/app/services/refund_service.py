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
from app.models.document import DocumentProvenance, DocumentSource
from app.models.payment import Payment
from app.models.refund import RefundRequest

logger = logging.getLogger(__name__)

# Reason categories where the document's provenance ledger is direct evidence
# for or against the complaint ("low quality" style claims)
QUALITY_COMPLAINT_CATEGORIES = {"quality", "not_satisfied"}

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
            "pages": ((total or 0) + per_page - 1) // per_page if per_page > 0 else 1,
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
            refund_request.status = "approved"  # type: ignore[assignment]
            refund_request.reviewed_at = datetime.utcnow()  # type: ignore[assignment]
            refund_request.reviewed_by = admin_id  # type: ignore[assignment]
            refund_request.admin_comment = admin_comment  # type: ignore[assignment]
            refund_request.refund_amount = refund_amount_decimal  # type: ignore[assignment]

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

            # ROOT CAUSE: Email infrastructure not in MVP scope
            # TRACE: approve_refund() → [email notification layer missing]
            # IMPACT: Users don't get notified about refund approval (UX issue)
            # DECISION: Deferred to post-MVP (see MVP_PLAN.md #2)
            # TODO: Implement email_service.send_refund_approved(user, refund_request)
            #   Priority: 🟡 MEDIUM | Time: 3-4h | Blocked by: SMTP config in production
            #   See: docs/MVP_PLAN.md → "POST-RELEASE IMPROVEMENTS" → #2

            return refund_request

        except stripe.StripeError as e:
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
        refund_request.status = "rejected"  # type: ignore[assignment]
        refund_request.reviewed_at = datetime.utcnow()  # type: ignore[assignment]
        refund_request.reviewed_by = admin_id  # type: ignore[assignment]
        refund_request.admin_comment = admin_comment  # type: ignore[assignment]

        await self.db.commit()
        await self.db.refresh(refund_request)

        logger.info(f"Refund rejected: id={refund_id}")

        # ROOT CAUSE: Email infrastructure not in MVP scope
        # TRACE: reject_refund() → [email notification layer missing]
        # IMPACT: Users don't get notified about refund rejection (UX issue)
        # DECISION: Deferred to post-MVP (see MVP_PLAN.md #2)
        # TODO: Implement email_service.send_refund_rejected(user, refund_request, admin_comment)
        #   Priority: 🟡 MEDIUM | Time: 3-4h | Blocked by: SMTP config in production
        #   See: docs/MVP_PLAN.md → "POST-RELEASE IMPROVEMENTS" → #2

        return refund_request

    async def _get_document_quality_evidence(self, document_id: int) -> dict[str, Any]:
        """
        Summarize a document's provenance ledger for refund risk scoring.

        Aggregates source verification statuses (document_sources) and the
        quality_gate/citation_gate events (document_provenance) into a flat
        signal dict. Returns has_provenance=False when no ledger exists, so
        callers can skip the adjustment for legacy documents.
        """
        statuses_result = await self.db.execute(
            select(DocumentSource.verification_status).where(
                DocumentSource.document_id == document_id
            )
        )
        statuses = list(statuses_result.scalars().all())
        total_sources = len(statuses)
        verified_sources = sum(1 for s in statuses if s == "verified")
        not_found_sources = sum(1 for s in statuses if s == "not_found")

        events_result = await self.db.execute(
            select(DocumentProvenance)
            .where(
                DocumentProvenance.document_id == document_id,
                DocumentProvenance.event_type.in_(["quality_gate", "citation_gate"]),
            )
            .order_by(DocumentProvenance.created_at.asc(), DocumentProvenance.id.asc())
        )
        events = list(events_result.scalars().all())

        quality_events = [e for e in events if e.event_type == "quality_gate"]
        citation_events = [e for e in events if e.event_type == "citation_gate"]
        quality_gate_failures = sum(
            1 for e in quality_events if not (e.payload or {}).get("passed")
        )
        quality_gates_passed = bool(quality_events) and quality_gate_failures == 0
        # The last citation_gate event reflects the final verification outcome
        citation_gate_passed = bool(citation_events) and bool(
            (citation_events[-1].payload or {}).get("passed")
        )

        return {
            "has_provenance": bool(events) or total_sources > 0,
            "total_sources": total_sources,
            "verified_sources": verified_sources,
            "not_found_sources": not_found_sources,
            "all_sources_verified": total_sources > 0
            and verified_sources == total_sources,
            "quality_gates_passed": quality_gates_passed,
            "quality_gate_failures": quality_gate_failures,
            "citation_gate_passed": citation_gate_passed,
        }

    async def analyze_refund_risk(self, refund_id: int) -> dict[str, Any]:
        """
        Analyze refund request for risk (AI-powered, optional).

        For quality-type complaints the document's provenance ledger is used
        as evidence: fully verified sources + passed quality/citation gates
        contradict a "low quality" claim (risk up -> lean reject), while
        failed gates or not_found sources support it (risk down -> lean
        approve).

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

        # Provenance evidence (only meaningful for quality-type complaints
        # on payments linked to a generated document)
        provenance_signal: dict[str, Any] | None = None
        if (
            payment
            and payment.document_id
            and refund_request.reason_category in QUALITY_COMPLAINT_CATEGORIES
        ):
            provenance_signal = await self._get_document_quality_evidence(
                int(payment.document_id)
            )
            if provenance_signal["has_provenance"]:
                if (
                    provenance_signal["all_sources_verified"]
                    and provenance_signal["quality_gates_passed"]
                    and provenance_signal["citation_gate_passed"]
                ):
                    # Ledger contradicts the claim: 100% verified sources and
                    # all gates passed -> complaint less likely substantiated
                    risk_score += 0.3
                elif (
                    provenance_signal["not_found_sources"] > 0
                    or provenance_signal["quality_gate_failures"] > 0
                ):
                    # Ledger supports the claim -> refund likely justified
                    risk_score -= 0.2

        risk_score = min(max(risk_score, 0.0), 1.0)

        # Determine recommendation
        if risk_score < 0.3:
            recommendation = "approve"
        elif risk_score < 0.6:
            recommendation = "review"
        else:
            recommendation = "reject"

        # Update refund request with AI analysis
        refund_request.risk_score = risk_score  # type: ignore[assignment]
        refund_request.ai_recommendation = recommendation  # type: ignore[assignment]
        await self.db.commit()

        return {
            "risk_score": risk_score,
            "recommendation": recommendation,
            "factors": {
                "previous_refunds": previous_refunds,
                "payment_amount": float(payment_amount),
                "reason_category": refund_request.reason_category,
                "provenance": provenance_signal,
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
