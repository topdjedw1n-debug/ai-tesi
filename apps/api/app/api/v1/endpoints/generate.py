"""
AI generation endpoints
"""

import logging
from collections.abc import Callable
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
    GenerationResumeRequest,
    OutlineRequest,
    OutlineResponse,
    SectionRequest,
    SectionResponse,
)
from app.services.academic_context import digest
from app.services.ai_service import AIService
from app.services.background_jobs import (  # noqa: F401 - legacy patch surface
    BackgroundJobService,
)
from app.services.cost_estimator import TOKENS_PER_PAGE, CostEstimator
from app.services.custom_requirements_service import combine_generation_requirements
from app.services.document_service import DocumentService
from app.services.executor_v2.budgets import POLICY
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_pause import require_generation_open
from app.services.generation_profile import generation_profile_sha256
from app.services.generation_recovery import (
    intent_receipt,
    latest_job_for_update,
    orphan_result_state,
    record_intent,
    recovery_state,
    resume_generation,
)
from app.services.generation_worker import (
    cancel_active_generation_job,
    clear_artifact_deletion_entries,
    enqueue_artifact_deletions,
)
from app.services.grammar_checker import GrammarChecker
from app.services.plagiarism_checker import PlagiarismChecker
from app.services.replay_snapshot import row_data
from app.services.storage_service import StorageService
from app.services.task_contract import (
    SUPPORTED_CITATION_STYLES,
    contract_confirmation_error,
)
from app.services.uploaded_sources import (
    uploaded_sources_blockers,
    uploaded_sources_digest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# PostgreSQL transaction-scoped advisory lock used only while deciding and
# persisting a new system-wide token reservation. A stable literal keeps the
# lock shared by every API process and deploy revision.
_GLOBAL_GENERATION_BUDGET_LOCK_ID = 23_709_198_609_219_393


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


async def _lock_global_generation_budget(db: AsyncSession) -> None:
    """Serialize cross-user budget decisions on PostgreSQL.

    Per-user row locks cannot prevent two different managers from both seeing
    the same remaining global budget. SQLite is used only by tests/local work
    and serializes writes itself, so the production advisory lock is skipped
    there.
    """
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(
            select(func.pg_advisory_xact_lock(_GLOBAL_GENERATION_BUDGET_LOCK_ID))
        )


async def _daily_token_commitment(
    db: AsyncSession,
    *,
    today_start: datetime,
    user_id: int | None = None,
) -> int:
    """Return actual usage plus the unspent part of active job reservations."""
    total_query = select(
        func.coalesce(func.sum(AIGenerationJob.total_tokens), 0)
    ).where(AIGenerationJob.started_at >= today_start)
    if user_id is not None:
        total_query = total_query.where(AIGenerationJob.user_id == user_id)
    tokens_today = int((await db.execute(total_query)).scalar() or 0)

    active_query = (
        select(
            Document.target_pages,
            func.coalesce(AIGenerationJob.total_tokens, 0),
            AIGenerationJob.started_at,
        )
        .select_from(AIGenerationJob)
        .join(Document, AIGenerationJob.document_id == Document.id)
        .where(
            AIGenerationJob.status.in_(["queued", "running"]),
        )
    )
    if user_id is not None:
        active_query = active_query.where(AIGenerationJob.user_id == user_id)
    active_rows = (await db.execute(active_query)).all()

    # Today's active-job usage is already included above, so reserve its
    # projected remainder. A job carried across midnight keeps its whole
    # projection reserved: this schema cannot split its accumulated token
    # counter by day, and conservative accounting must not open a budget hole.
    active_remaining_tokens = sum(
        (
            int(target_pages or 0) * TOKENS_PER_PAGE
            if started_at is None or started_at.replace(tzinfo=None) < today_start
            else max(
                int(target_pages or 0) * TOKENS_PER_PAGE - int(tokens_used or 0),
                0,
            )
        )
        for target_pages, tokens_used, started_at in active_rows
    )
    return tokens_today + active_remaining_tokens


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
    confirmation_error = contract_confirmation_error(document)
    if confirmation_error is not None:
        raise HTTPException(
            409, "Підтвердіть завдання перед запуском, зокрема за наявності методички."
        )
    style = str(document.citation_style or "apa").strip().lower()
    if style not in SUPPORTED_CITATION_STYLES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Citation style '{style}' is not supported; choose one of: "
                + ", ".join(sorted(SUPPORTED_CITATION_STYLES))
            ),
        )

    target_pages = int(document.target_pages or 0)
    projected_tokens = target_pages * TOKENS_PER_PAGE

    # Validate the manager-controlled document size before budget accounting,
    # so an oversized free job receives the actionable page-limit message.
    if (
        settings.MVP_FREE_GENERATION_ENABLED
        and target_pages > settings.MVP_FREE_GENERATION_MAX_PAGES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Free generation is limited to "
                f"{settings.MVP_FREE_GENERATION_MAX_PAGES} pages "
                f"(document requests {target_pages})."
            ),
        )

    # Explicit founder authorization (2026-09-04) for internal operators.
    # Keep input/readiness checks above; this bypasses spending/count quotas
    # and customer payment only, never quality or delivery requirements.
    if user_id in settings.UNLIMITED_GENERATION_USER_IDS:
        return

    # This ceiling applies to non-exempt managers. The
    # shared gate is used by manager start, admin retry and the legacy paid
    # webhook. Its transaction holds the advisory lock through the job insert,
    # so no enqueue path can race this decision and oversubscribe the cap.
    if settings.GLOBAL_DAILY_TOKEN_LIMIT is not None:
        await _lock_global_generation_budget(db)
        global_committed_tokens = await _daily_token_commitment(
            db,
            today_start=datetime.combine(datetime.utcnow().date(), datetime.min.time()),
        )
        if (
            global_committed_tokens + projected_tokens
            > settings.GLOBAL_DAILY_TOKEN_LIMIT
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "The system-wide daily generation budget is exhausted; "
                    "please try again tomorrow."
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
        user_committed_tokens = await _daily_token_commitment(
            db,
            today_start=today_start,
            user_id=user_id,
        )
        if user_committed_tokens + projected_tokens > settings.DAILY_TOKEN_LIMIT:
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


@router.get("/full-document/{document_id}/recovery")
async def get_generation_recovery(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | None:
    document = await DocumentService(db).check_document_ownership(
        document_id, int(current_user.id)
    )
    job = (
        await db.execute(
            select(AIGenerationJob)
            .where(
                AIGenerationJob.document_id == document_id,
                AIGenerationJob.job_type == "full_document",
            )
            .order_by(AIGenerationJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if job is None:
        return (
            orphan_result_state(document)
            if document.content
            or document.docx_path
            or document.pdf_path
            or (document.outline and document.status in {"failed", "failed_quality"})
            else None
        )
    case = (
        await db.execute(
            select(ProductionCase).where(ProductionCase.document_id == document_id)
        )
    ).scalar_one_or_none()
    return await recovery_state(db, document, job, case)


@router.post("/full-document", response_model=AsyncGenerationResponse)
@rate_limit("5/hour")  # Stricter limit for full document generation
async def generate_full_document(
    request: Request,
    req_data: AsyncGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerationResponse:
    return await enqueue_full_document(req_data, current_user, db)


async def enqueue_full_document(
    req_data: AsyncGenerationRequest,
    current_user: User,
    db: AsyncSession,
    *,
    on_enqueued: Callable[[AIGenerationJob], None] | None = None,
    actor_id: int | None = None,
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
    actor_id = actor_id if actor_id is not None else int(current_user.id)
    try:
        await require_generation_open(db)
        # 1. Check document exists and user owns it
        doc_service = DocumentService(db)
        await doc_service.check_document_ownership(
            req_data.document_id, int(current_user.id)
        )

        # 2. Serialize every daily-quota decision for this user, including jobs
        # for different documents. The shared generation gate later takes the
        # system-wide budget lock. Both are held through the job insert and
        # commit, so the queued job becomes the next request's reservation.
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
        if not locked_user.is_active:
            raise HTTPException(409, "User account is inactive.")
        # GDPR deletion and generation share this user lock. Once deletion is
        # requested, no new durable work may be queued behind it.
        if getattr(locked_user, "deletion_requested_at", None) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generation cannot start while account deletion is pending.",
            )

        previous_job = await latest_job_for_update(db, req_data.document_id)
        if previous_job is not None and previous_job.status in {"queued", "running"}:
            raise HTTPException(409, "Ця робота вже виконується.")
        receipt = await intent_receipt(
            db, req_data.document_id, actor_id, req_data.intent_id
        )
        if receipt:
            raise HTTPException(
                409, "Цей запуск уже зареєстровано. Оновіть стан роботи."
            )
        # Lock order: pause -> User -> Job -> Document -> Case.
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

        # 3. Reject repeated/concurrent requests with 409. This check must run
        # before the document-status guard because the winning transaction
        # sets the document to "generating" when it creates the job.
        existing_job = await _get_active_generation_job(db, req_data.document_id)
        if existing_job:
            raise HTTPException(409, "Ця робота вже виконується.")

        has_previous_result = previous_job is not None or bool(
            document.content
            or (document.outline and document.status in {"failed", "failed_quality"})
            or document.docx_path
            or document.pdf_path
        )
        if has_previous_result:
            state = (
                await recovery_state(db, document, previous_job, production_case)
                if previous_job is not None
                else orphan_result_state(document)
            )
            if req_data.mode != "new_version":
                raise HTTPException(
                    409,
                    {
                        **state,
                        "reason_code": (
                            "resumable_job_exists"
                            if "resume" in state["allowed_actions"]
                            else state["reason_code"]
                        ),
                    },
                )
            if "new_version" not in state["allowed_actions"]:
                raise HTTPException(409, state)
            if (
                not req_data.confirm_replace
                or not req_data.intent_id
                or not req_data.replacement_reason
            ):
                raise HTTPException(
                    409, {"reason_code": "replacement_confirmation_required"}
                )
            if req_data.expected_fingerprint != state["expected_fingerprint"]:
                raise HTTPException(409, {"reason_code": "terminal_state_changed"})
        elif req_data.mode != "start":
            raise HTTPException(409, {"reason_code": "no_result_to_replace"})

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
                if (
                    case_style not in SUPPORTED_CITATION_STYLES
                    and case_style != "apa-7"
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Citation style '{case_style}' is not supported; "
                            "choose one of: "
                            + ", ".join(sorted(SUPPORTED_CITATION_STYLES))
                        ),
                    )
                # The case style is authoritative for the run; apa-7 is the
                # same formatter as apa.
                document.citation_style = "apa" if case_style == "apa-7" else case_style

        # 4. Validate document is ready for generation
        if document.status == "generating":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is already being generated",
            )

        if document.status == "completed" and req_data.mode != "new_version":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document already completed. Create new document for regeneration.",
            )

        # 5. Enforce the MVP free-generation / payment gate before any job exists
        await _enforce_generation_gate(db, document, int(current_user.id))

        # Mandatory uploaded sources must be generation-ready: scans and
        # unconfirmed metadata stop the run HERE with the exact reasons,
        # never silently degrade to API sources (GPT review 2026-07-11).
        source_blockers, _source_warnings = await uploaded_sources_blockers(
            db, req_data.document_id
        )
        if source_blockers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Uploaded sources are not generation-ready: "
                    + "; ".join(source_blockers)
                ),
            )

        # A new run invalidates every prior release and citation association.
        # Otherwise a regenerated file could inherit the previous review, or
        # stale sources could make a zero-citation retry look verified.
        contract_sha256 = generation_contract_sha256(
            document,
            production_case,
            generation_requirements,
            await uploaded_sources_digest(db, req_data.document_id),
        )
        if has_previous_result:
            previous_sections = list(
                (
                    await db.execute(
                        select(DocumentSection)
                        .where(DocumentSection.document_id == document.id)
                        .order_by(DocumentSection.section_index)
                    )
                ).scalars()
            )
            previous_sources = list(
                (
                    await db.execute(
                        select(DocumentSource).where(
                            DocumentSource.document_id == document.id
                        )
                    )
                ).scalars()
            )
            db.add(
                DocumentProvenance(
                    document_id=document.id,
                    stage="generation",
                    event_type="generation_previous_snapshot",
                    payload={
                        "previous_job_id": previous_job.id if previous_job else None,
                        "document": row_data(document),
                        "sections": [row_data(row) for row in previous_sections],
                        "sources": [row_data(row) for row in previous_sources],
                        "outline": document.outline,
                    },
                )
            )
            await db.flush()
            db.add(
                DocumentProvenance(
                    document_id=req_data.document_id,
                    stage="generation",
                    event_type="generation_replacement",
                    payload={
                        "actor_id": actor_id,
                        "intent_id": req_data.intent_id,
                        "reason": req_data.replacement_reason,
                        "previous_job_id": (
                            previous_job.id if previous_job is not None else None
                        ),
                        "previous_status": (
                            previous_job.status
                            if previous_job is not None
                            else document.status
                        ),
                        "expected_fingerprint": req_data.expected_fingerprint,
                        "source_pack_sha256": (
                            previous_job.source_pack_sha256
                            if previous_job is not None
                            else None
                        ),
                        "docx_sha256": document.docx_sha256,
                        "outline_sha256": digest(document.outline),
                        "total_tokens": (
                            previous_job.total_tokens
                            if previous_job is not None
                            else document.tokens_used
                        ),
                        "cost_cents": (
                            previous_job.cost_cents
                            if previous_job is not None
                            else None
                        ),
                    },
                )
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
            ai_provider="anthropic",
            ai_model=POLICY["model"],
            status="queued",
            progress=0,
            request_payload={
                "executor_version": 2,
                "profile_sha256": generation_profile_sha256(
                    document, int(current_user.id)
                ),
                "additional_requirements": generation_requirements,
                "generation_contract_sha256": contract_sha256,
                "superseded_artifact_paths": superseded_paths,
            },
            max_attempts=1,
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
            raise HTTPException(409, "Ця робота вже виконується.") from None

        record_intent(
            db,
            req_data.document_id,
            actor_id,
            req_data.intent_id,
            int(job.id),
            req_data.mode,
            req_data.expected_fingerprint,
            granted=True,
        )

        # 7. Update document status
        document.status = "queued"
        production_case.generation_status = "queued"

        # 8. Commit transaction before starting background task
        if on_enqueued is not None:
            on_enqueued(job)
        await db.commit()

        # The new job and release revocation are now durable. Blob cleanup can
        # no longer leave SQL pointing at a file that was rolled back into use.
        # Prior artifacts remain addressable through the immutable attempt snapshot.

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


@router.post(
    "/full-document/{document_id}/resume", response_model=AsyncGenerationResponse
)
async def resume_full_document(
    document_id: int,
    req_data: GenerationResumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerationResponse:
    try:
        job = await resume_generation(db, document_id, current_user, req_data)
        return _active_job_response(job)
    except Exception:
        await db.rollback()
        raise


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
