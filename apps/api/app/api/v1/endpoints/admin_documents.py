"""
Admin endpoints for document management
"""

import hmac
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.generate import (
    _delete_superseded_artifacts,
    _enforce_generation_gate,
    _invalidate_previous_generation_evidence,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.exceptions import APIException, ValidationError
from app.core.logging import log_security_audit_event
from app.core.permissions import AdminPermissions
from app.core.security import create_download_token
from app.models.auth import User
from app.models.document import AIGenerationJob, Document, ProductionCase
from app.services.admin_service import AdminService
from app.services.document_service import DocumentService
from app.services.generation_contract import generation_contract_sha256
from app.services.storage_service import StorageService
from app.services.uploaded_sources import uploaded_sources_digest

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

        old_value = {
            "title": document.title,
            "user_id": document.user_id,
            "status": document.status,
        }

        # Reuse the same storage-first path as user deletion. Passing the
        # document owner's ID keeps the ownership condition inside the service
        # while the permission dependency above remains the admin authorization.
        document_service = DocumentService(db)
        await document_service.delete_document(
            document_id=document_id,
            user_id=int(document.user_id),
        )

        # Log admin action (critical)
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="delete_document",
            target_type="document",
            target_id=document_id,
            old_value=old_value,
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
    except ValidationError as e:
        raise APIException(
            detail=str(e),
            status_code=409,
            error_code="DOCUMENT_BUSY",
        ) from e
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
        # Discover the owner without locking, then use the shared lock order:
        # User -> Document -> ProductionCase -> active generation job.
        owner_id = (
            await db.execute(select(Document.user_id).where(Document.id == document_id))
        ).scalar_one_or_none()
        if owner_id is None:
            raise APIException(
                detail="Document not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        owner_result = await db.execute(
            select(User)
            .where(User.id == owner_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        owner = owner_result.scalar_one_or_none()
        if owner is None:
            raise APIException(
                detail="Document owner not found",
                status_code=409,
                error_code="DOCUMENT_OWNER_MISSING",
            )
        if owner.deletion_requested_at is not None:
            raise APIException(
                detail="Account deletion is pending; generation cannot be retried",
                status_code=409,
                error_code="ACCOUNT_DELETION_PENDING",
            )

        result = await db.execute(
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise APIException(
                detail="Document not found",
                status_code=404,
                error_code="NOT_FOUND",
            )

        case_result = await db.execute(
            select(ProductionCase)
            .where(ProductionCase.document_id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        production_case = case_result.scalar_one_or_none()
        if production_case is None:
            production_case = ProductionCase(
                document_id=int(document.id),
                client_user_id=int(document.user_id),
                citation_style=str(document.citation_style or "apa"),
                generation_status="not_started",
                payment_status="not_required",
            )
            db.add(production_case)
            await db.flush()

        active_job = (
            await db.execute(
                select(AIGenerationJob).where(
                    AIGenerationJob.document_id == document_id,
                    AIGenerationJob.job_type == "full_document",
                    AIGenerationJob.status.in_(["queued", "running"]),
                )
            )
        ).scalar_one_or_none()
        if active_job is not None:
            raise APIException(
                detail=f"Generation job {active_job.id} is already active",
                status_code=409,
                error_code="GENERATION_ALREADY_ACTIVE",
            )

        old_status = str(document.status)
        if old_status not in {"completed", "failed", "failed_quality"}:
            raise APIException(
                detail=f"Document in status '{old_status}' cannot be retried",
                status_code=409,
                error_code="DOCUMENT_NOT_RETRYABLE",
            )

        if (
            not bool(document.requirements_file_processed)
            or not str(document.additional_requirements or "").strip()
        ):
            raise APIException(
                detail="A processed methodology file is required before retry",
                status_code=409,
                error_code="METHODOLOGY_REQUIRED",
            )
        if str(document.citation_style or "").strip().lower() != "apa":
            raise APIException(
                detail="The current Italian MVP supports APA citations only",
                status_code=409,
                error_code="UNSUPPORTED_CITATION_STYLE",
            )

        try:
            # Admin retry is still a generation start. It reserves the same
            # page, daily-run, token, and payment budgets as the user endpoint.
            await _enforce_generation_gate(db, document, int(document.user_id))
        except HTTPException as gate_error:
            raise APIException(
                detail=str(gate_error.detail),
                status_code=gate_error.status_code,
                error_code="GENERATION_GATE_BLOCKED",
            ) from gate_error

        # The worker always prepends Document.additional_requirements. The job
        # payload carries only case/run additions so methodology is not doubled.
        run_requirements = (
            str(production_case.requirements_text)
            if production_case is not None and production_case.requirements_text
            else None
        )
        contract_sha256 = generation_contract_sha256(
            document,
            production_case,
            run_requirements,
            await uploaded_sources_digest(db, document_id),
        )
        superseded_paths = await _invalidate_previous_generation_evidence(
            db,
            document_id,
            contract_sha256=contract_sha256,
        )
        job = AIGenerationJob(
            user_id=int(document.user_id),
            document_id=document_id,
            job_type="full_document",
            ai_provider=document.ai_provider,
            ai_model=document.ai_model,
            status="queued",
            progress=0,
            request_payload={
                "additional_requirements": run_requirements,
                "generation_contract_sha256": contract_sha256,
                "superseded_artifact_paths": superseded_paths,
            },
            max_attempts=settings.GENERATION_JOB_MAX_ATTEMPTS,
        )
        db.add(job)
        try:
            # Reserve the single active-job slot before deleting old blobs or
            # evidence. Any competing retry fails without invalidating anything.
            await db.flush()
        except IntegrityError as error:
            await db.rollback()
            raise APIException(
                detail="A generation retry became active concurrently",
                status_code=409,
                error_code="GENERATION_ALREADY_ACTIVE",
            ) from error

        document.status = "generating"
        document.completed_at = None
        await db.commit()
        job_id = int(job.id)
        await _delete_superseded_artifacts(superseded_paths)

        # Log admin action
        admin_service = AdminService(db)
        await admin_service.log_admin_action(
            admin_id=int(current_user.id),
            action="retry_document_generation",
            target_type="document",
            target_id=document_id,
            old_value={"status": old_status},
            new_value={"status": "generating", "job_id": job_id},
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
            "message": "Document generation retry queued",
            "document_id": document_id,
            "job_id": job_id,
            "status": "queued",
            "check_url": f"/api/v1/jobs/{job_id}/status",
        }
    except APIException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
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

        file_path = document.docx_path or document.pdf_path
        if not file_path:
            raise APIException(
                detail="Document delivery file is not available",
                status_code=409,
                error_code="FILE_NOT_READY",
            )
        file_format = "docx" if str(file_path).endswith(".docx") else "pdf"
        expected_sha256 = str(
            (document.docx_sha256 if file_format == "docx" else document.pdf_sha256)
            or ""
        )
        if len(expected_sha256) != 64:
            raise APIException(
                detail="Document artifact fingerprint is not available",
                status_code=409,
                error_code="FILE_NOT_READY",
            )
        try:
            actual_sha256 = await StorageService().get_file_sha256(str(file_path))
        except Exception as error:
            raise APIException(
                detail="Document delivery file is not available",
                status_code=409,
                error_code="FILE_NOT_READY",
            ) from error
        if not hmac.compare_digest(actual_sha256, expected_sha256):
            raise APIException(
                detail="Stored document differs from the generated artifact",
                status_code=409,
                error_code="FILE_NOT_READY",
            )

        # Internal-review scope is issued only after admin authorization and
        # audit above; it intentionally permits pre-release Compilatio review.
        download_token = create_download_token(
            document_id=int(document.id),
            user_id=int(current_user.id),
            expiration_minutes=60,
            file_format=file_format,
            file_path=str(file_path),
            scope="internal_review",
            file_sha256=expected_sha256,
        )

        # Return document content (in production, this would be a signed URL or file download)
        return {
            "document_id": document_id,
            "title": document.title,
            "content": document.content,
            "download_url": f"/api/v1/documents/download/file?token={download_token}",
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
