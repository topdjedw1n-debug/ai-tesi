"""
AI generation endpoints
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import AIProviderError, NotFoundError, ValidationError
from app.middleware.rate_limit import rate_limit
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentOutline,
    DocumentProvenance,
    DocumentSection,
    DocumentSource,
    ProductionCase,
    ReleaseGateResult,
)
from app.models.payment import Payment
from app.schemas.document import (
    AsyncGenerationRequest,
    AsyncGenerationResponse,
    OutlineRequest,
    OutlineResponse,
    SectionRequest,
    SectionResponse,
)
from app.services.ai_service import AIService
from app.services.background_jobs import (  # noqa: F401 - legacy patch surface
    BackgroundJobService,
)
from app.services.cost_estimator import TOKENS_PER_PAGE, CostEstimator
from app.services.custom_requirements_service import combine_generation_requirements
from app.services.document_service import DocumentService
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_worker import (
    cancel_active_generation_job,
    clear_artifact_deletion_entries,
    enqueue_artifact_deletions,
)
from app.services.grammar_checker import GrammarChecker
from app.services.plagiarism_checker import PlagiarismChecker
from app.services.storage_service import StorageService
from app.services.uploaded_sources import uploaded_sources_digest

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_legacy_generation_enabled() -> None:
    if not settings.LEGACY_GENERATION_ENDPOINTS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This generation path is disabled; use full-document generation.",
        )


async def _get_active_generation_job(
    db: AsyncSession, document_id: int, job_type: str = "full_document"
) -> AIGenerationJob | None:
    """Return the single active job protected by the database constraint."""
    result = await db.execute(
        select(AIGenerationJob).where(
            AIGenerationJob.document_id == document_id,
            AIGenerationJob.job_type == job_type,
            AIGenerationJob.status.in_(["queued", "running"]),
        )
    )
    return result.scalar_one_or_none()


def _active_job_response(job: AIGenerationJob) -> AsyncGenerationResponse:
    return AsyncGenerationResponse(
        job_id=int(job.id),
        status=str(job.status),
        check_url=f"/api/v1/jobs/{job.id}/status",
    )


@router.post("/outline", response_model=OutlineResponse)
@rate_limit("10/hour")
async def generate_outline(
    request: Request,
    outline_request: OutlineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutlineResponse:
    """Generate document outline using AI"""
    _require_legacy_generation_enabled()
    try:
        ai_service = AIService(db)
        result = await ai_service.generate_outline(
            document_id=outline_request.document_id,
            user_id=int(current_user.id),
            additional_requirements=outline_request.additional_requirements,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except AIProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outline",
        ) from None


@router.post("/section", response_model=SectionResponse)
@rate_limit("10/hour")
async def generate_section(
    request: Request,
    section_request: SectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SectionResponse:
    """Generate a specific section using AI"""
    _require_legacy_generation_enabled()
    try:
        ai_service = AIService(db)
        result = await ai_service.generate_section(
            document_id=section_request.document_id,
            section_title=section_request.section_title,
            section_index=section_request.section_index,
            user_id=int(current_user.id),
            additional_requirements=section_request.additional_requirements,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except AIProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate section",
        ) from None


@router.get("/models")
async def list_available_models() -> dict[str, list[dict[str, Any]]]:
    """List available AI models"""
    return {
        "openai": [
            {"id": "gpt-5.5", "name": "GPT-5.5", "max_tokens": 8000},
            {"id": "gpt-4", "name": "GPT-4", "max_tokens": 4000},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "max_tokens": 8000},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "max_tokens": 4000},
        ],
        "anthropic": [
            {
                "id": "claude-opus-4-8",
                "name": "Claude Opus 4.8",
                "max_tokens": 4000,
            },
            {
                "id": "claude-sonnet-5",
                "name": "Claude Sonnet 5",
                "max_tokens": 4000,
            },
            {
                "id": "claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "max_tokens": 4000,
            },
            {
                "id": "claude-3-opus-20240229",
                "name": "Claude 3 Opus",
                "max_tokens": 4000,
            },
        ],
    }


@router.get("/usage/{user_id}")
async def get_user_usage(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get AI usage statistics for a user"""
    try:
        # Enforce authorization: users can only view their own usage
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view this user's usage",
            )

        ai_service = AIService(db)
        result = await ai_service.get_user_usage(user_id)
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage statistics",
        ) from None


@router.get("/estimate-cost")
async def estimate_cost(
    provider: str,
    model: str,
    target_pages: int,
    include_rag: bool = True,
    include_humanization: bool = False,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Estimate cost for document generation before starting

    Args:
        provider: AI provider ("openai" or "anthropic")
        model: Model name
        target_pages: Target number of pages
        include_rag: Whether RAG is enabled
        include_humanization: Whether humanization is enabled
    """
    try:
        cost_estimate = CostEstimator.estimate_document_cost(
            provider=provider,
            model=model,
            target_pages=target_pages,
            include_rag=include_rag,
            include_humanization=include_humanization,
        )
        return cost_estimate
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to estimate cost: {str(e)}",
        ) from e


class PlagiarismCheckRequest(BaseModel):
    """Request schema for plagiarism check"""

    text: str = Field(
        ...,
        min_length=10,
        max_length=50_000,
        description="Text to check for plagiarism (maximum 50,000 characters)",
    )


@router.post("/check-plagiarism")
@rate_limit("5/hour")
async def check_plagiarism(
    http_request: Request,
    request: PlagiarismCheckRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Check text for plagiarism using Copyscape API

    Args:
        request: Plagiarism check request with text
    """
    try:
        checker = PlagiarismChecker()
        result = await checker.check_text(request.text)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check plagiarism: {str(e)}",
        ) from e


class GrammarCheckRequest(BaseModel):
    """Request schema for grammar check"""

    text: str = Field(
        ..., min_length=10, description="Text to check for grammar errors"
    )
    language: str = Field(
        default="en-US", description="Language code (e.g., en-US, uk-UA)"
    )


@router.post("/check-grammar")
async def check_grammar(
    request: GrammarCheckRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Check text for grammar and spelling errors using LanguageTool API

    Args:
        request: Grammar check request with text and language
    """
    try:
        # Same preprocessing as the pipeline quality gate: strip citation
        # anchors so a manual check reports the score the gate recorded.
        from app.services.background_jobs import strip_citation_anchors

        checker = GrammarChecker()
        result = await checker.check_text(
            strip_citation_anchors(request.text), request.language
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check grammar: {str(e)}",
        ) from e


async def _enforce_generation_gate(
    db: AsyncSession, document: Document, user_id: int
) -> None:
    """Gate full-document generation (Stage 0: fix MVP scope & disable sales).

    Sales mode (``MVP_FREE_GENERATION_ENABLED=False``): a completed payment for
    the document is required, otherwise ``402``. Free MVP mode (``=True``):
    generation runs without Stripe but is bounded by a page cap (``400``), a
    per-user daily generation quota (``429``), and the daily token budget
    (``429``). Raises ``HTTPException`` when a guardrail is hit; returns ``None``
    when generation is allowed.
    """
    if settings.METHODOLOGY_REQUIRED_FOR_GENERATION:
        if not document.requirements_file_processed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A university methodology file must be uploaded and "
                    "processed before generation can start."
                ),
            )
        if str(document.citation_style or "apa").lower() != "apa":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The current Italian MVP supports APA citations only. "
                    "Create an APA document before generation."
                ),
            )

    if not settings.MVP_FREE_GENERATION_ENABLED:
        payment_result = await db.execute(
            select(Payment.id).where(
                Payment.document_id == document.id,
                Payment.status == "completed",
            )
        )
        if payment_result.first() is None:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Payment required before generation can start.",
            )
        return

    target_pages = document.target_pages or 0
    if target_pages > settings.MVP_FREE_GENERATION_MAX_PAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Free generation is limited to "
                f"{settings.MVP_FREE_GENERATION_MAX_PAGES} pages "
                f"(document requests {target_pages})."
            ),
        )

    # UTC day boundary: started_at is written with utcnow(), so "today" must
    # be the UTC date too. date.today() (local) silently reset the daily
    # quota at local midnight — a 3h window (Kyiv) where the cap didn't count
    # today's UTC jobs (caught by the quota tests run just after midnight).
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())

    jobs_today_result = await db.execute(
        select(func.count(AIGenerationJob.id)).where(
            AIGenerationJob.user_id == user_id,
            AIGenerationJob.started_at >= today_start,
        )
    )
    jobs_today = jobs_today_result.scalar() or 0
    if jobs_today >= settings.MVP_FREE_GENERATION_DAILY_USER_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Daily free-generation limit reached "
                f"({settings.MVP_FREE_GENERATION_DAILY_USER_LIMIT} per day)."
            ),
        )

    if settings.DAILY_TOKEN_LIMIT is not None:
        tokens_today_result = await db.execute(
            select(func.coalesce(func.sum(AIGenerationJob.total_tokens), 0)).where(
                AIGenerationJob.user_id == user_id,
                AIGenerationJob.started_at >= today_start,
            )
        )
        tokens_today = tokens_today_result.scalar() or 0

        active_reservations_result = await db.execute(
            select(
                Document.target_pages,
                func.coalesce(AIGenerationJob.total_tokens, 0),
            )
            .select_from(AIGenerationJob)
            .join(Document, AIGenerationJob.document_id == Document.id)
            .where(
                AIGenerationJob.user_id == user_id,
                AIGenerationJob.started_at >= today_start,
                AIGenerationJob.status.in_(["queued", "running"]),
            )
        )
        # Actual usage is already included in tokens_today. Keep reserving the
        # unspent remainder of every active job; otherwise its reservation
        # vanished after the first token write and parallel documents could
        # oversubscribe the daily budget.
        active_remaining_tokens = sum(
            max(
                int(target_pages or 0) * TOKENS_PER_PAGE - int(tokens_used or 0),
                0,
            )
            for target_pages, tokens_used in active_reservations_result.all()
        )

        projected_tokens = target_pages * TOKENS_PER_PAGE
        if (
            tokens_today + active_remaining_tokens + projected_tokens
            > settings.DAILY_TOKEN_LIMIT
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily token budget exhausted; try again tomorrow.",
            )


async def _invalidate_previous_generation_evidence(
    db: AsyncSession,
    document_id: int,
    *,
    contract_sha256: str | None = None,
) -> list[str]:
    """Revoke old DB evidence and return blobs to delete after commit.

    Object storage is deliberately not mutated inside this SQL transaction:
    a later flush/commit failure can roll SQL back, but cannot undelete a blob.
    """
    document = (
        await db.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    superseded_paths = (
        [str(path) for path in (document.docx_path, document.pdf_path) if path]
        if document is not None
        else []
    )
    # Durable deletion intent in the SAME transaction that supersedes the
    # blobs: if the post-commit best-effort delete fails or never runs, the
    # worker sweep retries until storage confirms (audit 2026-07-10).
    await enqueue_artifact_deletions(db, superseded_paths, reason="superseded")
    await db.execute(
        update(ProductionCase)
        .where(ProductionCase.document_id == document_id)
        .values(
            release_status="blocked",
            delivery_status="not_ready",
            editorial_status="not_started",
            released_at=None,
            released_docx_path=None,
            released_pdf_path=None,
            released_docx_sha256=None,
            released_pdf_sha256=None,
        )
    )
    await db.execute(
        delete(DocumentSource).where(DocumentSource.document_id == document_id)
    )
    case_ids = select(ProductionCase.id).where(
        ProductionCase.document_id == document_id
    )
    await db.execute(
        delete(ReleaseGateResult).where(
            ReleaseGateResult.production_case_id.in_(case_ids)
        )
    )
    await db.execute(
        delete(DocumentSection).where(DocumentSection.document_id == document_id)
    )
    await db.execute(
        delete(DocumentOutline).where(DocumentOutline.document_id == document_id)
    )
    await db.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(
            outline=None,
            content=None,
            docx_path=None,
            pdf_path=None,
            docx_sha256=None,
            pdf_sha256=None,
            completed_at=None,
        )
    )
    db.add(
        DocumentProvenance(
            document_id=document_id,
            stage="generation",
            event_type="generation_run_started",
            payload={
                "started_at": datetime.utcnow().isoformat(),
                "generation_contract_sha256": contract_sha256,
            },
        )
    )
    return superseded_paths


async def _delete_superseded_artifacts(paths: list[str]) -> None:
    """Immediate post-commit cleanup attempt.

    Every path here is already enqueued in artifact_deletion_outbox by
    _invalidate_previous_generation_evidence, so a failure needs no handling
    beyond the log — the worker sweep retries until storage confirms.
    Confirmed deletions clear their outbox rows so the sweep stays empty.
    """
    if not paths:
        return
    storage = StorageService()
    deleted: list[str] = []
    for path in dict.fromkeys(paths):
        try:
            if await storage.delete_file(path):
                deleted.append(path)
        except Exception:
            logger.exception(
                "Deferred cleanup failed for superseded artifact %s "
                "(outbox will retry)",
                path,
            )
    if deleted:
        try:
            async with database.AsyncSessionLocal() as db:
                await clear_artifact_deletion_entries(db, deleted)
        except Exception:
            # Harmless: the sweep re-deletes an absent object (S3 semantics)
            # and clears the row itself.
            logger.exception("Failed to clear deletion outbox entries")


@router.post("/full-document", response_model=AsyncGenerationResponse)
@rate_limit("5/hour")  # Stricter limit for full document generation
async def generate_full_document(
    request: Request,
    req_data: AsyncGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerationResponse:
    """
    Generate complete document with RAG (Retrieval-Augmented Generation)

    This endpoint:
    1. Validates document ownership and readiness
    2. Checks payment status (document must be paid)
    3. Creates AIGenerationJob with status 'queued'
    4. Starts background generation with RAG retrieval
    5. Returns job_id for status tracking via WebSocket

    Args:
        request: Generation request with document_id
        background_tasks: FastAPI background tasks
        current_user: Authenticated user
        db: Database session

    Returns:
        AsyncGenerationResponse with job_id and status

    Raises:
        404: Document not found
        403: User doesn't own document
        400: Document not ready (not paid, already generating, etc.)
    """
    try:
        # 1. Check document exists and user owns it
        doc_service = DocumentService(db)
        await doc_service.check_document_ownership(
            req_data.document_id, int(current_user.id)
        )

        # 2. Serialize every daily-quota decision for this user, including jobs
        # for different documents. The lock is held through the gate check,
        # job insert, and commit, so the queued job becomes the reservation
        # observed by the next request. User is the first row in the global
        # lock order: user -> document -> production case -> generation job.
        user_lock_result = await db.execute(
            select(User)
            .where(User.id == int(current_user.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        locked_user = user_lock_result.scalar_one_or_none()
        if locked_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account no longer exists.",
            )
        # GDPR deletion and generation share this user lock. Once deletion is
        # requested, no new durable work may be queued behind it.
        if getattr(locked_user, "deletion_requested_at", None) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generation cannot start while account deletion is pending.",
            )

        # Lock the document before looking up its optional production case.
        # The document row always exists, so it serializes generation against
        # case creation even when no case row exists yet. Case creation uses
        # the same document -> case order.
        result = await db.execute(
            select(Document)
            .where(Document.id == req_data.document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )

        # Re-read the case only after the document lock is held. If case
        # creation won the document lock, its requirements are committed and
        # visible here; if generation won, creation waits and is then rejected
        # while this job is active instead of silently missing requirements.
        case_result = await db.execute(
            select(ProductionCase)
            .where(ProductionCase.document_id == req_data.document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        production_case = case_result.scalar_one_or_none()

        # 3. Make repeated/concurrent requests idempotent. This check must run
        # before the document-status guard because the winning transaction
        # sets the document to "generating" when it creates the job.
        existing_job = await _get_active_generation_job(db, req_data.document_id)
        if existing_job:
            logger.info(
                f"Returning existing job {existing_job.id} for document {req_data.document_id}"
            )
            return _active_job_response(existing_job)

        if production_case is None:
            # Every new deliverable run needs a case that predates its artifact.
            # The active-job check above prevents this from retroactively
            # attaching a case to work that already started.
            production_case = ProductionCase(
                document_id=int(document.id),
                client_user_id=int(document.user_id),
                citation_style=str(document.citation_style or "apa"),
                generation_status="not_started",
                payment_status="not_required",
            )
            db.add(production_case)
            await db.flush()

        generation_requirements = req_data.requirements
        if production_case is not None:
            generation_requirements = combine_generation_requirements(
                production_case.requirements_text,
                req_data.requirements,
            )
            if production_case.citation_style:
                case_style = str(production_case.citation_style).strip().lower()
                if case_style not in {"apa", "apa-7"}:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="The current Italian MVP supports APA citations only.",
                    )
                document.citation_style = "apa"

        # 4. Validate document is ready for generation
        if document.status == "generating":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is already being generated",
            )

        if document.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document already completed. Create new document for regeneration.",
            )

        # 5. Enforce the MVP free-generation / payment gate before any job exists
        await _enforce_generation_gate(db, document, int(current_user.id))

        # A new run invalidates every prior release and citation association.
        # Otherwise a regenerated file could inherit the previous review, or
        # stale sources could make a zero-citation retry look verified.
        contract_sha256 = generation_contract_sha256(
            document,
            production_case,
            generation_requirements,
            await uploaded_sources_digest(db, req_data.document_id),
        )
        superseded_paths = await _invalidate_previous_generation_evidence(
            db,
            req_data.document_id,
            contract_sha256=contract_sha256,
        )

        # 6. Create new generation job
        job = AIGenerationJob(
            user_id=int(current_user.id),
            document_id=req_data.document_id,
            job_type="full_document",
            ai_provider=document.ai_provider,
            ai_model=req_data.model or document.ai_model,
            status="queued",
            progress=0,
            request_payload={
                "additional_requirements": generation_requirements,
                "generation_contract_sha256": contract_sha256,
                "superseded_artifact_paths": superseded_paths,
            },
            max_attempts=settings.GENERATION_JOB_MAX_ATTEMPTS,
        )
        db.add(job)
        try:
            await db.flush()  # Get job.id before commit
        except IntegrityError:
            # Another transaction can win after the optimistic lookup (for
            # example, a future recovery worker). The partial unique index is
            # the final arbiter. Roll back the failed insert, then return the
            # winner instead of surfacing a misleading 500 to the caller.
            await db.rollback()
            existing_job = await _get_active_generation_job(db, req_data.document_id)
            if existing_job is None:
                raise
            logger.info(
                "Generation race resolved with existing job %s for document %s",
                existing_job.id,
                req_data.document_id,
            )
            return _active_job_response(existing_job)

        # 7. Update document status
        document.status = "generating"

        # 8. Commit transaction before starting background task
        await db.commit()

        # The new job and release revocation are now durable. Blob cleanup can
        # no longer leave SQL pointing at a file that was rolled back into use.
        await _delete_superseded_artifacts(superseded_paths)

        logger.info(
            f"Created generation job {job.id} for document {req_data.document_id}"
        )

        # 9. Do not attach execution to this web process. The committed row is
        # the durable queue item; any API worker may lease it after this request
        # returns, and a later worker may resume it after a restart.

        return AsyncGenerationResponse(
            job_id=int(job.id),
            status="queued",
            check_url=f"/api/v1/jobs/{job.id}/status",
        )

    except HTTPException:
        raise
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error(
            f"Failed to start document generation: {e}",
            exc_info=True,
            extra={"document_id": req_data.document_id, "user_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start document generation",
        ) from e


@router.post("/full-document/{document_id}/cancel")
@rate_limit("30/hour")
async def cancel_full_document_generation(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Terminally cancel the active generation job for an owned document.

    The job flips to `cancelled` and its lease token is cleared, so the
    running executor loses every subsequent fenced write and the worker
    never re-claims the row. The document becomes `failed` (retryable via
    admin retry); any releasable snapshot is revoked fail-closed.
    """
    try:
        doc_service = DocumentService(db)
        await doc_service.check_document_ownership(document_id, int(current_user.id))

        job_id = await cancel_active_generation_job(
            db,
            document_id=document_id,
            cancelled_by=f"user:{current_user.id}",
        )
        if job_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No active generation job to cancel",
            )
        return {
            "job_id": job_id,
            "status": "cancelled",
            "document_status": "failed",
        }
    except HTTPException:
        raise
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error(
            f"Failed to cancel document generation: {e}",
            exc_info=True,
            extra={"document_id": document_id, "user_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel document generation",
        ) from e
