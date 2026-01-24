"""
Refund endpoints - for users and admins
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.logging import log_security_audit_event
from app.core.permissions import AdminPermissions
from app.models.auth import User
from app.schemas.refund import (
    RefundDetailsResponse,
    RefundListResponse,
    RefundRequestCreate,
    RefundResponse,
    RefundReviewRequest,
    RefundStatsResponse,
)
from app.services.admin_service import AdminService
from app.services.refund_service import RefundService

logger = logging.getLogger(__name__)

# Separate routers for user and admin endpoints
user_router = APIRouter()
admin_router = APIRouter()


# ==================== User Endpoints ====================


@user_router.post("", response_model=RefundResponse)
async def create_refund_request(
    request: Request,
    refund_data: RefundRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """
    Create a refund request (user endpoint).

    Users can request refunds for their completed payments.
    """
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        refund_service = RefundService(db)
        refund_request = await refund_service.create_refund_request(
            user_id=int(current_user.id),
            payment_id=refund_data.payment_id,
            reason=refund_data.reason,
            reason_category=refund_data.reason_category,
            screenshots=refund_data.screenshots,
        )

        log_security_audit_event(
            event_type="refund_request",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint="/api/v1/refunds",
            resource="refund",
            action="create",
            outcome="success",
            details={
                "refund_id": refund_request.id,
                "payment_id": refund_data.payment_id,
            },
        )

        return RefundResponse(
            id=int(refund_request.id),
            user_id=int(refund_request.user_id),
            payment_id=int(refund_request.payment_id),
            status=str(refund_request.status),
            reason=str(refund_request.reason),
            reason_category=str(refund_request.reason_category)
            if refund_request.reason_category
            else None,
            submitted_at=refund_request.submitted_at,
            reviewed_at=refund_request.reviewed_at
            if refund_request.reviewed_at
            else None,
            reviewed_by=int(refund_request.reviewed_by)
            if refund_request.reviewed_by
            else None,
            admin_comment=str(refund_request.admin_comment)
            if refund_request.admin_comment
            else None,
            refund_amount=refund_request.refund_amount
            if refund_request.refund_amount
            else None,
            ai_recommendation=str(refund_request.ai_recommendation)
            if refund_request.ai_recommendation
            else None,
            risk_score=float(refund_request.risk_score)
            if refund_request.risk_score
            else None,
        )
    except ValueError as e:
        log_security_audit_event(
            event_type="refund_request",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint="/api/v1/refunds",
            resource="refund",
            action="create",
            outcome="failure",
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error creating refund request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create refund request",
        ) from e


# ==================== Admin Endpoints ====================


@admin_router.get("", response_model=RefundListResponse)
async def list_refunds(
    request: Request,
    status: str | None = Query(None, pattern="^(pending|approved|rejected)$"),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permission(AdminPermissions.PROCESS_REFUNDS)),
    db: AsyncSession = Depends(get_db),
) -> RefundListResponse:
    """
    Get list of refund requests with filters (admin only).

    Requires PROCESS_REFUNDS permission.
    """
    try:
        refund_service = RefundService(db)
        result = await refund_service.get_refunds_list(
            status=status,
            user_id=user_id,
            page=page,
            per_page=per_page,
        )

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_refunds",
            target_type="refund",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            correlation_id=request.headers.get("X-Request-ID", "unknown"),
        )

        refunds_response = [
            RefundResponse(
                id=int(r.id),
                user_id=int(r.user_id),
                payment_id=int(r.payment_id),
                status=str(r.status),
                reason=str(r.reason),
                reason_category=str(r.reason_category) if r.reason_category else None,
                submitted_at=r.submitted_at,
                reviewed_at=r.reviewed_at,
                reviewed_by=int(r.reviewed_by) if r.reviewed_by else None,
                admin_comment=str(r.admin_comment) if r.admin_comment else None,
                refund_amount=r.refund_amount,
                ai_recommendation=str(r.ai_recommendation)
                if r.ai_recommendation
                else None,
                risk_score=float(r.risk_score) if r.risk_score else None,
            )
            for r in result["refunds"]
        ]

        return RefundListResponse(
            refunds=refunds_response,
            total=result["total"],
            page=result["page"],
            per_page=result["per_page"],
            pages=result["pages"],
        )
    except Exception as e:
        logger.error(f"Error listing refunds: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get refunds list",
        ) from e


@admin_router.get("/pending")
async def get_pending_refunds(
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.PROCESS_REFUNDS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get count of pending refunds (for badge display).

    Requires PROCESS_REFUNDS permission.
    """
    try:
        refund_service = RefundService(db)
        result = await refund_service.get_refunds_list(
            status="pending", page=1, per_page=1
        )

        return {"count": result["total"], "has_pending": result["total"] > 0}
    except Exception as e:
        logger.error(f"Error getting pending refunds count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pending refunds count",
        ) from e


@admin_router.get("/{refund_id}", response_model=RefundDetailsResponse)
async def get_refund_details(
    refund_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.PROCESS_REFUNDS)),
    db: AsyncSession = Depends(get_db),
) -> RefundDetailsResponse:
    """
    Get detailed refund request information (admin only).

    Requires PROCESS_REFUNDS permission.
    """
    try:
        refund_service = RefundService(db)
        refund_request = await refund_service.get_refund_request(refund_id)

        # Get user info
        user = refund_request.user
        user_info = {
            "id": user.id if user else None,
            "email": user.email if user else None,
            "full_name": user.full_name if user else None,
            "registered_at": user.created_at.isoformat() if user else None,
        }

        # Get payment info
        payment = refund_request.payment
        payment_info = {
            "id": payment.id if payment else None,
            "amount": float(payment.amount) if payment else None,
            "currency": payment.currency if payment else None,
            "status": payment.status if payment else None,
            "created_at": payment.created_at.isoformat() if payment else None,
        }

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_refund_details",
            target_type="refund",
            target_id=refund_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            correlation_id=request.headers.get("X-Request-ID", "unknown"),
        )

        return RefundDetailsResponse(
            id=int(refund_request.id),
            user_id=int(refund_request.user_id),
            payment_id=int(refund_request.payment_id),
            status=str(refund_request.status),
            reason=str(refund_request.reason),
            reason_category=str(refund_request.reason_category)
            if refund_request.reason_category
            else None,
            submitted_at=refund_request.submitted_at,
            reviewed_at=refund_request.reviewed_at
            if refund_request.reviewed_at
            else None,
            reviewed_by=int(refund_request.reviewed_by)
            if refund_request.reviewed_by
            else None,
            admin_comment=str(refund_request.admin_comment)
            if refund_request.admin_comment
            else None,
            refund_amount=refund_request.refund_amount
            if refund_request.refund_amount
            else None,
            ai_recommendation=str(refund_request.ai_recommendation)
            if refund_request.ai_recommendation
            else None,
            risk_score=float(refund_request.risk_score)
            if refund_request.risk_score
            else None,
            user=user_info,
            payment=payment_info,
            screenshots=list(refund_request.screenshots)
            if refund_request.screenshots
            else [],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error getting refund details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get refund details",
        ) from e


@admin_router.post("/{refund_id}/approve", response_model=RefundResponse)
async def approve_refund(
    refund_id: int,
    request: Request,
    review_data: RefundReviewRequest,
    current_user: User = Depends(require_permission(AdminPermissions.PROCESS_REFUNDS)),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """
    Approve a refund request and process Stripe refund (admin only).

    Requires PROCESS_REFUNDS permission.
    """
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        refund_service = RefundService(db)

        # Get refund before approval to log old value
        refund_before = await refund_service.get_refund_request(refund_id)

        # Approve refund
        refund_request = await refund_service.approve_refund(
            refund_id=refund_id,
            admin_id=int(current_user.id),
            admin_comment=review_data.admin_comment,
            refund_amount=review_data.refund_amount,
        )

        # Log admin action with old/new values
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="approve_refund",
            target_type="refund",
            target_id=refund_id,
            old_value={
                "status": refund_before.status,
                "reviewed_at": refund_before.reviewed_at.isoformat()
                if refund_before.reviewed_at
                else None,
            },
            new_value={
                "status": refund_request.status,
                "reviewed_at": refund_request.reviewed_at.isoformat(),
                "refund_amount": float(refund_request.refund_amount)
                if refund_request.refund_amount
                else None,
            },
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        return RefundResponse(
            id=int(refund_request.id),
            user_id=int(refund_request.user_id),
            payment_id=int(refund_request.payment_id),
            status=str(refund_request.status),
            reason=str(refund_request.reason),
            reason_category=str(refund_request.reason_category)
            if refund_request.reason_category
            else None,
            submitted_at=refund_request.submitted_at,
            reviewed_at=refund_request.reviewed_at
            if refund_request.reviewed_at
            else None,
            reviewed_by=int(refund_request.reviewed_by)
            if refund_request.reviewed_by
            else None,
            admin_comment=str(refund_request.admin_comment)
            if refund_request.admin_comment
            else None,
            refund_amount=refund_request.refund_amount
            if refund_request.refund_amount
            else None,
            ai_recommendation=str(refund_request.ai_recommendation)
            if refund_request.ai_recommendation
            else None,
            risk_score=float(refund_request.risk_score)
            if refund_request.risk_score
            else None,
        )
    except ValueError as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/refunds/{refund_id}/approve",
            resource="refund",
            action="approve_refund",
            outcome="failure",
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error approving refund: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve refund",
        ) from e


@admin_router.post("/{refund_id}/reject", response_model=RefundResponse)
async def reject_refund(
    refund_id: int,
    request: Request,
    review_data: RefundReviewRequest,
    current_user: User = Depends(require_permission(AdminPermissions.PROCESS_REFUNDS)),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """
    Reject a refund request (admin only).

    Requires PROCESS_REFUNDS permission.
    """
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        refund_service = RefundService(db)

        # Get refund before rejection to log old value
        refund_before = await refund_service.get_refund_request(refund_id)

        # Reject refund
        refund_request = await refund_service.reject_refund(
            refund_id=refund_id,
            admin_id=int(current_user.id),
            admin_comment=review_data.admin_comment,
        )

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="reject_refund",
            target_type="refund",
            target_id=refund_id,
            old_value={"status": refund_before.status},
            new_value={"status": refund_request.status},
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        return RefundResponse(
            id=int(refund_request.id),
            user_id=int(refund_request.user_id),
            payment_id=int(refund_request.payment_id),
            status=str(refund_request.status),
            reason=str(refund_request.reason),
            reason_category=str(refund_request.reason_category)
            if refund_request.reason_category
            else None,
            submitted_at=refund_request.submitted_at,
            reviewed_at=refund_request.reviewed_at
            if refund_request.reviewed_at
            else None,
            reviewed_by=int(refund_request.reviewed_by)
            if refund_request.reviewed_by
            else None,
            admin_comment=str(refund_request.admin_comment)
            if refund_request.admin_comment
            else None,
            refund_amount=refund_request.refund_amount
            if refund_request.refund_amount
            else None,
            ai_recommendation=str(refund_request.ai_recommendation)
            if refund_request.ai_recommendation
            else None,
            risk_score=float(refund_request.risk_score)
            if refund_request.risk_score
            else None,
        )
    except ValueError as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/refunds/{refund_id}/reject",
            resource="refund",
            action="reject_refund",
            outcome="failure",
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error rejecting refund: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject refund",
        ) from e


@admin_router.post("/{refund_id}/analyze")
async def analyze_refund_risk(
    refund_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.PROCESS_REFUNDS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Analyze refund request for risk using AI (admin only, optional).

    Requires PROCESS_REFUNDS permission.
    """
    try:
        refund_service = RefundService(db)
        analysis = await refund_service.analyze_refund_risk(refund_id)

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="analyze_refund_risk",
            target_type="refund",
            target_id=refund_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            correlation_id=request.headers.get("X-Request-ID", "unknown"),
        )

        return analysis
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error analyzing refund risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze refund risk",
        ) from e


@admin_router.get("/stats", response_model=RefundStatsResponse)
async def get_refund_stats(
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_ANALYTICS)),
    db: AsyncSession = Depends(get_db),
) -> RefundStatsResponse:
    """
    Get refund statistics (admin only).

    Requires VIEW_ANALYTICS permission.
    """
    try:
        refund_service = RefundService(db)
        stats = await refund_service.get_refund_stats()

        return RefundStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting refund stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get refund stats",
        ) from e
