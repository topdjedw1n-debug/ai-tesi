"""
Admin endpoints for monitoring and management
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import reload_settings
from app.core.database import get_db
from app.core.dependencies import get_admin_user, require_permission
from app.core.exceptions import APIException
from app.core.logging import log_security_audit_event
from app.core.permissions import AdminPermissions
from app.models.auth import User
from app.schemas.admin_user import (
    BlockUserRequest,
    BulkUserActionRequest,
    BulkUserActionResult,
    MakeAdminRequest,
    SendEmailRequest,
    SendEmailResponse,
    UserWithStatsResponse,
)
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_platform_stats(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get platform statistics (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/stats"

    try:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="platform",
            action="read_stats",
            outcome="success",
        )

        admin_service = AdminService(db)
        result = await admin_service.get_platform_stats()
        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="platform",
            action="read_stats",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to get platform statistics",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/dashboard/charts")
async def get_dashboard_charts(
    request: Request,
    period: str = Query("week", regex="^(day|week|month|year)$"),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get chart data for dashboard graphs (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/dashboard/charts"

    try:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="dashboard",
            action="read_charts",
            outcome="success",
        )

        admin_service = AdminService(db)
        result = await admin_service.get_dashboard_charts(period=period)
        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="dashboard",
            action="read_charts",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to get dashboard charts",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/dashboard/activity")
async def get_dashboard_activity(
    request: Request,
    type: str = Query("recent", regex="^(recent|payments|registrations|errors)$"),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get recent activity for dashboard (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/dashboard/activity"

    try:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="dashboard",
            action="read_activity",
            outcome="success",
        )

        admin_service = AdminService(db)
        result = await admin_service.get_dashboard_activity(
            activity_type=type, limit=limit
        )
        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="dashboard",
            action="read_activity",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to get dashboard activity",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/dashboard/metrics")
async def get_dashboard_metrics(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get business metrics for dashboard (MRR, ARPU, etc.) (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/dashboard/metrics"

    try:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="dashboard",
            action="read_metrics",
            outcome="success",
        )

        admin_service = AdminService(db)
        result = await admin_service.get_dashboard_metrics()
        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="dashboard",
            action="read_metrics",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to get dashboard metrics",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/users")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str | None = None,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all users (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/users"

    try:
        admin_service = AdminService(db)
        result = await admin_service.list_users(page, per_page, search)

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="users",
            action="list",
            outcome="success",
            details={
                "page": page,
                "per_page": per_page,
                "has_search": search is not None,
            },
        )

        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="users",
            action="list",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to list users",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/users/{user_id}", response_model=UserWithStatsResponse)
async def get_user_details(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed user information (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)
        user_data = await admin_service.get_user_details(user_id)

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}",
            resource="user",
            action="view_details",
            outcome="success",
        )

        # Log admin action
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_user_details",
            target_type="user",
            target_id=user_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        return UserWithStatsResponse(**user_data)
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=404,
            error_code="NOT_FOUND",
        ) from e
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise APIException(
            detail="Failed to get user details",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.put("/users/{user_id}/block")
async def block_user(
    user_id: int,
    request: Request,
    block_data: BlockUserRequest,
    current_user: User = Depends(require_permission(AdminPermissions.BLOCK_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Block a user (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)

        # Get user before blocking for audit log
        user_before = await admin_service.get_user_details(user_id)

        # Block user
        result = await admin_service.block_user(
            user_id=user_id,
            reason=block_data.reason,
            admin_id=int(current_user.id),
        )

        # Log admin action
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="block_user",
            target_type="user",
            target_id=user_id,
            old_value={"is_active": user_before["is_active"]},
            new_value={"is_active": False, "reason": block_data.reason},
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}/block",
            resource="user",
            action="block",
            outcome="success",
        )

        return result
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="VALIDATION_ERROR",
        ) from e
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        raise APIException(
            detail="Failed to block user",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.put("/users/{user_id}/unblock")
async def unblock_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.BLOCK_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Unblock a user (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)

        # Get user before unblocking for audit log
        user_before = await admin_service.get_user_details(user_id)

        # Unblock user
        result = await admin_service.unblock_user(
            user_id=user_id,
            admin_id=int(current_user.id),
        )

        # Log admin action
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="unblock_user",
            target_type="user",
            target_id=user_id,
            old_value={"is_active": user_before["is_active"]},
            new_value={"is_active": True},
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}/unblock",
            resource="user",
            action="unblock",
            outcome="success",
        )

        return result
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="VALIDATION_ERROR",
        ) from e
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        raise APIException(
            detail="Failed to unblock user",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.DELETE_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Soft delete a user (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)

        # Get user before deletion for audit log
        user_before = await admin_service.get_user_details(user_id)

        # Delete user
        result = await admin_service.delete_user(
            user_id=user_id,
            admin_id=int(current_user.id),
        )

        # Log admin action (critical)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="delete_user",
            target_type="user",
            target_id=user_id,
            old_value={
                "is_active": user_before["is_active"],
                "email": user_before["email"],
            },
            new_value={"is_active": False, "deleted": True},
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}",
            resource="user",
            action="delete",
            outcome="success",
        )

        return result
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="VALIDATION_ERROR",
        ) from e
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise APIException(
            detail="Failed to delete user",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/users/{user_id}/make-admin")
async def make_admin(
    user_id: int,
    request: Request,
    admin_data: MakeAdminRequest,
    current_user: User = Depends(require_permission(AdminPermissions.MAKE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Make user admin or revoke admin rights (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)

        # Get user before change for audit log
        user_before = await admin_service.get_user_details(user_id)

        # Update admin status
        result = await admin_service.make_admin(
            user_id=user_id,
            is_admin=admin_data.is_admin,
            is_super_admin=admin_data.is_super_admin,
            admin_id=int(current_user.id),
        )

        # Log admin action (critical if granting super admin)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="grant_super_admin" if admin_data.is_super_admin else "make_admin",
            target_type="user",
            target_id=user_id,
            old_value={
                "is_admin": user_before["is_admin"],
                "is_super_admin": user_before["is_super_admin"],
            },
            new_value={
                "is_admin": result["is_admin"],
                "is_super_admin": result["is_super_admin"],
            },
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}/make-admin",
            resource="user",
            action="make_admin",
            outcome="success",
        )

        return result
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="VALIDATION_ERROR",
        ) from e
    except Exception as e:
        logger.error(f"Error updating admin status: {e}")
        raise APIException(
            detail="Failed to update admin status",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/users/{user_id}/documents")
async def get_user_documents(
    user_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get documents for a specific user (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)
        result = await admin_service.get_user_documents(user_id, page, per_page)

        # Log admin action
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_user_documents",
            target_type="user",
            target_id=user_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}/documents",
            resource="user_documents",
            action="list",
            outcome="success",
        )

        return result
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=404,
            error_code="NOT_FOUND",
        ) from e
    except Exception as e:
        logger.error(f"Error getting user documents: {e}")
        raise APIException(
            detail="Failed to get user documents",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/users/{user_id}/payments")
async def get_user_payments(
    user_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get payments for a specific user (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)
        result = await admin_service.get_user_payments(user_id, page, per_page)

        # Log admin action
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_user_payments",
            target_type="user",
            target_id=user_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}/payments",
            resource="user_payments",
            action="list",
            outcome="success",
        )

        return result
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=404,
            error_code="NOT_FOUND",
        ) from e
    except Exception as e:
        logger.error(f"Error getting user payments: {e}")
        raise APIException(
            detail="Failed to get user payments",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/users/{user_id}/revoke-admin")
async def revoke_admin(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.MAKE_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Revoke admin rights from a user (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)

        # Get user before change for audit log
        user_before = await admin_service.get_user_details(user_id)

        # Revoke admin rights
        result = await admin_service.revoke_admin(
            user_id=user_id,
            admin_id=int(current_user.id),
        )

        # Log admin action (critical)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="revoke_admin",
            target_type="user",
            target_id=user_id,
            old_value={
                "is_admin": user_before.get("is_admin"),
                "is_super_admin": user_before.get("is_super_admin"),
            },
            new_value={"is_admin": False, "is_super_admin": False},
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}/revoke-admin",
            resource="user",
            action="revoke_admin",
            outcome="success",
        )

        return result
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="VALIDATION_ERROR",
        ) from e
    except Exception as e:
        logger.error(f"Error revoking admin rights: {e}")
        raise APIException(
            detail="Failed to revoke admin rights",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/users/{user_id}/send-email", response_model=SendEmailResponse)
async def send_email_to_user(
    user_id: int,
    request: Request,
    email_data: SendEmailRequest,
    current_user: User = Depends(require_permission(AdminPermissions.EDIT_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Send email to a user (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)

        # Send email
        result = await admin_service.send_email_to_user(
            user_id=user_id,
            subject=email_data.subject,
            message=email_data.message,
            admin_id=int(current_user.id),
        )

        # Log admin action
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="send_email_to_user",
            target_type="user",
            target_id=user_id,
            new_value={
                "subject": email_data.subject,
                "sent": result["sent"],
            },
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/users/{user_id}/send-email",
            resource="user",
            action="send_email",
            outcome="success" if result["sent"] else "partial",
            details={"subject": email_data.subject, "sent": result["sent"]},
        )

        return SendEmailResponse(**result)
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="VALIDATION_ERROR",
        ) from e
    except Exception as e:
        logger.error(f"Error sending email to user: {e}")
        raise APIException(
            detail="Failed to send email",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/users/bulk", response_model=BulkUserActionResult)
async def bulk_user_action(
    request: Request,
    bulk_data: BulkUserActionRequest,
    current_user: User = Depends(require_permission(AdminPermissions.BLOCK_USERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Perform bulk action on users (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        admin_service = AdminService(db)

        # Perform bulk action
        result = await admin_service.bulk_user_action(
            user_ids=bulk_data.user_ids,
            action=bulk_data.action,
            admin_id=int(current_user.id),
            reason=None,  # TODO: Add reason to schema if needed
        )

        # Log admin action
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action=f"bulk_{bulk_data.action}_users",
            target_type="user",
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
            new_value={
                "action": bulk_data.action,
                "total_requested": result["total_requested"],
                "successful": result["successful"],
                "failed": result["failed"],
            },
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint="/api/v1/admin/users/bulk",
            resource="user",
            action=f"bulk_{bulk_data.action}",
            outcome="success",
        )

        return BulkUserActionResult(**result)
    except ValueError as e:
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="VALIDATION_ERROR",
        ) from e
    except Exception as e:
        logger.error(f"Error performing bulk user action: {e}")
        raise APIException(
            detail="Failed to perform bulk action",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/ai-jobs")
async def list_ai_jobs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    user_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List AI generation jobs (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/ai-jobs"

    try:
        admin_service = AdminService(db)
        result = await admin_service.list_ai_jobs(
            page, per_page, user_id, start_date, end_date
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="ai_jobs",
            action="list",
            outcome="success",
            details={"page": page, "per_page": per_page, "filter_user_id": user_id},
        )

        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="ai_jobs",
            action="list",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to list AI jobs",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/costs")
async def get_cost_analysis(
    request: Request,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    group_by: str = Query("day", regex="^(day|week|month)$"),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get cost analysis (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/costs"

    try:
        admin_service = AdminService(db)
        result = await admin_service.get_cost_analysis(start_date, end_date, group_by)

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="costs",
            action="read",
            outcome="success",
            details={"group_by": group_by},
        )

        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="costs",
            action="read",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to get cost analysis",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/health")
async def health_check(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Detailed health check for admin"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/health"

    try:
        admin_service = AdminService(db)
        result = await admin_service.health_check()

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="system",
            action="health_check",
            outcome="success",
        )

        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="system",
            action="health_check",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Health check failed",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/config/reload")
async def reload_config(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reload application configuration from environment variables (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/config/reload"

    try:
        # Reload settings
        result = reload_settings()

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="config",
            action="reload",
            outcome="success",
            details={"validation_passed": result.get("validation_passed", False)},
        )

        return {
            "message": "Configuration reloaded successfully",
            "validation_passed": result.get("validation_passed", False),
            "warnings": result.get("warnings", []),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="config",
            action="reload",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail=f"Failed to reload configuration: {str(e)}",
            status_code=500,
            error_code="CONFIG_RELOAD_ERROR",
        ) from e


@router.get("/backup/verify")
async def verify_backup(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Verify database backup integrity (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/backup/verify"

    try:
        from app.core.database import verify_db_backup

        result = await verify_db_backup(db)

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="database",
            action="verify_backup",
            outcome="success"
            if result.get("status") == "healthy"
            else "needs_attention",
            details={
                "status": result.get("status"),
                "checks": result.get("checks", {}),
            },
        )

        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="database",
            action="verify_backup",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail=f"Failed to verify backup: {str(e)}",
            status_code=500,
            error_code="BACKUP_VERIFICATION_ERROR",
        ) from e


@router.get("/storage/verify")
async def verify_storage(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Verify file storage integrity (MinIO/S3) (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/storage/verify"

    try:
        from app.services.document_service import DocumentService

        document_service = DocumentService(db)
        result = await document_service.verify_file_storage_integrity()

        status = (
            "healthy"
            if result.get("missing_files", 0) == 0
            and result.get("orphaned_files", 0) == 0
            else "needs_attention"
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="storage",
            action="verify_integrity",
            outcome="success" if status == "healthy" else "needs_attention",
            details={
                "status": status,
                "missing_files": result.get("missing_files", 0),
                "orphaned_files": result.get("orphaned_files", 0),
            },
        )

        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="storage",
            action="verify_integrity",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail=f"Failed to verify storage: {str(e)}",
            status_code=500,
            error_code="STORAGE_VERIFICATION_ERROR",
        ) from e


@router.get("/jobs/stuck")
async def monitor_stuck_jobs(
    request: Request,
    threshold_minutes: int = Query(
        5, ge=1, le=60, description="Minutes after which a job is considered stuck"
    ),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Monitor for stuck AI generation jobs (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/jobs/stuck"

    try:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="jobs",
            action="monitor_stuck",
            outcome="success",
        )

        admin_service = AdminService(db)
        result = await admin_service.monitor_stuck_jobs(
            stuck_threshold_minutes=threshold_minutes
        )
        return result
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="jobs",
            action="monitor_stuck",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail=f"Failed to monitor stuck jobs: {str(e)}",
            status_code=500,
            error_code="MONITOR_STUCK_JOBS_ERROR",
        ) from e


@router.post("/jobs/cleanup")
async def cleanup_stuck_jobs(
    request: Request,
    threshold_minutes: int = Query(
        5, ge=1, le=60, description="Minutes after which a job is considered stuck"
    ),
    action: str = Query(
        "mark_failed", description="Action to take: 'mark_failed' or 'retry'"
    ),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Cleanup stuck AI generation jobs (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/jobs/cleanup"

    if action not in ["mark_failed", "retry"]:
        raise APIException(
            detail="Invalid action. Must be 'mark_failed' or 'retry'",
            status_code=400,
            error_code="INVALID_ACTION",
        )

    try:
        admin_service = AdminService(db)
        result = await admin_service.cleanup_stuck_jobs(
            stuck_threshold_minutes=threshold_minutes, action=action
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="jobs",
            action="cleanup_stuck",
            outcome="success",
            details={
                "threshold_minutes": threshold_minutes,
                "action": action,
                "cleaned_jobs": result.get("cleaned_jobs", {}).get("total", 0),
            },
        )

        return result
    except ValueError as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="jobs",
            action="cleanup_stuck",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail=str(e),
            status_code=400,
            error_code="INVALID_PARAMETER",
        ) from e
    except Exception as e:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=endpoint,
            resource="jobs",
            action="cleanup_stuck",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail=f"Failed to cleanup stuck jobs: {str(e)}",
            status_code=500,
            error_code="CLEANUP_STUCK_JOBS_ERROR",
        ) from e
