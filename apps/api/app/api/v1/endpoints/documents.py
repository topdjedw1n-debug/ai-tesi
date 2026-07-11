"""
Document management endpoints
"""

import hmac
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, verify_download_token
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import create_download_token
from app.middleware.rate_limit import rate_limit
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    DocumentSourceFile,
    ProductionCase,
    SourceFilePage,
)
from app.schemas.document import (
    DocumentCreate,
    DocumentFeedbackRequest,
    DocumentFeedbackResponse,
    DocumentListResponse,
    DocumentProvenanceResponse,
    DocumentResponse,
    DocumentUpdate,
    ExportRequest,
    ExportResponse,
    ProvenanceEventResponse,
)
from app.services import uploaded_sources
from app.services.custom_requirements_service import CustomRequirementsService
from app.services.document_service import DocumentService
from app.services.production_case_service import (
    ProductionCaseService,
    revoke_release,
)
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter()  # 307 redirect for trailing slash is standard REST API behavior


def _mask_unreleased_content(result: dict[str, Any]) -> dict[str, Any]:
    if (
        result.get("release_status") == "released"
        and result.get("status") == "completed"
    ):
        return result
    for section in result.get("sections") or []:
        section["content"] = None
    result["content"] = None
    return result


async def _require_released_production_case(
    db: AsyncSession, document_id: int
) -> ProductionCase:
    """Fail closed unless the document has passed the production release gate."""
    result = await db.execute(
        select(ProductionCase).where(ProductionCase.document_id == document_id)
    )
    production_case = result.scalar_one_or_none()
    if production_case is None or production_case.release_status != "released":
        logger.warning(
            "Document delivery blocked: document_id=%s, release_status=%s",
            document_id,
            (
                production_case.release_status
                if production_case is not None
                else "missing_production_case"
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document has not been released for delivery",
        )

    gates = await ProductionCaseService(db).get_release_gates(int(production_case.id))
    blockers = [
        gate
        for gate in gates
        if gate["blocking"]
        and gate["status"] in {"failed", "no_data", "unchecked", "warning"}
        and gate.get("override_reason") is None
    ]
    if blockers:
        revoke_release(production_case)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document release evidence is no longer current",
        )
    return production_case


async def _require_released_artifact(
    db: AsyncSession,
    document: Document,
    file_format: str,
) -> tuple[str, ProductionCase]:
    production_case = await _require_released_production_case(db, int(document.id))
    if document.status != "completed":
        revoke_release(production_case)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is no longer in a completed delivery state",
        )
    released_path = (
        production_case.released_docx_path
        if file_format == "docx"
        else production_case.released_pdf_path
    )
    current_path = document.docx_path if file_format == "docx" else document.pdf_path
    released_sha256 = (
        production_case.released_docx_sha256
        if file_format == "docx"
        else production_case.released_pdf_sha256
    )
    current_sha256 = (
        document.docx_sha256 if file_format == "docx" else document.pdf_sha256
    )
    if not released_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No reviewed {file_format.upper()} artifact is available",
        )
    if (
        str(current_path or "") != str(released_path)
        or not released_sha256
        or not current_sha256
        or not hmac.compare_digest(str(current_sha256), str(released_sha256))
    ):
        revoke_release(production_case)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The reviewed delivery artifact is no longer current",
        )
    storage = StorageService()
    try:
        actual_sha256 = await storage.get_file_sha256(str(released_path))
    except Exception:
        actual_sha256 = None
    if not actual_sha256 or not hmac.compare_digest(
        actual_sha256, str(released_sha256)
    ):
        revoke_release(production_case)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The released delivery file is missing from storage",
        )
    return str(released_path), production_case


async def _delivery_response(
    db: AsyncSession,
    document: Document,
    user_id: int,
    file_format: str,
) -> dict[str, Any]:
    file_path, production_case = await _require_released_artifact(
        db, document, file_format
    )
    storage = StorageService()
    file_size = await storage.get_file_size(file_path)
    download_token = create_download_token(
        document_id=int(document.id),
        user_id=user_id,
        expiration_minutes=60,
        file_format=file_format,
        file_path=file_path,
        release_version=int(production_case.release_version),
        file_sha256=str(production_case.released_docx_sha256)
        if file_format == "docx"
        else str(production_case.released_pdf_sha256),
    )
    return {
        "download_url": f"/api/v1/documents/download/file?token={download_token}",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "file_size": file_size,
        "format": file_format,
    }


@router.post("/", response_model=DocumentResponse)
@rate_limit("100/hour")
async def create_document(
    request: Request,
    document: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Create a new document"""
    try:
        document_service = DocumentService(db)
        result = await document_service.create_document(
            user_id=int(current_user.id),
            title=document.title,
            topic=document.topic,
            language=document.language,
            target_pages=document.target_pages,
            ai_provider=(
                document.ai_provider.value if document.ai_provider else "anthropic"
            ),
            ai_model=document.ai_model or "claude-opus-4-8",
            additional_requirements=document.additional_requirements,
            citation_style=document.citation_style,
        )
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create document",
        ) from None


@router.get("/", response_model=DocumentListResponse)
@rate_limit("100/hour")
async def list_documents(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List user's documents with pagination"""
    try:
        document_service = DocumentService(db)
        result = await document_service.get_user_documents(
            user_id=int(current_user.id), limit=limit, offset=offset
        )
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents",
        ) from None


@router.get("/activity")
@rate_limit("100/hour")
async def get_recent_activity(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    """Get recent activity for user dashboard"""
    try:
        document_service = DocumentService(db)
        activities = await document_service.get_recent_activity(
            int(current_user.id), limit=limit
        )
        return {"activities": activities}
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recent activity",
        ) from None


@router.get("/stats")
@rate_limit("100/hour")
async def get_user_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get user statistics for dashboard"""
    try:
        document_service = DocumentService(db)
        stats = await document_service.get_user_stats(int(current_user.id))
        return stats
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user stats",
        ) from None


@router.get("/{document_id}", response_model=DocumentResponse)
@rate_limit("100/hour")
async def get_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get a specific document by ID"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(
            document_id, int(current_user.id)
        )
        result = await document_service.get_document(document_id, int(current_user.id))
        if not result:
            raise NotFoundError("Document not found")
        return _mask_unreleased_content(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document",
        ) from None


@router.put("/{document_id}", response_model=DocumentResponse)
@rate_limit("100/hour")
async def update_document(
    request: Request,
    document_id: int,
    document: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Update a document"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(
            document_id, int(current_user.id)
        )
        # Convert Pydantic model to dict and unpack
        update_dict = document.model_dump(exclude_unset=True)
        await document_service.update_document(
            document_id, int(current_user.id), **update_dict
        )
        # Fetch updated document to return
        result = await document_service.get_document(document_id, int(current_user.id))
        return _mask_unreleased_content(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        # e.g. metadata of a generated document is locked; the client must
        # see the reason, not a generic 500
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document",
        ) from None


@router.delete("/{document_id}")
@rate_limit("100/hour")
async def delete_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a document (soft delete)"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(
            document_id, int(current_user.id)
        )
        success = await document_service.delete_document(
            document_id, int(current_user.id)
        )
        if not success:
            raise NotFoundError("Document not found")
        return {"message": "Document deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        ) from None


@router.get("/{document_id}/provenance", response_model=DocumentProvenanceResponse)
@rate_limit("100/hour")
async def get_document_provenance(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentProvenanceResponse:
    """
    Chronological provenance ledger for a document.

    Returns every pipeline event (rag_retrieved, section_generated, humanized,
    quality_gate, citation_gate, exported, ...) in the order they occurred.
    Access: document owner or admin (403 otherwise).
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if document.user_id != int(current_user.id) and not current_user.is_admin:
        logger.warning(
            f"PROVENANCE_ACCESS_DENIED: user_id={current_user.id}, "
            f"document_id={document_id}, owner_id={document.user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    events_result = await db.execute(
        select(DocumentProvenance)
        .where(DocumentProvenance.document_id == document_id)
        .order_by(
            DocumentProvenance.created_at.asc(),
            DocumentProvenance.id.asc(),
        )
    )
    events = events_result.scalars().all()

    return DocumentProvenanceResponse(
        document_id=document_id,
        total=len(events),
        events=[ProvenanceEventResponse.model_validate(event) for event in events],
    )


@router.post(
    "/{document_id}/feedback",
    response_model=DocumentFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
@rate_limit("30/hour")
async def submit_document_feedback(
    request: Request,
    document_id: int,
    feedback: DocumentFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentFeedbackResponse:
    """
    Record manager feedback on a document (internal MVP).

    Stored as a provenance event (stage="feedback") so it lands in the same
    append-only ledger the admin already reads — no extra table needed.
    Access: document owner or admin.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if document.user_id != int(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    event = DocumentProvenance(
        document_id=document_id,
        stage="feedback",
        event_type="manager_feedback",
        payload={
            "text": feedback.text,
            "author_id": int(current_user.id),
            "author_email": current_user.email,
        },
    )
    db.add(event)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback",
        ) from None
    await db.refresh(event)

    return DocumentFeedbackResponse(
        document_id=document_id,
        event_id=int(event.id),
        created_at=event.created_at,
    )


@router.post("/{document_id}/export", response_model=ExportResponse)
@rate_limit("100/hour")
async def export_document(
    request: Request,
    document_id: int,
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """Export document to DOCX or PDF"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        document = await document_service.check_document_ownership(
            document_id, int(current_user.id)
        )
        return await _delivery_response(
            db,
            document,
            int(current_user.id),
            export_request.format,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export document",
        ) from None


@router.get("/{document_id}/export/{format}", response_model=ExportResponse)
@rate_limit("100/hour")
async def export_document_get(
    request: Request,
    document_id: int,
    format: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """Export document via GET route to match frontend: /documents/{id}/export/{format}"""
    try:
        if format not in {"docx", "pdf"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Export format must be docx or pdf",
            )
        document_service = DocumentService(db)
        # Check ownership using helper function
        document = await document_service.check_document_ownership(
            document_id, int(current_user.id)
        )
        return await _delivery_response(
            db,
            document,
            int(current_user.id),
            format,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export document",
        ) from None


@router.post("/{document_id}/custom-requirements/upload")
@rate_limit("10/hour")
async def upload_custom_requirements(
    request: Request,
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Upload custom requirements file (PDF, DOCX, TXT)
    Extracts text from the file and stores it
    """
    try:
        # Parse first, then use the global document -> production-case lock order.
        # generation and release. The state check happens under those locks so
        # a run cannot start while a methodology change is being persisted.
        requirements_service = CustomRequirementsService()
        extracted_text = await requirements_service.extract_text(file)

        user_result = await db.execute(
            select(User)
            .where(User.id == int(current_user.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        locked_user = user_result.scalar_one_or_none()
        if locked_user is None or not locked_user.is_active:
            raise NotFoundError("User account not found")
        if locked_user.deletion_requested_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account deletion is pending; requirements cannot be changed",
            )

        document_result = await db.execute(
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        document = document_result.scalar_one_or_none()
        if document is None or document.user_id != int(current_user.id):
            raise NotFoundError("Document not found")
        case_result = await db.execute(
            select(ProductionCase)
            .where(ProductionCase.document_id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        production_case = case_result.scalar_one_or_none()

        active_job_result = await db.execute(
            select(AIGenerationJob.id).where(
                AIGenerationJob.document_id == document_id,
                AIGenerationJob.status.in_(["queued", "running"]),
            )
        )
        if document.status == "generating" or active_job_result.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Requirements cannot change while generation is running",
            )

        document.additional_requirements = requirements_service.merge_with_existing(
            document.additional_requirements, extracted_text
        )
        document.requirements_file_processed = True
        # New requirements invalidate any old review. The old binary may stay
        # in storage for internal history, but it is no longer deliverable and
        # the next run must rebuild the thesis under the changed methodology.
        if document.status not in {"draft", "payment_pending", "payment_failed"}:
            document.status = "draft"
            document.completed_at = None
        if production_case is not None:
            revoke_release(production_case)
            production_case.generation_status = "not_started"
            production_case.qa_status = "no_data"
            production_case.editorial_status = "not_started"
        await db.commit()

        logger.info(
            "Persisted %s extracted requirements characters for document %s",
            len(extracted_text),
            document_id,
        )

        return {
            "message": "Custom requirements file uploaded and processed successfully",
            "document_id": document_id,
            "file_size": len(extracted_text),
            "preview": (
                extracted_text[:500] if len(extracted_text) > 500 else extracted_text
            ),
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process custom requirements file: {str(e)}",
        ) from e


@router.get("/download/file")
async def download_document_secure(
    token: str = Query(..., description="Signed download token"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Secure document download endpoint with JWT token validation.

    Token must contain document_id and user_id claims.
    Only the document owner can download.
    """
    try:
        # Verify token and extract claims
        payload = verify_download_token(token)
        document_id = int(payload["document_id"])
        user_id = int(payload["user_id"])
        token_scope = str(payload.get("scope") or "client_delivery")
        file_format = str(payload.get("file_format") or "")
        token_file_path = str(payload.get("file_path") or "")
        token_file_sha256 = str(payload.get("file_sha256") or "")
        if (
            file_format not in {"docx", "pdf"}
            or not token_file_path
            or len(token_file_sha256) != 64
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Download token is not bound to a delivery artifact",
            )

        # Query the model directly: the regular document service returns a
        # serialized dictionary, while secure download needs storage fields.
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )

        current_path = (
            str(document.docx_path or "")
            if file_format == "docx"
            else str(document.pdf_path or "")
        )
        if current_path != token_file_path:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The signed artifact is no longer current",
            )

        if token_scope == "internal_review":
            file_path = token_file_path
            expected_sha256 = str(
                (document.docx_sha256 if file_format == "docx" else document.pdf_sha256)
                or ""
            )
        elif token_scope == "client_delivery":
            # Verify ownership (CRITICAL security check)
            if document.user_id != user_id:
                logger.warning(
                    f"SECURITY: Download attempt with mismatched ownership. "
                    f"Token user_id={user_id}, Document user_id={document.user_id}, "
                    f"Document ID={document_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )
            file_path, production_case = await _require_released_artifact(
                db, document, file_format
            )
            if int(payload.get("release_version", -1)) != int(
                production_case.release_version
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Download token belongs to an earlier release",
                )
            expected_sha256 = str(
                (
                    production_case.released_docx_sha256
                    if file_format == "docx"
                    else production_case.released_pdf_sha256
                )
                or ""
            )
        else:
            logger.warning(
                "SECURITY: Download attempt with unknown scope %s", token_scope
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid download scope"
            )

        if not expected_sha256 or not hmac.compare_digest(
            token_file_sha256, expected_sha256
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The signed artifact fingerprint is no longer current",
            )

        # Initialize StorageService
        storage_service = StorageService()
        try:
            actual_sha256 = await storage_service.get_file_sha256(file_path)
        except Exception:
            actual_sha256 = None
        if not actual_sha256 or not hmac.compare_digest(actual_sha256, expected_sha256):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Delivery file is missing or differs from the reviewed artifact",
            )

        if file_format == "docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            file_extension = ".docx"
        else:
            media_type = "application/pdf"
            file_extension = ".pdf"

        logger.info(
            f"Document download: user_id={user_id}, document_id={document_id}, "
            f"file_path={file_path}"
        )

        # Stream file from MinIO using StorageService
        file_stream = storage_service.download_file_stream(file_path)

        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{document.title}{file_extension}"',
                "Cache-Control": "private, no-store",
                "Pragma": "no-cache",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document",
        ) from e


def _reset_document_after_input_change(
    document: Document, production_case: ProductionCase | None
) -> None:
    """Changed grounding inputs invalidate any generated/released state —
    identical semantics to a methodology change."""
    if document.status not in {"draft", "payment_pending", "payment_failed"}:
        document.status = "draft"
        document.completed_at = None
    if production_case is not None:
        revoke_release(production_case)
        production_case.generation_status = "not_started"
        production_case.qa_status = "no_data"
        production_case.editorial_status = "not_started"


async def _lock_document_for_source_change(
    db: AsyncSession, document_id: int, user_id: int
) -> tuple[Document, ProductionCase | None]:
    """User -> Document -> ProductionCase locks + the active-generation guard
    shared by every uploaded-source mutation."""
    user_result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    locked_user = user_result.scalar_one_or_none()
    if locked_user is None or not locked_user.is_active:
        raise NotFoundError("User account not found")
    if locked_user.deletion_requested_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account deletion is pending; sources cannot be changed",
        )
    document_result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    document = document_result.scalar_one_or_none()
    if document is None or document.user_id != user_id:
        raise NotFoundError("Document not found")
    case_result = await db.execute(
        select(ProductionCase)
        .where(ProductionCase.document_id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    production_case = case_result.scalar_one_or_none()
    active_job_result = await db.execute(
        select(AIGenerationJob.id).where(
            AIGenerationJob.document_id == document_id,
            AIGenerationJob.status.in_(["queued", "running"]),
        )
    )
    if document.status == "generating" or active_job_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sources cannot change while generation is running",
        )
    return document, production_case


@router.post("/{document_id}/sources/upload")
@rate_limit("30/hour")
async def upload_source_file(
    request: Request,
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload one scientific PDF that must ground this document.

    The file is parsed page by page (no OCR: scans are stored but flagged
    and excluded from retrieval) and becomes part of the generation
    contract — swapping sources later invalidates the run and the release.
    """
    try:
        filename = (file.filename or "source.pdf").strip() or "source.pdf"
        if not filename.lower().endswith(".pdf"):
            raise ValidationError("Only PDF sources are supported")
        data = await file.read()
        if not data:
            raise ValidationError("Empty file")
        pages = uploaded_sources.extract_pdf_pages(data)
        digest = uploaded_sources.sha256_hex(data)

        document, production_case = await _lock_document_for_source_change(
            db, document_id, int(current_user.id)
        )

        duplicate = (
            await db.execute(
                select(DocumentSourceFile.id).where(
                    DocumentSourceFile.document_id == document_id,
                    DocumentSourceFile.sha256 == digest,
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This PDF is already uploaded for this document",
            )

        meta = uploaded_sources.derive_source_metadata(filename, data, pages)
        existing_keys = set(
            (
                await db.execute(
                    select(DocumentSourceFile.citation_key).where(
                        DocumentSourceFile.document_id == document_id
                    )
                )
            ).scalars()
        )
        citation_key = str(meta["citation_key"])
        if citation_key in existing_keys:
            for suffix in "bcdefghijklmnopqrstuvwxyz":
                candidate = f"{citation_key}{suffix}"
                if candidate not in existing_keys:
                    citation_key = candidate
                    break
            else:
                raise ValidationError("Too many sources with the same citation key")

        text_chars = sum(len(p) for p in pages)
        has_text_layer = pages and (
            text_chars / max(1, len(pages)) >= uploaded_sources.MIN_TEXT_CHARS_PER_PAGE
        )

        storage = StorageService()
        object_name = (
            f"documents/{int(current_user.id)}/{document_id}/sources/"
            f"{digest[:16]}.pdf"
        )
        storage_path = await storage.upload_file(
            object_name, data, content_type="application/pdf"
        )

        source_file = DocumentSourceFile(
            document_id=document_id,
            filename=filename[:255],
            citation_key=citation_key,
            title=str(meta["title"]) if meta["title"] else None,
            authors=str(meta["authors"]) if meta["authors"] else None,
            year=int(meta["year"]) if meta["year"] else None,
            storage_path=storage_path,
            sha256=digest,
            page_count=len(pages),
            text_chars=text_chars,
            status="parsed" if has_text_layer else "no_text_layer",
            metadata_incomplete=bool(meta["metadata_incomplete"]),
        )
        db.add(source_file)
        await db.flush()
        if has_text_layer:
            for page_number, text in enumerate(pages, start=1):
                if text.strip():
                    db.add(
                        SourceFilePage(
                            source_file_id=int(source_file.id),
                            page_number=page_number,
                            text=text,
                        )
                    )

        _reset_document_after_input_change(document, production_case)
        await db.commit()

        logger.info(
            "Uploaded source %s for document %s: %s pages, %s chars, status=%s",
            citation_key,
            document_id,
            len(pages),
            text_chars,
            source_file.status,
        )
        return {
            "id": int(source_file.id),
            "citation_key": citation_key,
            "filename": filename,
            "title": source_file.title,
            "authors": source_file.authors,
            "year": source_file.year,
            "page_count": len(pages),
            "status": source_file.status,
            "metadata_incomplete": bool(source_file.metadata_incomplete),
            "warning": (
                None
                if has_text_layer
                else "No text layer detected (scanned PDF?) — this source "
                "will not be used for grounding"
            ),
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (ValidationError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Source upload failed for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload source file",
        ) from e


@router.get("/{document_id}/sources/files")
async def list_source_files(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List the uploaded grounding sources of an owned document."""
    try:
        document_service = DocumentService(db)
        await document_service.check_document_ownership(
            document_id, int(current_user.id)
        )
        rows = (
            (
                await db.execute(
                    select(DocumentSourceFile)
                    .where(DocumentSourceFile.document_id == document_id)
                    .order_by(DocumentSourceFile.id.asc())
                )
            )
            .scalars()
            .all()
        )
        return {
            "files": [
                {
                    "id": int(row.id),
                    "citation_key": row.citation_key,
                    "filename": row.filename,
                    "title": row.title,
                    "authors": row.authors,
                    "year": row.year,
                    "page_count": int(row.page_count or 0),
                    "status": row.status,
                    "metadata_incomplete": bool(row.metadata_incomplete),
                }
                for row in rows
            ]
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete("/{document_id}/sources/files/{file_id}")
async def delete_source_file(
    document_id: int,
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove an uploaded source. Fail-closed: the blob must be confirmed
    deleted from storage before the rows go."""
    try:
        document, production_case = await _lock_document_for_source_change(
            db, document_id, int(current_user.id)
        )
        source_file = (
            await db.execute(
                select(DocumentSourceFile).where(
                    DocumentSourceFile.id == file_id,
                    DocumentSourceFile.document_id == document_id,
                )
            )
        ).scalar_one_or_none()
        if source_file is None:
            raise NotFoundError("Source file not found")

        storage = StorageService()
        if not await storage.delete_file(str(source_file.storage_path)):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Storage did not confirm deletion; source kept",
            )
        await db.delete(source_file)
        _reset_document_after_input_change(document, production_case)
        await db.commit()
        return {"message": "Source file deleted", "id": file_id}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Source delete failed for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete source file",
        ) from e


@router.patch("/{document_id}/sources/files/{file_id}")
async def update_source_metadata(
    document_id: int,
    file_id: int,
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Correct the citation metadata of an uploaded source.

    Honest bibliography needs real authors/year — the system never invents
    them, so incomplete files block generation until fixed here. Metadata
    is part of the generation contract: an edit invalidates any generated
    state exactly like swapping the file would.
    """
    try:
        document, production_case = await _lock_document_for_source_change(
            db, document_id, int(current_user.id)
        )
        source_file = (
            await db.execute(
                select(DocumentSourceFile).where(
                    DocumentSourceFile.id == file_id,
                    DocumentSourceFile.document_id == document_id,
                )
            )
        ).scalar_one_or_none()
        if source_file is None:
            raise NotFoundError("Source file not found")

        allowed = {"title", "authors", "year"}
        unknown = set(payload) - allowed
        if unknown:
            raise ValidationError(
                f"Unknown fields: {', '.join(sorted(unknown))}; "
                f"editable fields are title, authors, year"
            )
        if "title" in payload:
            title = str(payload["title"] or "").strip()
            if not 3 <= len(title) <= 500:
                raise ValidationError("title must be 3-500 characters")
            source_file.title = title
        if "authors" in payload:
            authors = str(payload["authors"] or "").strip()
            if not 3 <= len(authors) <= 500:
                raise ValidationError(
                    "authors must be 3-500 characters ('; '-separated)"
                )
            source_file.authors = authors
        if "year" in payload:
            try:
                year = int(payload["year"])
            except (TypeError, ValueError) as exc:
                raise ValidationError("year must be an integer") from exc
            if not 1900 <= year <= 2049:
                raise ValidationError("year must be between 1900 and 2049")
            source_file.year = year

        source_file.metadata_incomplete = not (
            str(source_file.authors or "").strip() and source_file.year
        )
        _reset_document_after_input_change(document, production_case)
        await db.commit()
        return {
            "id": int(source_file.id),
            "citation_key": source_file.citation_key,
            "title": source_file.title,
            "authors": source_file.authors,
            "year": source_file.year,
            "metadata_incomplete": bool(source_file.metadata_incomplete),
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Source metadata update failed for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update source metadata",
        ) from e
