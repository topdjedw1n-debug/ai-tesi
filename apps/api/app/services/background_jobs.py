"""
Background jobs service for async document generation
Uses FastAPI BackgroundTasks for async processing
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.config import settings
from app.core.exceptions import (
    CitationIntegrityError,
    NotFoundError,
    QualityThresholdNotMetError,
)
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentSection,
)
from app.services.ai_detection_checker import AIDetectionChecker
from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.generator import SectionGenerator
from app.services.ai_pipeline.humanizer import Humanizer
from app.services.ai_pipeline.source_pack import SourcePackBuilder
from app.services.ai_service import AIService
from app.services.citation_verifier import (
    CitationVerifier,
)
from app.services.claim_verification_stage import (
    run_claim_verification_stage,
)
from app.services.db_helpers import (
    safe_scalar_one_or_none as _safe_scalar_one_or_none,
)
from app.services.db_helpers import (
    safe_scalars_all as _safe_scalars_all,
)
from app.services.document_service import DocumentService
from app.services.grammar_checker import GrammarChecker
from app.services.grounding_gate import GroundingResult, evaluate_grounding
from app.services.plagiarism_checker import PlagiarismChecker
from app.services.provenance_service import record_event as _record_provenance
from app.services.quality_validator import QualityValidator
from app.services.source_verification_stage import (
    load_source_pack as _load_source_pack,
)
from app.services.source_verification_stage import (
    map_verification_status as _map_verification_status,  # noqa: F401
)
from app.services.source_verification_stage import (
    persist_cited_sources as _persist_cited_sources,
)
from app.services.source_verification_stage import (
    persist_source_pack as _persist_source_pack,
)
from app.services.source_verification_stage import (
    run_citation_verification_stage,
)
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)

# Redis client for checkpoints (initialized on first use)
_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create Redis client for checkpoints"""
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


async def _clear_generation_checkpoint(document_id: int, context: str) -> None:
    """Best-effort checkpoint cleanup for terminal generation states."""
    try:
        redis = await get_redis()
        await redis.delete(f"checkpoint:doc:{document_id}")
        logger.info(f"✅ Checkpoint cleared for document {document_id} ({context})")
    except Exception as checkpoint_error:
        logger.warning(
            f"⚠️ Failed to clear checkpoint for document {document_id} ({context}): {checkpoint_error}"
        )


# Type variable for background task functions
F = TypeVar("F", bound=Callable[..., Any])


def background_task_error_handler(task_name: str) -> Callable[[F], F]:
    """
    Decorator for background tasks to provide consistent error handling

    Wraps background tasks with:
    - Exception catching and logging
    - Error tracking
    - Graceful failure handling

    Args:
        task_name: Name of the task for logging purposes
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                logger.info(f"Starting background task: {task_name}")
                result = await func(*args, **kwargs)
                logger.info(f"Background task completed: {task_name}")
                return result
            except Exception as e:
                logger.error(
                    f"Background task failed: {task_name}",
                    exc_info=True,
                    extra={
                        "task_name": task_name,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "task_args_snapshot": str(args)[:200],  # Limit log size
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )
                # Re-raise to allow upstream handlers to process
                raise

        return wrapper  # type: ignore

    return decorator


# ========== WebSocket Heartbeat Helper (Step 1.2) ==========


async def send_periodic_heartbeat(
    user_id: int, job_id: int, document_id: int, interval: int = 10
) -> None:
    """
    Send periodic heartbeat to keep WebSocket connection alive during long generations

    Prevents browser and proxy timeouts:
    - Chrome: 5 min idle timeout
    - Safari: 30 sec idle timeout
    - Nginx: 60 sec default timeout
    - CloudFlare: 100 sec timeout

    Automatically stops when job completes or fails by checking DB status.

    Args:
        user_id: User ID for WebSocket routing
        job_id: Job ID for frontend correlation
        document_id: Document ID for debugging
        interval: Seconds between heartbeats (default: 10)

    Example:
        heartbeat_task = asyncio.create_task(
            send_periodic_heartbeat(user_id, job_id, doc_id)
        )
        try:
            await generate_document(...)
        finally:
            heartbeat_task.cancel()
    """
    while True:
        try:
            await asyncio.sleep(interval)

            # Check if job still running (fetch fresh from DB)
            async with database.AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AIGenerationJob).where(AIGenerationJob.id == job_id)
                )
                job = _safe_scalar_one_or_none(result, "heartbeat_job_lookup")

                # Stop if job finished/failed/not found
                if not job or job.status not in ["running", "generating"]:
                    logger.info(
                        f"Heartbeat stopped: job {job_id} status={job.status if job else 'not_found'}"
                    )
                    break

            # Send heartbeat via WebSocket
            await manager.send_progress(
                user_id,
                {
                    "type": "heartbeat",
                    "job_id": job_id,
                    "document_id": document_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            logger.debug(f"💓 Heartbeat sent for job {job_id}")

        except asyncio.CancelledError:
            # Task cancelled (normal shutdown)
            logger.info(f"Heartbeat task cancelled for job {job_id}")
            break
        except Exception as e:
            # Log error but continue sending heartbeats
            # Connection is critical - one failed heartbeat shouldn't stop all
            logger.warning(f"⚠️ Heartbeat error for job {job_id}: {e}")
            # Continue loop


async def _check_panel_quality(
    db: AsyncSession,
    content: str,
    section_title: str,
    target_word_count: int,
) -> dict[str, Any] | None:
    """
    Run the LLM reviewer panel for one section attempt (GATE 4).

    Returns the QualityValidator result dict ({"passed", "overall_score",
    "issues", ...} plus panel keys). ⚠️ Never raises: on unexpected failure
    returns None and the caller behaves as if the panel had not run (the
    post-loop heuristic then produces a real score instead of a fabricated
    one). Only the panel's verdict can fail the gate, never its outage.
    """
    try:
        validator = QualityValidator(ai_service=AIService(db))
        return await validator.validate_section(
            content=content,
            outline_section={
                "title": section_title,
                "target_word_count": target_word_count,
            },
        )
    except Exception as e:
        logger.error(f"Reviewer panel crashed for section '{section_title}': {e}")
        return None


# ========== Quality Gate Helper Functions (Task 3.2) ==========


class CheckStatus(str, Enum):
    """Outcome of a single quality check.

    UNCHECKED means the provider was disabled/unconfigured or threw: the
    check never ran. It must not block generation, but it must never be
    recorded as passed either — release gates and the UI surface it.
    str-mixin so test mocks can return plain "passed"/"failed"/"unchecked".
    """

    PASSED = "passed"
    FAILED = "failed"
    UNCHECKED = "unchecked"

    def __str__(self) -> str:  # str(CheckStatus.PASSED) == "passed"
        return self.value


async def _check_grammar_quality(
    content: str, language: str, threshold: int
) -> tuple[float | None, int, CheckStatus, str | None]:
    """
    Check grammar quality and return results

    Args:
        content: Text to check
        language: Language code (en, de, fr, etc.)
        threshold: Max allowed errors (from QUALITY_MAX_GRAMMAR_ERRORS)

    Returns:
        Tuple of (score, error_count, status, reason)
        - score: Grammar score (0-100, None if check didn't run)
        - error_count: Number of grammar errors found
        - status: PASSED / FAILED / UNCHECKED (provider unavailable or threw)
        - reason: Failure detail or why the check didn't run; None on pass
    """
    try:
        grammar_checker = GrammarChecker()
        grammar_result = await grammar_checker.check_text(
            text=content, language=language
        )

        if grammar_result.get("checked"):
            matches = grammar_result.get("matches", [])
            error_count = len(matches)

            normalized_language = (language or "").lower()
            is_english = normalized_language.startswith("en")
            effective_threshold = (
                threshold
                if is_english
                else max(threshold, settings.QUALITY_MAX_GRAMMAR_ERRORS_NON_EN)
            )

            # Calculate score: max 100, -5 per issue
            score = max(0.0, 100.0 - (error_count * 5.0))

            passed = error_count <= effective_threshold
            error_msg = (
                None
                if passed
                else f"Grammar: {error_count} errors (max: {effective_threshold})"
            )

            return (
                score,
                error_count,
                CheckStatus.PASSED if passed else CheckStatus.FAILED,
                error_msg,
            )
        else:
            reason = grammar_result.get("error", "grammar check unavailable")
            logger.warning(f"Grammar check UNCHECKED: {reason}")
            return (None, 0, CheckStatus.UNCHECKED, reason)

    except Exception as e:
        logger.error(f"Grammar check exception: {e}")
        return (None, 0, CheckStatus.UNCHECKED, f"exception: {e}")


async def _check_plagiarism_quality(
    content: str, threshold: float
) -> tuple[float | None, float, CheckStatus, str | None]:
    """
    Check plagiarism and return results

    Args:
        content: Text to check
        threshold: Min required uniqueness % (from QUALITY_MIN_PLAGIARISM_UNIQUENESS)

    Returns:
        Tuple of (plagiarism_score, uniqueness, status, reason)
        - plagiarism_score: Plagiarism % (0-100, None if check didn't run)
        - uniqueness: Uniqueness % (100 - plagiarism_score; placeholder
          100.0 when unchecked — do not treat as a real measurement)
        - status: PASSED / FAILED / UNCHECKED (provider unavailable or threw)
        - reason: Failure detail or why the check didn't run; None on pass
    """
    try:
        plagiarism_checker = PlagiarismChecker()
        plagiarism_result = await plagiarism_checker.check_text(text=content)

        if plagiarism_result.get("checked"):
            uniqueness = plagiarism_result.get("uniqueness_percentage", 100.0)
            plagiarism_score = 100.0 - uniqueness

            passed = uniqueness >= threshold
            error_msg = (
                None
                if passed
                else f"Plagiarism: {uniqueness:.1f}% unique (min: {threshold}%)"
            )

            return (
                plagiarism_score,
                uniqueness,
                CheckStatus.PASSED if passed else CheckStatus.FAILED,
                error_msg,
            )
        else:
            reason = plagiarism_result.get("error", "plagiarism check unavailable")
            logger.warning(f"Plagiarism check UNCHECKED: {reason}")
            return (None, 100.0, CheckStatus.UNCHECKED, reason)

    except Exception as e:
        logger.error(f"Plagiarism check exception: {e}")
        return (None, 100.0, CheckStatus.UNCHECKED, f"exception: {e}")


async def _check_ai_detection_quality(
    content: str,
    threshold: float,
    humanizer: Humanizer,
    provider: str,
    model: str,
    language: str,
    score_trace: dict[str, Any] | None = None,
) -> tuple[float | None, str, str, CheckStatus, str | None]:
    """
    Check AI detection score and run multi-pass if needed

    Args:
        content: Text to check
        threshold: Max allowed AI % (from QUALITY_MAX_AI_DETECTION_SCORE)
        humanizer: Humanizer instance for multi-pass
        provider: AI provider (openai/anthropic)
        model: AI model name
        language: Target language code for the output
        score_trace: Optional dict the caller can pass to receive the
            before/after AI scores (initial_ai_score, final_ai_score,
            multi_pass) for the provenance ledger. Kwarg-only by convention
            so existing 5-tuple mocks stay compatible.

    Returns:
        Tuple of (ai_score, final_content, provider_used, status, reason)
        - ai_score: AI detection % (0-100, None if check didn't run)
        - final_content: Content after potential multi-pass humanization
        - provider_used: Detection provider used ("none" when unchecked)
        - status: PASSED / FAILED / UNCHECKED (provider unavailable or threw)
        - reason: Failure detail or why the check didn't run; None on pass
    """
    try:
        ai_checker = AIDetectionChecker()
        ai_result = await ai_checker.check_text(text=content)

        if ai_result.get("checked"):
            ai_score = ai_result.get("ai_probability", 0.0)
            provider_used = ai_result.get("provider", "unknown")
            final_content = content
            if score_trace is not None:
                score_trace["initial_ai_score"] = ai_score
                score_trace["multi_pass"] = False

            # If score too high, try multi-pass humanization
            if ai_score > threshold:
                logger.info(
                    f"AI score {ai_score:.1f}% > {threshold}%, running multi-pass..."
                )

                final_content, final_ai_score = await humanizer.humanize_multi_pass(
                    text=content,
                    provider=provider,
                    model=model,
                    target_ai_score=threshold - 5.0,  # Aim 5% below threshold
                    max_attempts=2,
                    preserve_citations=True,
                    language=language,
                )

                ai_score = final_ai_score
                if score_trace is not None:
                    score_trace["multi_pass"] = True
                logger.info(f"After multi-pass: AI score = {final_ai_score:.1f}%")

            if score_trace is not None:
                score_trace["final_ai_score"] = ai_score

            passed = ai_score <= threshold
            error_msg = (
                None if passed else f"AI detection: {ai_score:.1f}% (max: {threshold}%)"
            )

            return (
                ai_score,
                final_content,
                provider_used,
                CheckStatus.PASSED if passed else CheckStatus.FAILED,
                error_msg,
            )
        else:
            reason = ai_result.get("error", "AI detection unavailable")
            logger.warning(f"AI detection check UNCHECKED: {reason}")
            return (None, content, "none", CheckStatus.UNCHECKED, reason)

    except Exception as e:
        logger.error(f"AI detection check exception: {e}")
        return (None, content, "none", CheckStatus.UNCHECKED, f"exception: {e}")


# ========== End Quality Gate Helpers ==========


# ========== Citation Verification Helpers (Academic Quality Engine) ==========


async def _safe_send_progress(user_id: int, message: dict[str, Any]) -> None:
    """
    Send a websocket progress message without ever raising.

    manager.send_progress only swallows WebSocket exceptions; anything else
    (e.g. Starlette's RuntimeError on a socket closed mid-send) propagates
    and must not be able to derail the verification stage or the strict gate.
    Used by NEW citation-verification code only.
    """
    try:
        await manager.send_progress(user_id, message)
    except Exception as e:
        logger.warning(f"⚠️ Failed to send citation progress update: {e}")


async def _run_citation_verification_stage(
    db: AsyncSession, document_id: int, user_id: int
) -> None:
    """
    Thin wrapper around source_verification_stage.run_citation_verification_stage.

    Passes this module's globals (settings, CitationVerifier,
    _safe_send_progress) at call time so test monkeypatches on
    app.services.background_jobs keep reaching the stage.
    """
    await run_citation_verification_stage(
        db,
        document_id,
        user_id,
        config=settings,
        verifier_factory=CitationVerifier,
        send_progress=_safe_send_progress,
    )


# ========== Claim Faithfulness Helpers (Academic Quality Engine) ==========


async def _run_claim_verification_stage(
    db: AsyncSession, document_id: int, user_id: int
) -> None:
    """
    Thin wrapper around claim_verification_stage.run_claim_verification_stage.

    Passes this module's globals (settings, AIService, _safe_send_progress)
    at call time so test monkeypatches on app.services.background_jobs keep
    reaching the stage.
    """
    await run_claim_verification_stage(
        db,
        document_id,
        user_id,
        config=settings,
        ai_service_factory=AIService,
        send_progress=_safe_send_progress,
    )


# ========== End Citation Verification Helpers ==========


async def _build_source_pack(
    db: AsyncSession,
    document: Document,
    section_titles: list[str] | None = None,
) -> Any:
    """
    Thin wrapper around SourcePackBuilder.build for the upfront source pack.

    Reads this module's `settings` global at call time so test monkeypatches on
    app.services.background_jobs keep working, mirroring the other stage
    wrappers. Returns a SourcePack (never raises — builder degrades gracefully).
    section_titles is set on the post-outline rebuild so queries cover every
    promised section, not just the bare topic.
    """
    builder = SourcePackBuilder()
    return await builder.build(
        topic=str(document.topic),
        language=str(document.language),
        document_id=int(document.id),
        target_size=settings.SOURCE_PACK_TARGET_SIZE,
        min_on_topic_score=settings.SOURCE_PACK_MIN_ON_TOPIC_SCORE,
        section_titles=section_titles,
    )


def _augment_with_grounding_feedback(
    base_requirements: str | None, grounding: GroundingResult
) -> str:
    """Append grounding-failure feedback so the next attempt fixes the right thing."""
    prefix = f"{base_requirements}\n\n" if base_requirements else ""
    if "concrete evidence" in grounding.reason:
        # Evidence failure: citations are fine, prose lacks concrete detail.
        return (
            f"{prefix}Grounding check failed: {grounding.reason}. Add at least "
            f"one concrete detail drawn from the AVAILABLE SOURCES (a statistic, "
            f"numeric finding, or specific study result from their abstracts). "
            f"NEVER invent numeric data — if the sources give no numbers, state "
            f"their concrete qualitative findings instead."
        )
    keys = ", ".join(grounding.offending_keys[:10]) or "(unresolved)"
    return (
        f"{prefix}Grounding check failed: {grounding.reason}. Cite ONLY sources "
        f"from the provided AVAILABLE SOURCES list, using their exact [Key]. Do "
        f"NOT use these ungrounded or invented citations: {keys}. If a claim has "
        f"no supporting listed source, state it without a citation."
    )


class BackgroundJobService:
    """Service for background document generation tasks"""

    @staticmethod
    @background_task_error_handler("generate_full_document")
    async def generate_full_document(
        document_id: int, user_id: int, additional_requirements: str | None = None
    ) -> None:
        """
        Background task to generate a complete document

        This function:
        1. Generates document outline
        2. Generates all sections sequentially
        3. Humanizes all content (mandatory)
        4. Exports to DOCX
        5. Updates document status

        Args:
            document_id: ID of the document to generate
            user_id: ID of the user owning the document
            additional_requirements: Optional additional requirements
        """
        async with database.AsyncSessionLocal() as db:
            try:
                logger.info(
                    f"Starting full document generation for document {document_id}"
                )

                # Get document
                result = await db.execute(
                    select(Document).where(
                        Document.id == document_id, Document.user_id == user_id
                    )
                )
                document = _safe_scalar_one_or_none(result, "document_lookup")

                if not document:
                    logger.error(f"Document {document_id} not found for user {user_id}")
                    return

                # Update status to generating
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(status="generating")
                )
                await db.commit()

                # Step 0: Build the upfront topic-locked source pack (grounding).
                # Built once and reused for the outline + every section so
                # citations come from a curated, on-topic set. Gated: when
                # SOURCE_GROUNDING_ENABLED is off, source_pack stays None and the
                # pipeline follows the legacy per-section retrieval path.
                source_pack = None
                if settings.SOURCE_GROUNDING_ENABLED:
                    source_pack = await _load_source_pack(db, document_id)
                    if source_pack is None or not source_pack.sources:
                        source_pack = await _build_source_pack(db, document)
                        if source_pack is not None:
                            await _persist_source_pack(db, document_id, source_pack)
                            if settings.PROVENANCE_LEDGER_ENABLED:
                                scores = [
                                    ps.on_topic_score for ps in source_pack.sources
                                ]
                                await _record_provenance(
                                    db,
                                    document_id,
                                    stage="retrieval",
                                    event_type="source_pack_built",
                                    payload={
                                        "pack_size": len(source_pack.sources),
                                        "mean_on_topic_score": (
                                            round(sum(scores) / len(scores), 3)
                                            if scores
                                            else 0.0
                                        ),
                                        "underfilled": source_pack.underfilled,
                                    },
                                )

                # Step 1: Generate outline if not exists
                if not document.outline:
                    logger.info(f"Generating outline for document {document_id}")
                    ai_service = AIService(db)
                    try:
                        await ai_service.generate_outline(
                            document_id=document_id,
                            user_id=user_id,
                            additional_requirements=additional_requirements,
                            source_pack=source_pack,
                        )
                        logger.info(
                            f"Outline generated successfully for document {document_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to generate outline: {e}")
                        await db.execute(
                            update(Document)
                            .where(Document.id == document_id)
                            .values(status="failed")
                        )
                        await db.commit()
                        return

                # Reload document to get outline
                await db.refresh(document)

                if not document.outline or "sections" not in document.outline:
                    logger.error(
                        f"No outline sections found for document {document_id}"
                    )
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed")
                    )
                    await db.commit()
                    return

                # Step 2: Generate all sections
                sections = document.outline.get("sections", [])
                section_generator = SectionGenerator()
                humanizer = Humanizer()

                logger.info(
                    f"Generating {len(sections)} sections for document {document_id}"
                )

                # ✅ TASK 3.7.2: Check for checkpoint and resume from last completed section
                start_section_index = 0
                try:
                    redis = await get_redis()
                    checkpoint_raw = await redis.get(f"checkpoint:doc:{document_id}")
                    if checkpoint_raw:
                        checkpoint = json.loads(checkpoint_raw)
                        start_section_index = checkpoint.get(
                            "last_completed_section_index", 0
                        )
                        logger.info(
                            f"♻️ Resuming generation from section {start_section_index + 1}/{len(sections)}"
                        )

                        # Send WebSocket notification about resume
                        await manager.send_progress(
                            user_id,
                            {
                                "progress": int(
                                    (start_section_index / len(sections)) * 100
                                ),
                                "stage": f"Resuming from section {start_section_index + 1}",
                                "status": "generating",
                                "document_id": document_id,
                            },
                        )
                    else:
                        logger.info(
                            f"Starting fresh generation for document {document_id}"
                        )
                except Exception as checkpoint_error:
                    # ⚠️ Non-critical: log warning and start from beginning
                    logger.warning(
                        f"⚠️ Failed to load checkpoint: {checkpoint_error}. Starting from beginning."
                    )
                    start_section_index = 0

                # Post-outline pack rebuild (grounding): re-query with the
                # promised section titles so the pack covers every section, not
                # just the bare topic (which returned a generic "AI" mix).
                # ONLY on fresh generation — on resume, already-generated
                # sections cite the persisted keys and a rebuild would re-key
                # the pack and orphan their citations.
                if (
                    settings.SOURCE_GROUNDING_ENABLED
                    and source_pack is not None
                    and start_section_index == 0
                ):
                    titles = [s.get("title") for s in sections if s.get("title")]
                    if titles:
                        source_pack = await _build_source_pack(
                            db, document, section_titles=titles
                        )
                        await _persist_source_pack(db, document_id, source_pack)
                        if settings.PROVENANCE_LEDGER_ENABLED:
                            scores = [ps.on_topic_score for ps in source_pack.sources]
                            await _record_provenance(
                                db,
                                document_id,
                                stage="retrieval",
                                event_type="source_pack_rebuilt",
                                payload={
                                    "pack_size": len(source_pack.sources),
                                    "mean_on_topic_score": (
                                        round(sum(scores) / len(scores), 3)
                                        if scores
                                        else 0.0
                                    ),
                                    "underfilled": source_pack.underfilled,
                                    "section_titles": titles[:12],
                                },
                            )

                total_sections = len(sections)  # Calculate once for progress tracking
                for idx, section_data in enumerate(sections):
                    section_title = section_data.get("title", f"Section {idx + 1}")
                    section_index = idx + 1

                    # ✅ Skip sections that were completed before checkpoint
                    if section_index <= start_section_index:
                        logger.info(
                            f"⏭️ Skipping already completed section {section_index}"
                        )
                        continue

                    current_section = section_data  # For word count target

                    try:
                        # ✅ TASK 3.7.5: Idempotency - check if section already completed
                        existing_section_result = await db.execute(
                            select(DocumentSection).where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                                DocumentSection.status == "completed",
                            )
                        )
                        existing_section = _safe_scalar_one_or_none(
                            existing_section_result,
                            f"idempotency_section_{section_index}",
                        )

                        if existing_section:
                            logger.info(
                                f"⏭️ Section {section_index} already completed (idempotency), skipping"
                            )
                            continue

                        # Update section status to generating
                        await db.execute(
                            update(DocumentSection)
                            .where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                            )
                            .values(status="generating")
                        )
                        await db.commit()

                        # Get previously generated sections for context (✅ LIMITED to last N sections)
                        context_result = await db.execute(
                            select(DocumentSection)
                            .where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index < section_index,
                                DocumentSection.status == "completed",
                            )
                            .order_by(
                                DocumentSection.section_index.desc()
                            )  # Most recent first
                            .limit(
                                settings.QUALITY_GATES_MAX_CONTEXT_SECTIONS
                            )  # ✅ Limit context
                        )
                        context_sections = _safe_scalars_all(
                            context_result,
                            f"context_sections_before_{section_index}",
                        )
                        context_list = (
                            [
                                {"title": s.title, "content": s.content}
                                for s in context_sections
                            ]
                            if context_sections
                            else None
                        )

                        # ========== REGENERATION LOOP START (Task 3.2 - Quality Gates) ==========
                        # Try generation up to MAX_REGENERATE_ATTEMPTS times if quality gates fail

                        final_content = None
                        final_grammar_score = None
                        final_plagiarism_score = None
                        final_ai_score = None
                        final_quality_score = None
                        # Per-check status/score/reason of the final accepted
                        # attempt — recorded in the quality_gate event so
                        # unchecked checks are visible downstream
                        final_check_breakdown: dict[str, dict[str, Any]] | None = None
                        ai_trace: dict[str, Any] = {}
                        panel_result: dict[str, Any] | None = None
                        panel_feedback: list[str] = []
                        # Reviewer remarks from a failed attempt are appended
                        # here so the NEXT attempt's prompt addresses them;
                        # identical to additional_requirements when the panel
                        # is disabled or hasn't flagged anything
                        effective_requirements = additional_requirements

                        for attempt in range(
                            settings.QUALITY_MAX_REGENERATE_ATTEMPTS + 1
                        ):
                            attempt_num = attempt + 1
                            logger.info(
                                f"Section {section_index} attempt {attempt_num}/"
                                f"{settings.QUALITY_MAX_REGENERATE_ATTEMPTS + 1}: {section_title}"
                            )

                            # WebSocket: Notify attempt number
                            await manager.send_progress(
                                user_id,
                                {
                                    "stage": f"generating_section_{section_index}_attempt_{attempt_num}",
                                    "progress": min(
                                        95, 50 + (section_index / total_sections) * 40
                                    ),
                                    "message": f"Generating section {section_index} (attempt {attempt_num})",
                                },
                            )

                            # Generate section with RAG (closed-book against the
                            # source pack when grounding is enabled).
                            section_result = await section_generator.generate_section(
                                document=document,
                                section_title=section_title,
                                section_index=section_index,
                                provider=document.ai_provider,
                                model=document.ai_model,
                                citation_style=CitationStyle.APA,  # Default to APA
                                humanize=False,  # Will humanize in next step
                                context_sections=context_list,
                                additional_requirements=effective_requirements,
                                source_pack=source_pack,
                            )

                            # Grounding gate (Academic Quality Engine): score the
                            # raw draft's citations against the source pack BEFORE
                            # humanization. Ungrounded/off-topic citations trigger
                            # bounded regeneration within this loop's budget.
                            if (
                                settings.GROUNDING_GATE_ENABLED
                                and source_pack is not None
                            ):
                                grounding = evaluate_grounding(
                                    section_result,
                                    source_pack,
                                    min_grounding_rate=settings.GROUNDING_MIN_RATE,
                                    require_evidence=(
                                        settings.GROUNDING_REQUIRE_EVIDENCE
                                    ),
                                    min_on_topic_score=(
                                        settings.SOURCE_PACK_MIN_ON_TOPIC_SCORE
                                    ),
                                )
                                if not grounding.passed:
                                    if settings.PROVENANCE_LEDGER_ENABLED:
                                        await _record_provenance(
                                            db,
                                            document_id,
                                            stage="generation",
                                            event_type="grounding_gate_failed",
                                            payload={
                                                "section_index": section_index,
                                                "attempt": attempt_num,
                                                "grounding_rate": round(
                                                    grounding.grounding_rate, 3
                                                ),
                                                "offending_keys": (
                                                    grounding.offending_keys[:20]
                                                ),
                                                "reason": grounding.reason,
                                            },
                                        )
                                    if (
                                        attempt
                                        < settings.QUALITY_MAX_REGENERATE_ATTEMPTS
                                    ):
                                        # Feed the failure back and regenerate
                                        # (shares this loop's attempt budget).
                                        effective_requirements = (
                                            _augment_with_grounding_feedback(
                                                effective_requirements, grounding
                                            )
                                        )
                                        logger.warning(
                                            f"Grounding gate failed for section "
                                            f"{section_index} (attempt {attempt_num}): "
                                            f"{grounding.reason} — regenerating"
                                        )
                                        continue
                                    # Final attempt: strict fails, mark_only ships.
                                    if settings.GROUNDING_GATE_POLICY == "strict":
                                        raise QualityThresholdNotMetError(
                                            detail=(
                                                f"Section {section_index} failed the "
                                                f"grounding gate after "
                                                f"{settings.QUALITY_MAX_REGENERATE_ATTEMPTS + 1} "
                                                f"attempts: {grounding.reason}"
                                            )
                                        )
                                    if settings.PROVENANCE_LEDGER_ENABLED:
                                        await _record_provenance(
                                            db,
                                            document_id,
                                            stage="generation",
                                            event_type="grounding_gate_exhausted",
                                            payload={
                                                "section_index": section_index,
                                                "grounding_rate": round(
                                                    grounding.grounding_rate, 3
                                                ),
                                                "policy": "mark_only",
                                            },
                                        )

                            # Step 3: Humanize content (mandatory)
                            logger.info(
                                f"Humanizing section {section_index}: {section_title}"
                            )
                            humanized_content = await humanizer.humanize(
                                text=section_result.get("content", ""),
                                provider=document.ai_provider,
                                model=document.ai_model,
                                preserve_citations=True,
                                language=document.language,
                            )

                            # ========== QUALITY GATES START ==========
                            # ✅ BUG FIX: Always run ALL checks (for metrics), only block if gates enabled

                            gates_passed = True
                            attempt_errors = []
                            # Reset per attempt: stale remarks about an older
                            # draft must not leak into later prompts
                            panel_feedback = []

                            # GATE 1: Grammar Check (ALWAYS RUN)
                            (
                                grammar_score,
                                grammar_errors,
                                grammar_status,
                                grammar_reason,
                            ) = await _check_grammar_quality(
                                humanized_content,
                                document.language,
                                settings.QUALITY_MAX_GRAMMAR_ERRORS,
                            )
                            final_grammar_score = grammar_score  # Save for DB

                            if (
                                grammar_status == CheckStatus.FAILED
                                and settings.QUALITY_GATES_ENABLED
                            ):
                                gates_passed = False
                                attempt_errors.append(grammar_reason)
                                logger.warning(
                                    f"❌ Grammar gate FAILED: {grammar_reason}"
                                )
                            elif grammar_status == CheckStatus.UNCHECKED:
                                # Non-blocking, but never counts as passed
                                logger.warning(
                                    f"⚠️ Grammar gate UNCHECKED: {grammar_reason}"
                                )
                            else:
                                logger.info(
                                    f"✅ Grammar gate: {grammar_errors} errors (status={grammar_status})"
                                )

                            # GATE 2: Plagiarism Check (ALWAYS RUN)
                            (
                                plagiarism_score,
                                uniqueness,
                                plagiarism_status,
                                plagiarism_reason,
                            ) = await _check_plagiarism_quality(
                                humanized_content,
                                settings.QUALITY_MIN_PLAGIARISM_UNIQUENESS,
                            )
                            final_plagiarism_score = plagiarism_score  # Save for DB

                            if (
                                plagiarism_status == CheckStatus.FAILED
                                and settings.QUALITY_GATES_ENABLED
                            ):
                                gates_passed = False
                                attempt_errors.append(plagiarism_reason)
                                logger.warning(
                                    f"❌ Plagiarism gate FAILED: {plagiarism_reason}"
                                )
                            elif plagiarism_status == CheckStatus.UNCHECKED:
                                logger.warning(
                                    f"⚠️ Plagiarism gate UNCHECKED: {plagiarism_reason}"
                                )
                            else:
                                logger.info(
                                    f"✅ Plagiarism gate: {uniqueness:.1f}% unique (status={plagiarism_status})"
                                )

                            # GATE 3: AI Detection Check (ALWAYS RUN, includes multi-pass humanization)
                            ai_trace = (
                                {}
                            )  # fresh trace per attempt; final attempt's survives
                            (
                                ai_score,
                                humanized_content,
                                provider_used,
                                ai_status,
                                ai_reason,
                            ) = await _check_ai_detection_quality(
                                humanized_content,
                                settings.QUALITY_MAX_AI_DETECTION_SCORE,
                                humanizer,
                                document.ai_provider,
                                document.ai_model,
                                document.language,
                                score_trace=ai_trace,
                            )
                            final_ai_score = ai_score  # Save for DB

                            if (
                                ai_status == CheckStatus.FAILED
                                and settings.QUALITY_GATES_ENABLED
                            ):
                                gates_passed = False
                                attempt_errors.append(ai_reason)
                                logger.warning(
                                    f"❌ AI detection gate FAILED: {ai_reason}"
                                )
                            elif ai_status == CheckStatus.UNCHECKED:
                                logger.warning(
                                    f"⚠️ AI detection gate UNCHECKED: {ai_reason}"
                                )
                            else:
                                ai_score_text = (
                                    f"{ai_score:.1f}% AI"
                                    if ai_score is not None
                                    else "N/A"
                                )
                                logger.info(
                                    f"✅ AI detection gate: {ai_score_text} (status={ai_status})"
                                )

                            # Per-check breakdown for the provenance ledger —
                            # rebuilt every attempt; the final accepted
                            # attempt's survives (mirrors final_*_score).
                            # str() → "passed"/"failed"/"unchecked" for both
                            # CheckStatus members and plain-string mocks.
                            final_check_breakdown = {
                                "grammar": {
                                    "status": str(grammar_status),
                                    "score": final_grammar_score,
                                    "reason": grammar_reason,
                                },
                                "plagiarism": {
                                    "status": str(plagiarism_status),
                                    "score": final_plagiarism_score,
                                    "reason": plagiarism_reason,
                                },
                                "ai_detection": {
                                    "status": str(ai_status),
                                    "score": final_ai_score,
                                    "reason": ai_reason,
                                    "provider": provider_used,
                                },
                            }

                            # GATE 4: Reviewer Panel (flag-gated: 4 LLM calls
                            # per run, unlike gates 1-3 it does NOT always
                            # run; also skipped when gates 1-3 already failed
                            # this attempt - the draft will be regenerated
                            # anyway, no point reviewing a doomed draft)
                            if settings.QUALITY_PANEL_ENABLED and gates_passed:
                                # Reset so a crash here doesn't leave scores/
                                # reports describing an older attempt's draft
                                panel_result = None
                                final_quality_score = None
                                panel_attempt = await _check_panel_quality(
                                    db,
                                    humanized_content,
                                    section_title,
                                    current_section.get("word_count", 500),
                                )
                                if panel_attempt is None:
                                    logger.warning(
                                        f"⚠️ Panel gate skipped for section "
                                        f"{section_index} (panel crashed); "
                                        f"heuristic scoring will apply"
                                    )
                                else:
                                    panel_result = panel_attempt
                                    final_quality_score = panel_result.get(
                                        "overall_score", 75.0
                                    )
                                    panel_passed = panel_result.get("passed", True)

                                    if (
                                        not panel_passed
                                        and settings.QUALITY_GATES_ENABLED
                                    ):
                                        gates_passed = False
                                        panel_feedback = panel_result.get(
                                            "feedback_for_regeneration", []
                                        )
                                        panel_error_msg = (
                                            f"Reviewer panel score "
                                            f"{final_quality_score:.1f} "
                                            f"(critical_override="
                                            f"{panel_result.get('critical_override', False)})"
                                        )
                                        attempt_errors.append(panel_error_msg)
                                        logger.warning(
                                            f"❌ Panel gate FAILED: {panel_error_msg}"
                                        )
                                    else:
                                        logger.info(
                                            f"✅ Panel gate: {final_quality_score:.1f} "
                                            f"(passed={panel_passed})"
                                        )

                            # ========== QUALITY GATES DECISION ==========

                            if not settings.QUALITY_GATES_ENABLED or gates_passed:
                                # ALL GATES PASSED or GATES DISABLED ✅
                                final_content = humanized_content
                                logger.info(
                                    f"✅ Section {section_index} passed all quality gates (enabled={settings.QUALITY_GATES_ENABLED})"
                                )
                                break  # Exit regeneration loop, save section

                            elif attempt < settings.QUALITY_MAX_REGENERATE_ATTEMPTS:
                                # GATES FAILED but ATTEMPTS REMAIN → REGENERATE
                                logger.warning(
                                    f"⚠️ Section {section_index} attempt {attempt_num} failed quality gates: "
                                    f"{', '.join(attempt_errors)}. Regenerating..."
                                )

                                # Feed reviewer remarks into the next
                                # attempt's prompt; panel_feedback is reset
                                # every attempt, so this is empty unless the
                                # panel flagged THIS attempt's draft - in
                                # that case drop any older feedback too
                                if panel_feedback:
                                    feedback_block = "\n".join(
                                        f"- {item}" for item in panel_feedback
                                    )
                                    base_requirements = (
                                        f"{additional_requirements}\n\n"
                                        if additional_requirements
                                        else ""
                                    )
                                    effective_requirements = (
                                        f"{base_requirements}"
                                        f"Address the following reviewer feedback "
                                        f"from the previous draft:\n{feedback_block}"
                                    )
                                else:
                                    effective_requirements = additional_requirements

                                # WebSocket: Notify regeneration
                                await manager.send_progress(
                                    user_id,
                                    {
                                        "stage": f"regenerating_section_{section_index}",
                                        "progress": min(
                                            95,
                                            50 + (section_index / total_sections) * 40,
                                        ),
                                        "message": f"Quality check failed, regenerating section {section_index}...",
                                    },
                                )

                                continue  # Try again with next attempt

                            else:
                                # GATES FAILED and NO ATTEMPTS LEFT → FAIL JOB
                                error_detail = f"Section {section_index} quality validation failed after {settings.QUALITY_MAX_REGENERATE_ATTEMPTS + 1} attempts: {', '.join(attempt_errors)}"
                                logger.error(f"❌ {error_detail}")
                                # Preserve the failing attempt's reviewer
                                # detail - the success-path persistence below
                                # is never reached, and without this the
                                # remarks that killed the job are lost
                                if (
                                    settings.PROVENANCE_LEDGER_ENABLED
                                    and panel_result is not None
                                ):
                                    await _record_provenance(
                                        db,
                                        document_id,
                                        stage="quality",
                                        event_type="panel_gate_failed",
                                        payload={
                                            "section_index": section_index,
                                            "attempts": attempt_num,
                                            "overall_score": panel_result.get(
                                                "overall_score"
                                            ),
                                            "critical_override": panel_result.get(
                                                "critical_override", False
                                            ),
                                            "panel": panel_result.get("panel"),
                                        },
                                    )
                                raise QualityThresholdNotMetError(detail=error_detail)

                        # ========== REGENERATION LOOP END ==========

                        # If we reached here, section passed all quality gates
                        # Run final quality validation (non-blocking, for
                        # stats only) - unless the reviewer panel already
                        # scored this attempt inside the gate loop
                        if final_quality_score is None:
                            try:
                                logger.info(
                                    f"📊 Running quality validation for section {section_index}..."
                                )

                                quality_validator = QualityValidator()
                                quality_result = (
                                    await quality_validator.validate_section(
                                        content=final_content,
                                        outline_section={
                                            "title": section_title,
                                            "target_word_count": current_section.get(
                                                "word_count", 500
                                            ),
                                        },
                                    )
                                )

                                final_quality_score = quality_result.get(
                                    "overall_score", 75.0
                                )

                                logger.info(
                                    f"Quality validation: score={final_quality_score:.1f}, "
                                    f"issues={len(quality_result.get('issues', []))}"
                                )

                            except Exception as e:
                                logger.error(
                                    f"Quality validation failed for section {section_index}: {e}"
                                )
                                final_quality_score = 75.0  # Neutral score on error

                        # ✅ BUG FIX: Defensive check - final_content must be set
                        if final_content is None:
                            error_msg = f"BUG: final_content is None after regeneration loop for section {section_index}"
                            logger.error(error_msg)
                            raise RuntimeError(error_msg)

                        # Save or update section (using final scores from quality gates)
                        section_result_db = await db.execute(
                            select(DocumentSection).where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                            )
                        )
                        section = _safe_scalar_one_or_none(
                            section_result_db,
                            f"section_lookup_{section_index}",
                        )

                        word_count = len(final_content.split())

                        if section:
                            section.content = final_content
                            section.status = "completed"
                            section.word_count = word_count
                            section.grammar_score = final_grammar_score
                            section.plagiarism_score = final_plagiarism_score
                            section.ai_detection_score = final_ai_score
                            section.quality_score = final_quality_score
                            section.completed_at = datetime.utcnow()
                        else:
                            section = DocumentSection(
                                document_id=document_id,
                                title=section_title,
                                section_index=section_index,
                                content=final_content,
                                status="completed",
                                word_count=word_count,
                                grammar_score=final_grammar_score,
                                plagiarism_score=final_plagiarism_score,
                                ai_detection_score=final_ai_score,
                                quality_score=final_quality_score,
                                completed_at=datetime.utcnow(),
                            )
                            db.add(section)

                        if panel_result is not None:
                            # Assign a NEW dict (JSON columns don't track
                            # in-place mutation)
                            section.quality_panel = panel_result.get("panel")

                        await db.commit()

                        # Academic Quality Engine: persist this section's
                        # cited sources (only the final accepted attempt's;
                        # failed regeneration attempts were discarded above).
                        # section.id is populated post-commit thanks to
                        # expire_on_commit=False. Non-critical: never raises.
                        if settings.CITATION_VERIFICATION_ENABLED:
                            await _persist_cited_sources(
                                db,
                                document_id,
                                section.id,
                                section_result.get("cited_sources") or [],
                            )

                        # Provenance ledger: record this section's pipeline
                        # events (final accepted attempt only; discarded
                        # regeneration attempts leave no trace). Best-effort,
                        # never breaks generation.
                        if settings.PROVENANCE_LEDGER_ENABLED:
                            cited_sources = section_result.get("cited_sources") or []
                            await _record_provenance(
                                db,
                                document_id,
                                stage="retrieval",
                                event_type="rag_retrieved",
                                payload={
                                    "section_index": section_index,
                                    "section_title": section_title,
                                    "sources_used": section_result.get(
                                        "sources_used", 0
                                    ),
                                    "sources": [
                                        {
                                            "title": (s.get("title") or "")[:300],
                                            "doi": s.get("doi"),
                                            "year": s.get("year"),
                                            "verification_status": "unverified",
                                        }
                                        for s in cited_sources[:50]
                                    ],
                                },
                            )
                            await _record_provenance(
                                db,
                                document_id,
                                stage="generation",
                                event_type="section_generated",
                                payload={
                                    "section_index": section_index,
                                    "section_title": section_title,
                                    "provider": document.ai_provider,
                                    "model": document.ai_model,
                                    "word_count": word_count,
                                    "tokens_used": section.tokens_used or 0,
                                    "attempts": attempt_num,
                                },
                            )
                            await _record_provenance(
                                db,
                                document_id,
                                stage="generation",
                                event_type="humanized",
                                payload={
                                    "section_index": section_index,
                                    "ai_score_before": ai_trace.get("initial_ai_score"),
                                    "ai_score_after": ai_trace.get(
                                        "final_ai_score", final_ai_score
                                    ),
                                    "multi_pass": ai_trace.get("multi_pass", False),
                                    "threshold": settings.QUALITY_MAX_AI_DETECTION_SCORE,
                                },
                            )
                            # Honest gate status: "passed" only when every
                            # check actually ran and passed. A failed check
                            # can reach this point only with gates disabled —
                            # record it as failed, not passed.
                            check_statuses = [
                                c["status"]
                                for c in (final_check_breakdown or {}).values()
                            ]
                            overall_gate_status = (
                                "failed"
                                if "failed" in check_statuses
                                else "unchecked"
                                if "unchecked" in check_statuses
                                else "passed"
                            )
                            await _record_provenance(
                                db,
                                document_id,
                                stage="quality",
                                event_type="quality_gate",
                                payload={
                                    "section_index": section_index,
                                    "passed": overall_gate_status == "passed",
                                    "status": overall_gate_status,
                                    "checks": final_check_breakdown,
                                    "gates_enabled": settings.QUALITY_GATES_ENABLED,
                                    "grammar_score": final_grammar_score,
                                    "plagiarism_score": final_plagiarism_score,
                                    "ai_detection_score": final_ai_score,
                                    "quality_score": final_quality_score,
                                },
                            )
                            if panel_result is not None:
                                await _record_provenance(
                                    db,
                                    document_id,
                                    stage="quality",
                                    event_type="panel_review",
                                    payload={
                                        "section_index": section_index,
                                        "overall_score": panel_result.get(
                                            "overall_score"
                                        ),
                                        "passed": panel_result.get("passed"),
                                        "critical_override": panel_result.get(
                                            "critical_override", False
                                        ),
                                        "attempts": attempt_num,
                                        "panel": panel_result.get("panel"),
                                    },
                                )

                        grammar_text = (
                            f"{final_grammar_score:.1f}"
                            if final_grammar_score is not None
                            else "N/A"
                        )
                        plagiarism_text = (
                            f"{final_plagiarism_score:.1f}%"
                            if final_plagiarism_score is not None
                            else "N/A"
                        )
                        ai_text = (
                            f"{final_ai_score:.1f}%"
                            if final_ai_score is not None
                            else "N/A"
                        )
                        quality_text = (
                            f"{final_quality_score:.1f}"
                            if final_quality_score is not None
                            else "N/A"
                        )
                        logger.info(
                            f"Section {section_index} completed - "
                            f"Grammar: {grammar_text}, "
                            f"Plagiarism: {plagiarism_text}, "
                            f"AI Detection: {ai_text}, "
                            f"Quality: {quality_text}"
                        )

                        # WebSocket: Send quality check completion
                        await manager.send_progress(
                            user_id,
                            {
                                "stage": "quality_check",
                                "progress": min(
                                    95, 50 + (section_index / total_sections) * 40
                                ),
                                "message": f"Section {section_index} quality validated",
                                "quality_score": final_quality_score,
                                "quality_passed": not any(
                                    c["status"] != "passed"
                                    for c in (final_check_breakdown or {}).values()
                                ),
                                "quality_status": {
                                    key: c["status"]
                                    for key, c in (final_check_breakdown or {}).items()
                                },
                                "grammar_score": final_grammar_score,
                                "plagiarism_score": final_plagiarism_score,
                                "ai_detection_score": final_ai_score,
                            },
                        )

                        # ✅ TASK 3.7.1: Save checkpoint after section completion
                        try:
                            checkpoint_data = {
                                "document_id": document_id,
                                "last_completed_section_index": section_index,
                                "total_sections": len(sections),
                                "completed_at": datetime.utcnow().isoformat(),
                                "status": "in_progress",
                            }
                            redis = await get_redis()
                            await redis.set(
                                f"checkpoint:doc:{document_id}",
                                json.dumps(checkpoint_data),
                                ex=3600,  # TTL: 1 hour
                            )
                            logger.info(
                                f"✅ Checkpoint saved: section {section_index}/{len(sections)} "
                                f"({int((section_index / len(sections)) * 100)}% complete)"
                            )
                        except Exception as checkpoint_error:
                            # ⚠️ Non-critical: log warning but continue generation
                            logger.warning(
                                f"⚠️ Failed to save checkpoint: {checkpoint_error}"
                            )

                    except QualityThresholdNotMetError as e:
                        # ✅ Quality gates failed after all regeneration attempts
                        logger.error(
                            f"❌ Quality threshold not met for section {section_index}: {e}"
                        )
                        await db.execute(
                            update(DocumentSection)
                            .where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                            )
                            .values(status="failed_quality")
                        )
                        await db.commit()

                        if settings.PROVENANCE_LEDGER_ENABLED:
                            await _record_provenance(
                                db,
                                document_id,
                                stage="quality",
                                event_type="quality_gate",
                                payload={
                                    "section_index": section_index,
                                    "passed": False,
                                    "status": "failed",
                                    "detail": str(e)[:500],
                                },
                            )

                        # Send WebSocket error notification
                        await manager.send_progress(  # was: send_error (method does not exist)
                            user_id,
                            {
                                "error": "quality_threshold_not_met",
                                "section": section_index,
                                "message": f"Section {section_index} quality validation failed after {settings.QUALITY_MAX_REGENERATE_ATTEMPTS + 1} attempts",
                                "details": str(e),
                            },
                        )

                        # Stop generation to avoid incomplete document
                        raise

                    except Exception as e:
                        logger.error(f"Error generating section {section_index}: {e}")
                        await db.execute(
                            update(DocumentSection)
                            .where(
                                DocumentSection.document_id == document_id,
                                DocumentSection.section_index == section_index,
                            )
                            .values(status="failed")
                        )
                        await db.commit()
                        # Stop generation to avoid incomplete document
                        raise

                # Step 4: Check if all sections completed
                sections_result = await db.execute(
                    select(DocumentSection).where(
                        DocumentSection.document_id == document_id,
                        DocumentSection.status == "completed",
                    )
                )
                completed_sections = _safe_scalars_all(
                    sections_result,
                    "completed_sections_lookup",
                )

                if len(completed_sections) == 0:
                    logger.error(f"No sections completed for document {document_id}")
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed")
                    )
                    await db.commit()
                    return

                if len(completed_sections) < total_sections:
                    error_msg = (
                        f"Only {len(completed_sections)}/{total_sections} sections completed "
                        f"for document {document_id}"
                    )
                    logger.error(error_msg)
                    raise QualityThresholdNotMetError(detail=error_msg)

                # Step 4.5: Combine sections into final document content
                logger.info(
                    f"Combining {len(completed_sections)} sections into document {document_id}"
                )
                final_content = "\n\n".join(
                    [
                        f"# {section.title}\n\n{section.content}"
                        for section in sorted(
                            completed_sections, key=lambda s: s.section_index
                        )
                    ]
                )

                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(content=final_content, status="sections_generated")
                )
                await db.commit()

                # Step 4.7: Citation verification + integrity gate
                # (Academic Quality Engine). Strict policy raises
                # CitationIntegrityError here, before export; mark_only and
                # internal failures never block (fail-open).
                if settings.CITATION_VERIFICATION_ENABLED:
                    await _run_citation_verification_stage(db, document_id, user_id)

                # Step 4.8: Claim faithfulness audit (advisory by default;
                # when CLAIM_VERIFICATION_BLOCKING is set, unsupported cited
                # claims raise CitationIntegrityError here, before export)
                if settings.CLAIM_VERIFICATION_ENABLED:
                    await _run_claim_verification_stage(db, document_id, user_id)

                # Step 5: Export to DOCX
                logger.info(f"Exporting document {document_id} to DOCX")
                try:
                    document_service = DocumentService(db)
                    export_result = await document_service.export_document(
                        document_id=document_id, format="docx", user_id=user_id
                    )
                    logger.info(
                        f"Document {document_id} exported successfully: {export_result.get('download_url')}"
                    )

                    if settings.PROVENANCE_LEDGER_ENABLED:
                        export_format = (export_result or {}).get("format", "docx")
                        await _record_provenance(
                            db,
                            document_id,
                            stage="export",
                            event_type="exported",
                            payload={
                                "formats": [export_format],
                                "paths": {
                                    export_format: (export_result or {}).get(
                                        "download_url"
                                    )
                                },
                                "file_size": (export_result or {}).get("file_size"),
                            },
                        )
                except Exception as e:
                    logger.error(f"Failed to export document {document_id}: {e}")
                    # Export failure doesn't fail the entire job, but log it

                # Step 6: Update document status to completed
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(status="completed", completed_at=datetime.utcnow())
                )
                await db.commit()

                logger.info(f"Document {document_id} generation completed successfully")

                # Step 7: Send email notification to user
                try:
                    from app.models.auth import User
                    from app.services.notification_service import notification_service

                    user_result = await db.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = _safe_scalar_one_or_none(
                        user_result,
                        "completion_email_user_lookup",
                    )

                    if user and user.email:
                        await notification_service.send_document_ready_notification(
                            email=user.email,
                            document_title=document.title,
                            document_id=document_id,
                        )
                except Exception as e:
                    logger.warning(f"Failed to send completion email: {e}")

            except Exception as e:
                logger.error(
                    f"Critical error in background document generation: {e}",
                    exc_info=True,
                )
                error_message = str(e)

                # Mark document as failed
                try:
                    # The citation integrity gate already set 'failed_quality'
                    # and committed; don't overwrite it with the generic
                    # 'failed'. Flag off => this exception never exists.
                    if not isinstance(e, CitationIntegrityError):
                        await db.execute(
                            update(Document)
                            .where(Document.id == document_id)
                            .values(status="failed")
                        )
                        await db.commit()

                    # Send failure notification email
                    try:
                        from app.models.auth import User
                        from app.services.notification_service import (
                            notification_service,
                        )

                        user_result = await db.execute(
                            select(User).where(User.id == user_id)
                        )
                        user = _safe_scalar_one_or_none(
                            user_result,
                            "failure_email_user_lookup",
                        )

                        if user and user.email:
                            await notification_service.send_document_failed_notification(
                                email=user.email,
                                document_title=(
                                    document.title if document else "Unknown"
                                ),
                                error_message=error_message[:200],  # Limit length
                            )
                    except Exception as email_error:
                        logger.warning(f"Failed to send failure email: {email_error}")
                except Exception:
                    logger.error(
                        f"Failed to update document {document_id} status to failed"
                    )
                raise
            finally:
                # Always cleanup checkpoint on terminal state to avoid stale recovery data.
                await _clear_generation_checkpoint(
                    document_id, "generate_full_document"
                )

    @staticmethod
    @background_task_error_handler("generate_full_document_async")
    async def generate_full_document_async(
        document_id: int,
        user_id: int,
        job_id: int,
        additional_requirements: str | None = None,
    ) -> None:
        """
        Async version of generate_full_document with job progress tracking.

        Updates AIGenerationJob status and progress throughout generation.

        Args:
            document_id: ID of the document to generate
            user_id: ID of the user owning the document
            job_id: ID of the AIGenerationJob for tracking
            additional_requirements: Optional additional requirements
        """
        # ✅ STEP 1.2: WebSocket heartbeat task (prevents 5-10 min timeouts)
        heartbeat_task = None

        async with database.AsyncSessionLocal() as db:
            try:
                # Update job to running
                await db.execute(
                    update(AIGenerationJob)
                    .where(AIGenerationJob.id == job_id)
                    .values(status="running", progress=0)
                )
                await db.commit()

                # Notify WebSocket clients
                await manager.send_progress(
                    user_id,
                    {
                        "type": "job_started",
                        "job_id": job_id,
                        "document_id": document_id,
                        "status": "running",
                        "progress": 0,
                    },
                )

                # ✅ STEP 1.2: Start heartbeat task to keep WebSocket alive
                heartbeat_task = asyncio.create_task(
                    send_periodic_heartbeat(
                        user_id=user_id,
                        job_id=job_id,
                        document_id=document_id,
                        interval=10,  # 10 seconds (prevents Chrome 5 min, Nginx 60 sec timeouts)
                    )
                )
                logger.info(f"💓 Heartbeat task started for job {job_id}")

                # Call the original generation method
                await BackgroundJobService.generate_full_document(
                    document_id=document_id,
                    user_id=user_id,
                    additional_requirements=additional_requirements,
                )

                # Update job to completed
                await db.execute(
                    update(AIGenerationJob)
                    .where(AIGenerationJob.id == job_id)
                    .values(
                        status="completed", progress=100, completed_at=datetime.utcnow()
                    )
                )
                await db.commit()

                # Notify WebSocket clients
                await manager.send_progress(
                    user_id,
                    {
                        "type": "job_completed",
                        "job_id": job_id,
                        "document_id": document_id,
                        "status": "completed",
                        "progress": 100,
                    },
                )

                logger.info(f"Job {job_id} completed successfully")

            except Exception as e:
                # Update job to failed
                try:
                    await db.execute(
                        update(AIGenerationJob)
                        .where(AIGenerationJob.id == job_id)
                        .values(
                            status="failed",
                            error_message=str(e)[:500],  # Limit error message length
                            success=False,
                            completed_at=datetime.utcnow(),
                        )
                    )
                    await db.commit()

                    # ✅ TASK 3.7.4: Clear checkpoint on failure
                    try:
                        redis = await get_redis()
                        await redis.delete(f"checkpoint:doc:{document_id}")
                        logger.info("✅ Checkpoint cleared after failure")
                    except Exception as checkpoint_error:
                        # ⚠️ Non-critical: log warning
                        logger.warning(
                            f"⚠️ Failed to clear checkpoint on failure: {checkpoint_error}"
                        )

                    # Notify WebSocket clients
                    await manager.send_progress(
                        user_id,
                        {
                            "type": "job_failed",
                            "job_id": job_id,
                            "document_id": document_id,
                            "status": "failed",
                            "error": str(e)[:200],
                        },
                    )
                except Exception:
                    logger.error(f"Failed to update job {job_id} status to failed")
                raise  # Re-raise to maintain error logging

            finally:
                # ✅ STEP 1.2: Cleanup heartbeat task
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass  # Expected when cancelling
                    logger.info(f"💓 Heartbeat task stopped for job {job_id}")

    @staticmethod
    @background_task_error_handler("process_custom_requirement")
    async def process_custom_requirement(
        document_id: int, file_path: str, user_id: int
    ) -> dict[str, Any]:
        """
        Background task to process uploaded custom requirement file

        Extracts text from PDF or DOCX files and stores it for document generation

        Args:
            document_id: ID of the document
            file_path: Path to uploaded file
            user_id: ID of the user

        Returns:
            Dictionary with extracted text and metadata
        """
        async with database.AsyncSessionLocal() as db:
            try:
                logger.info(
                    f"Processing custom requirement for document {document_id}: {file_path}"
                )

                # Verify document ownership
                result = await db.execute(
                    select(Document).where(
                        Document.id == document_id, Document.user_id == user_id
                    )
                )
                document = _safe_scalar_one_or_none(
                    result,
                    "custom_requirement_document_lookup",
                )

                if not document:
                    raise NotFoundError("Document not found")

                # Extract text based on file extension
                extracted_text = ""

                if file_path.endswith(".pdf"):
                    extracted_text = await BackgroundJobService._extract_pdf_text(
                        file_path
                    )
                elif file_path.endswith((".doc", ".docx")):
                    extracted_text = await BackgroundJobService._extract_docx_text(
                        file_path
                    )
                else:
                    raise ValueError(f"Unsupported file format: {file_path}")

                # Store extracted text (can be stored in document metadata or separate table)
                # For now, we'll log it and return it
                logger.info(
                    f"Extracted {len(extracted_text)} characters from {file_path}"
                )

                return {
                    "document_id": document_id,
                    "file_path": file_path,
                    "extracted_text": extracted_text,
                    "text_length": len(extracted_text),
                    "processed_at": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing custom requirement: {e}")
                raise

    @staticmethod
    async def _extract_pdf_text(file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            import PyPDF2

            text = ""
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"

            return text.strip()

        except ImportError as e:
            logger.error("PyPDF2 not installed. Install it with: pip install PyPDF2")
            raise ValueError(
                "PDF extraction not available: PyPDF2 not installed"
            ) from e
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}") from e

    @staticmethod
    async def _extract_docx_text(file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])

            return text.strip()

        except ImportError as e:
            logger.error(
                "python-docx not installed. Install it with: pip install python-docx"
            )
            raise ValueError(
                "DOCX extraction not available: python-docx not installed"
            ) from e
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}")
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}") from e
