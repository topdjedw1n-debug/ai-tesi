"""
Admin endpoints for document management
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.exceptions import APIException
from app.core.logging import log_security_audit_event
from app.core.permissions import AdminPermissions
from app.core.security import create_download_token
from app.models.auth import User
from app.models.document import AIGenerationJob, Document
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def list_documents(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(draft|generating|completed|failed)$"),
    user_id: int | None = Query(None),
    language: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_DOCUMENTS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all documents with filters (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"
    endpoint = "/api/v1/admin/documents"

    try:
        # Build query
        query = select(Document)

        # Apply filters
        if status:
            query = query.where(Document.status == status)
        if user_id:
            query = query.where(Document.user_id == user_id)
        if language:
            query = query.where(Document.language == language)
        if start_date:
            query = query.where(Document.created_at >= start_date)
        if end_date:
            query = query.where(Document.created_at <= end_date)

        # Get total count
        count_query = select(func.count(Document.id))
        if status:
            count_query = count_query.where(Document.status == status)
        if user_id:
            count_query = count_query.where(Document.user_id == user_id)
        if language:
            count_query = count_query.where(Document.language == language)
        if start_date:
            count_query = count_query.where(Document.created_at >= start_date)
        if end_date:
            count_query = count_query.where(Document.created_at <= end_date)

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        offset = (page - 1) * per_page
        query = (
            query.offset(offset).limit(per_page).order_by(Document.created_at.desc())
        )

        result = await db.execute(query)
        documents = result.scalars().all()

        # Convert to dict format
        documents_list = []
        for doc in documents:
            documents_list.append(
                {
                    "id": doc.id,
                    "user_id": doc.user_id,
                    "title": doc.title,
                    "topic": doc.topic,
                    "language": doc.language,
                    "target_pages": doc.target_pages,
                    "status": doc.status,
                    "ai_provider": doc.ai_provider,
                    "ai_model": doc.ai_model,
                    "tokens_used": doc.tokens_used,
                    "generation_time_seconds": doc.generation_time_seconds,
                    "created_at": doc.created_at.isoformat()
                    if doc.created_at
                    else None,
                    "completed_at": doc.completed_at.isoformat()
                    if doc.completed_at
                    else None,
                }
            )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
            ip=ip,
            endpoint=endpoint,
            resource="documents",
            action="list",
            outcome="success",
            details={
                "page": page,
                "per_page": per_page,
                "filters": {
                    "status": status,
                    "user_id": user_id,
                    "language": language,
                },
            },
        )

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_documents",
            target_type="document",
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        return {
            "documents": documents_list,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": ((total or 0) + per_page - 1) // per_page,
        }
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
            ip=ip,
            endpoint=endpoint,
            resource="documents",
            action="list",
            outcome="failure",
            details={"error": str(e)},
        )
        raise APIException(
            detail="Failed to list documents",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/{document_id}")
async def get_document_details(
    document_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_DOCUMENTS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed document information (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get document
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise APIException(
                detail="Document not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        # Get user info
        user_result = await db.execute(select(User).where(User.id == document.user_id))
        user = user_result.scalar_one_or_none()

        # Get AI generation jobs for this document
        jobs_result = await db.execute(
            select(AIGenerationJob)
            .where(AIGenerationJob.document_id == document_id)
            .order_by(AIGenerationJob.started_at.desc())
        )
        jobs = jobs_result.scalars().all()

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_document_details",
            target_type="document",
            target_id=document_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/documents/{document_id}",
            resource="document",
            action="view_details",
            outcome="success",
        )

        return {
            "id": document.id,
            "user_id": document.user_id,
            "user_email": user.email if user else None,
            "title": document.title,
            "topic": document.topic,
            "language": document.language,
            "target_pages": document.target_pages,
            "status": document.status,
            "ai_provider": document.ai_provider,
            "ai_model": document.ai_model,
            "tokens_used": document.tokens_used,
            "generation_time_seconds": document.generation_time_seconds,
            "created_at": document.created_at.isoformat()
            if document.created_at
            else None,
            "completed_at": document.completed_at.isoformat()
            if document.completed_at
            else None,
            "content": document.content,
            "outline": document.outline,
            "jobs": [
                {
                    "id": job.id,
                    "status": job.status,
                    "started_at": job.started_at.isoformat()
                    if job.started_at
                    else None,
                    "completed_at": job.completed_at.isoformat()
                    if job.completed_at
                    else None,
                    "total_tokens": getattr(
                        job, "total_tokens", 0
                    ),  # Safe attribute access
                    "cost_cents": getattr(job, "cost_cents", 0),
                }
                for job in jobs
            ],
        }
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details: {e}")
        raise APIException(
            detail="Failed to get document details",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.get("/{document_id}/logs")
async def get_document_logs(
    document_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_DOCUMENTS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get generation logs for a document (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Verify document exists
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise APIException(
                detail="Document not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        # Get AI generation jobs
        jobs_result = await db.execute(
            select(AIGenerationJob)
            .where(AIGenerationJob.document_id == document_id)
            .order_by(AIGenerationJob.started_at.desc())
        )
        jobs = jobs_result.scalars().all()

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="view_document_logs",
            target_type="document",
            target_id=document_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        return {
            "document_id": document_id,
            "logs": [
                {
                    "id": job.id,
                    "status": job.status,
                    "started_at": job.started_at.isoformat()
                    if job.started_at
                    else None,
                    "completed_at": job.completed_at.isoformat()
                    if job.completed_at
                    else None,
                    "tokens_used": job.total_tokens,  # was: tokens_used
                    "cost_cents": job.cost_cents,
                    "error_message": job.error_message,
                }
                for job in jobs
            ],
        }
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error getting document logs: {e}")
        raise APIException(
            detail="Failed to get document logs",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.DELETE_DOCUMENTS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a document (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get document before deletion
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise APIException(
                detail="Document not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        # Delete document
        from sqlalchemy import delete

        await db.execute(delete(Document).where(Document.id == document_id))
        await db.commit()

        # Log admin action (critical)
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="delete_document",
            target_type="document",
            target_id=document_id,
            old_value={
                "title": document.title,
                "user_id": document.user_id,
                "status": document.status,
            },
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=current_user.id,
            ip=ip,
            endpoint=f"/api/v1/admin/documents/{document_id}",
            resource="document",
            action="delete",
            outcome="success",
        )

        return {"message": "Document deleted successfully", "document_id": document_id}
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise APIException(
            detail="Failed to delete document",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/{document_id}/retry")
async def retry_document_generation(
    document_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.RETRY_DOCUMENTS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retry document generation (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get document
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise APIException(
                detail="Document not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        # Update document status to draft so it can be regenerated
        from sqlalchemy import update

        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status="draft", completed_at=None)
        )
        await db.commit()

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="retry_document_generation",
            target_type="document",
            target_id=document_id,
            old_value={"status": document.status},
            new_value={"status": "draft"},
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id,
            user_id=int(current_user.id),
            ip=ip,
            endpoint=f"/api/v1/admin/documents/{document_id}/retry",
            resource="document",
            action="retry",
            outcome="success",
        )

        return {
            "message": "Document generation retry initiated",
            "document_id": document_id,
            "status": "draft",
        }
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error retrying document generation: {e}")
        raise APIException(
            detail="Failed to retry document generation",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e


@router.post("/{document_id}/download")
async def download_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_DOCUMENTS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get download link or content for a document (admin only)"""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    ip = request.client.host if request.client else "unknown"

    try:
        # Get document
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise APIException(
                detail="Document not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="download_document",
            target_type="document",
            target_id=document_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        # Generate signed download URL
        download_token = create_download_token(
            document_id=int(document.id),
            user_id=int(current_user.id),
            expiration_minutes=60,
        )

        # Return document content (in production, this would be a signed URL or file download)
        return {
            "document_id": document_id,
            "title": document.title,
            "content": document.content,
            "download_url": f"/api/v1/documents/download?token={download_token}",
        }
    except APIException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document: {e}")
        raise APIException(
            detail="Failed to download document",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e
