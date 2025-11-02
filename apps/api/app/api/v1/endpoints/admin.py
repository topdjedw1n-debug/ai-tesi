"""
Admin endpoints for monitoring and management
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import reload_settings
from app.core.database import get_db
from app.core.dependencies import get_admin_user
from app.core.exceptions import APIException
from app.core.logging import log_security_audit_event
from app.models.auth import User
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_platform_stats(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get platform statistics (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/stats"

    try:
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
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
            user_id=current_user.id,
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


@router.get("/users")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str | None = None,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
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
            user_id=current_user.id,
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
            user_id=current_user.id,
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
):
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
            user_id=current_user.id,
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
            user_id=current_user.id,
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
):
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
            user_id=current_user.id,
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
            user_id=current_user.id,
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
):
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
            user_id=current_user.id,
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
            user_id=current_user.id,
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
):
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
            user_id=current_user.id,
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
            user_id=current_user.id,
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
):
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
            user_id=current_user.id,
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
            user_id=current_user.id,
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
):
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
            user_id=current_user.id,
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
            user_id=current_user.id,
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
