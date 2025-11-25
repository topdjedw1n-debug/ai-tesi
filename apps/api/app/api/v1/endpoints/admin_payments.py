"""
Admin endpoints for payment management
"""

import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.exceptions import APIException
from app.core.logging import log_security_audit_event
from app.core.permissions import AdminPermissions
from app.models.auth import User
from app.models.payment import Payment
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def list_payments(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(pending|completed|failed|refunded)$"),
    user_id: int | None = Query(None),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_PAYMENTS)),
    db: AsyncSession = Depends(get_db),
):
    """List all payments with filters (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/payments"

    try:
        # Build query
        query = select(Payment)

        # Apply filters
        if status:
            query = query.where(Payment.status == status)
        if user_id:
            query = query.where(Payment.user_id == user_id)
        if start_date:
            query = query.where(Payment.created_at >= start_date)
        if end_date:
            query = query.where(Payment.created_at <= end_date)
        if min_amount:
            query = query.where(Payment.amount >= min_amount)
        if max_amount:
            query = query.where(Payment.amount <= max_amount)

        # Get total count
        count_query = select(func.count(Payment.id))
        if status:
            count_query = count_query.where(Payment.status == status)
        if user_id:
            count_query = count_query.where(Payment.user_id == user_id)
        if start_date:
            count_query = count_query.where(Payment.created_at >= start_date)
        if end_date:
            count_query = count_query.where(Payment.created_at <= end_date)
        if min_amount:
            count_query = count_query.where(Payment.amount >= min_amount)
        if max_amount:
            count_query = count_query.where(Payment.amount <= max_amount)

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page).order_by(Payment.created_at.desc())

        result = await db.execute(query)
        payments = result.scalars().all()

        # Convert to dict format
        payments_list = []
        for payment in payments:
            payments_list.append(
                {
                    "id": payment.id,
                    "user_id": payment.user_id,
                    "document_id": payment.document_id,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "status": payment.status,
                    "stripe_payment_intent_id": payment.stripe_payment_intent_id,
                    "stripe_session_id": payment.stripe_session_id,
                    "payment_method": payment.payment_method,
                    "created_at": payment.created_at.isoformat()
                    if payment.created_at
                    else None,
                    "completed_at": payment.completed_at.isoformat()
                    if payment.completed_at
                    else None,
                }
            )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
            ip=ip,
            endpoint=endpoint,
            resource="payments",
            action="list",
            outcome="success",
            details={
                "page": page,
                "per_page": per_page,
                "filters": {
                    "status": status,
                    "user_id": user_id,
                },
            },
        )

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="view_payments",
            target_type="payment",
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        return {
            "payments": payments_list,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }
    except Exception as e:
        logger.error(f"Error listing payments: {e}")
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
            ip=ip,
            endpoint=endpoint,
            resource="payments",
            action="list",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to list payments",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/{payment_id}")
async def get_payment_details(
    payment_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_PAYMENTS)),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed payment information (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get payment
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()

        if not payment:
            raise APIException(
                detail="Payment not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        # Get user info
        from app.models.user import User as UserModel

        user_result = await db.execute(
            select(UserModel).where(UserModel.id == payment.user_id)
        )
        user = user_result.scalar_one_or_none()

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="view_payment_details",
            target_type="payment",
            target_id=payment_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
            ip=ip,
            endpoint=f"/api/v1/admin/payments/{payment_id}",
            resource="payment",
            action="view_details",
            outcome="success",
        )

        return {
            "id": payment.id,
            "user_id": payment.user_id,
            "user_email": user.email if user else None,
            "document_id": payment.document_id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "stripe_payment_intent_id": payment.stripe_payment_intent_id,
            "stripe_session_id": payment.stripe_session_id,
            "stripe_customer_id": payment.stripe_customer_id,
            "payment_method": payment.payment_method,
            "discount_code": payment.discount_code,
            "discount_amount": float(payment.discount_amount)
            if payment.discount_amount
            else None,
            "failure_reason": payment.failure_reason,
            "created_at": payment.created_at.isoformat()
            if payment.created_at
            else None,
            "completed_at": payment.completed_at.isoformat()
            if payment.completed_at
            else None,
        }
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment details: {e}")
        raise APIException(
            detail="Failed to get payment details",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/{payment_id}/stripe-link")
async def get_stripe_dashboard_link(
    payment_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_PAYMENTS)),
    db: AsyncSession = Depends(get_db),
):
    """Get Stripe dashboard link for a payment (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get payment
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()

        if not payment:
            raise APIException(
                detail="Payment not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="view_stripe_link",
            target_type="payment",
            target_id=payment_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        # Generate Stripe dashboard link
        stripe_link = None
        if payment.stripe_payment_intent_id:
            # Stripe dashboard link format: https://dashboard.stripe.com/payments/{payment_intent_id}
            stripe_link = f"https://dashboard.stripe.com/payments/{payment.stripe_payment_intent_id}"
        elif payment.stripe_session_id:
            # Checkout session link
            stripe_link = f"https://dashboard.stripe.com/checkout/sessions/{payment.stripe_session_id}"

        return {
            "payment_id": payment_id,
            "stripe_link": stripe_link,
            "stripe_payment_intent_id": payment.stripe_payment_intent_id,
            "stripe_session_id": payment.stripe_session_id,
        }
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error getting Stripe link: {e}")
        raise APIException(
            detail="Failed to get Stripe link",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/{payment_id}/refund")
async def initiate_refund(
    payment_id: int,
    request: Request,
    amount: float | None = None,
    current_user: User = Depends(require_permission(AdminPermissions.PROCESS_REFUNDS)),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a refund through Stripe (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get payment
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()

        if not payment:
            raise APIException(
                detail="Payment not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        if payment.status != "completed":
            raise APIException(
                detail="Only completed payments can be refunded",
                status_code=400,
                error_code="INVALID_STATUS",
            )

        # TODO: Integrate with Stripe API to create refund
        # For now, just mark as refunded
        from sqlalchemy import update

        refund_amount = amount or float(payment.amount)

        await db.execute(
            update(Payment).where(Payment.id == payment_id).values(status="refunded")
        )
        await db.commit()

        # Log admin action (critical)
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="initiate_refund",
            target_type="payment",
            target_id=payment_id,
            old_value={"status": payment.status},
            new_value={"status": "refunded", "refund_amount": refund_amount},
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
            ip=ip,
            endpoint=f"/api/v1/admin/payments/{payment_id}/refund",
            resource="payment",
            action="initiate_refund",
            outcome="success",
        )

        return {
            "message": "Refund initiated successfully",
            "payment_id": payment_id,
            "refund_amount": refund_amount,
            "status": "refunded",
        }
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error initiating refund: {e}")
        raise APIException(
            detail="Failed to initiate refund",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/export")
async def export_payments(
    request: Request,
    format: str = Query("csv", pattern="^(csv|excel)$"),
    status: str | None = Query(None),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_user: User = Depends(require_permission(AdminPermissions.EXPORT_DATA)),
    db: AsyncSession = Depends(get_db),
):
    """Export payments to CSV/Excel (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Build query
        query = select(Payment)

        if status:
            query = query.where(Payment.status == status)
        if start_date:
            query = query.where(Payment.created_at >= start_date)
        if end_date:
            query = query.where(Payment.created_at <= end_date)

        query = query.order_by(Payment.created_at.desc())

        result = await db.execute(query)
        payments = result.scalars().all()

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="export_payments",
            target_type="payment",
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        if format == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(
                [
                    "ID",
                    "User ID",
                    "Document ID",
                    "Amount",
                    "Currency",
                    "Status",
                    "Stripe Payment Intent ID",
                    "Payment Method",
                    "Created At",
                    "Completed At",
                ]
            )

            # Write data
            for payment in payments:
                writer.writerow(
                    [
                        payment.id,
                        payment.user_id,
                        payment.document_id,
                        float(payment.amount),
                        payment.currency,
                        payment.status,
                        payment.stripe_payment_intent_id,
                        payment.payment_method,
                        payment.created_at.isoformat() if payment.created_at else None,
                        payment.completed_at.isoformat()
                        if payment.completed_at
                        else None,
                    ]
                )

            output.seek(0)

            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=payments_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                },
            )
        else:
            # TODO: Implement Excel export
            raise APIException(
                detail="Excel export not yet implemented",
                status_code=501,
                error_code="NOT_IMPLEMENTED",
            )
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error exporting payments: {e}")
        raise APIException(
            detail="Failed to export payments",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/stats")
async def get_payment_stats(
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_ANALYTICS)),
    db: AsyncSession = Depends(get_db),
):
    """Get payment statistics (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get total payments
        total_result = await db.execute(select(func.count(Payment.id)))
        total_payments = total_result.scalar()

        # Get payments by status
        status_result = await db.execute(
            select(Payment.status, func.count(Payment.id)).group_by(Payment.status)
        )
        status_counts = {row[0]: row[1] for row in status_result.all()}

        # Get total revenue
        revenue_result = await db.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "completed")
        )
        total_revenue = float(revenue_result.scalar() or 0)

        # Get average payment amount
        avg_result = await db.execute(
            select(func.avg(Payment.amount)).where(Payment.status == "completed")
        )
        avg_amount = float(avg_result.scalar() or 0)

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="view_payment_stats",
            target_type="payment",
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        return {
            "total_payments": total_payments,
            "status_counts": status_counts,
            "total_revenue": total_revenue,
            "average_payment_amount": avg_amount,
        }
    except Exception as e:
        logger.error(f"Error getting payment stats: {e}")
        raise APIException(
            detail="Failed to get payment stats",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e
