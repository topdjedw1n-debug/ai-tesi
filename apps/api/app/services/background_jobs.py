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
from typing import Any, TypeVar

import redis.asyncio as aioredis
from sqlalchemy import select, update

from app.core import database
from app.core.config import settings
from app.core.exceptions import NotFoundError, QualityThresholdNotMetError
from app.models.document import AIGenerationJob, Document, DocumentSection
from app.services.ai_detection_checker import AIDetectionChecker
from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.generator import SectionGenerator
from app.services.ai_pipeline.humanizer import Humanizer
from app.services.ai_service import AIService
from app.services.document_service import DocumentService
from app.services.grammar_checker import GrammarChecker
from app.services.plagiarism_checker import PlagiarismChecker
from app.services.quality_validator import QualityValidator
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


# Type variable for background task functions
F = TypeVar("F", bound=Callable[..., Any])


def background_task_error_handler(task_name: str):
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
                        "args": str(args)[:200],  # Limit log size
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
                job = result.scalar_one_or_none()

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


# ========== Quality Gate Helper Functions (Task 3.2) ==========


async def _check_grammar_quality(
    content: str, language: str, threshold: int
) -> tuple[float | None, int, bool, str | None]:
    """
    Check grammar quality and return results

    Args:
        content: Text to check
        language: Language code (en, de, fr, etc.)
        threshold: Max allowed errors (from QUALITY_MAX_GRAMMAR_ERRORS)

    Returns:
        Tuple of (score, error_count, passed, error_message)
        - score: Grammar score (0-100, None if check failed)
        - error_count: Number of grammar errors found
        - passed: True if error_count <= threshold
        - error_message: Error description if failed, None if passed
    """
    try:
        grammar_checker = GrammarChecker()
        grammar_result = await grammar_checker.check_text(
            text=content, language=language
        )

        if grammar_result.get("checked"):
            matches = grammar_result.get("matches", [])
            error_count = len(matches)

            # Calculate score: max 100, -5 per issue
            score = max(0.0, 100.0 - (error_count * 5.0))

            passed = error_count <= threshold
            error_msg = (
                None if passed else f"Grammar: {error_count} errors (max: {threshold})"
            )

            return (score, error_count, passed, error_msg)
        else:
            # Check failed but don't block (non-critical)
            logger.warning(
                f"Grammar check skipped: {grammar_result.get('error', 'Unknown')}"
            )
            return (None, 0, True, None)  # Pass by default if check unavailable

    except Exception as e:
        logger.error(f"Grammar check exception: {e}")
        return (None, 0, True, None)  # Pass by default on error


async def _check_plagiarism_quality(
    content: str, threshold: float
) -> tuple[float | None, float, bool, str | None]:
    """
    Check plagiarism and return results

    Args:
        content: Text to check
        threshold: Min required uniqueness % (from QUALITY_MIN_PLAGIARISM_UNIQUENESS)

    Returns:
        Tuple of (plagiarism_score, uniqueness, passed, error_message)
        - plagiarism_score: Plagiarism % (0-100, None if check failed)
        - uniqueness: Uniqueness % (100 - plagiarism_score)
        - passed: True if uniqueness >= threshold
        - error_message: Error description if failed, None if passed
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

            return (plagiarism_score, uniqueness, passed, error_msg)
        else:
            # Check failed but don't block (non-critical)
            logger.warning(
                f"Plagiarism check skipped: {plagiarism_result.get('error', 'Unknown')}"
            )
            return (None, 100.0, True, None)  # Pass by default if check unavailable

    except Exception as e:
        logger.error(f"Plagiarism check exception: {e}")
        return (None, 100.0, True, None)  # Pass by default on error


async def _check_ai_detection_quality(
    content: str, threshold: float, humanizer: Humanizer, provider: str, model: str
) -> tuple[float | None, str, str, bool, str | None]:
    """
    Check AI detection score and run multi-pass if needed

    Args:
        content: Text to check
        threshold: Max allowed AI % (from QUALITY_MAX_AI_DETECTION_SCORE)
        humanizer: Humanizer instance for multi-pass
        provider: AI provider (openai/anthropic)
        model: AI model name

    Returns:
        Tuple of (ai_score, final_content, provider_used, passed, error_message)
        - ai_score: AI detection % (0-100, None if check failed)
        - final_content: Content after potential multi-pass humanization
        - provider_used: Detection provider used
        - passed: True if ai_score <= threshold
        - error_message: Error description if failed, None if passed
    """
    try:
        ai_checker = AIDetectionChecker()
        ai_result = await ai_checker.check_text(text=content)

        if ai_result.get("checked"):
            ai_score = ai_result.get("ai_probability", 0.0)
            provider_used = ai_result.get("provider", "unknown")
            final_content = content

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
                )

                ai_score = final_ai_score
                logger.info(f"After multi-pass: AI score = {final_ai_score:.1f}%")

            passed = ai_score <= threshold
            error_msg = (
                None if passed else f"AI detection: {ai_score:.1f}% (max: {threshold}%)"
            )

            return (ai_score, final_content, provider_used, passed, error_msg)
        else:
            # Check failed but don't block (non-critical)
            logger.warning(
                f"AI detection check skipped: {ai_result.get('error', 'Unknown')}"
            )
            return (
                None,
                content,
                "unknown",
                True,
                None,
            )  # Pass by default if check unavailable

    except Exception as e:
        logger.error(f"AI detection check exception: {e}")
        return (None, content, "unknown", True, None)  # Pass by default on error


# ========== End Quality Gate Helpers ==========


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
                document = result.scalar_one_or_none()

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

                # Step 1: Generate outline if not exists
                if not document.outline:
                    logger.info(f"Generating outline for document {document_id}")
                    ai_service = AIService(db)
                    try:
                        await ai_service.generate_outline(
                            document_id=document_id,
                            user_id=user_id,
                            additional_requirements=additional_requirements,
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
                        existing_section = existing_section_result.scalar_one_or_none()

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
                        context_sections = context_result.scalars().all()
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
                        quality_errors = []

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

                            # Generate section with RAG
                            section_result = await section_generator.generate_section(
                                document=document,
                                section_title=section_title,
                                section_index=section_index,
                                provider=document.ai_provider,
                                model=document.ai_model,
                                citation_style=CitationStyle.APA,  # Default to APA
                                humanize=False,  # Will humanize in next step
                                context_sections=context_list,
                                additional_requirements=additional_requirements,
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
                            )

                            # ========== QUALITY GATES START ==========
                            # ✅ BUG FIX: Always run ALL checks (for metrics), only block if gates enabled

                            gates_passed = True
                            attempt_errors = []

                            # GATE 1: Grammar Check (ALWAYS RUN)
                            (
                                grammar_score,
                                grammar_errors,
                                grammar_passed,
                                grammar_error_msg,
                            ) = await _check_grammar_quality(
                                humanized_content,
                                document.language,
                                settings.QUALITY_MAX_GRAMMAR_ERRORS,
                            )
                            final_grammar_score = grammar_score  # Save for DB

                            if not grammar_passed and settings.QUALITY_GATES_ENABLED:
                                gates_passed = False
                                attempt_errors.append(grammar_error_msg)
                                logger.warning(
                                    f"❌ Grammar gate FAILED: {grammar_error_msg}"
                                )
                            else:
                                logger.info(
                                    f"✅ Grammar gate: {grammar_errors} errors (passed={grammar_passed})"
                                )

                            # GATE 2: Plagiarism Check (ALWAYS RUN)
                            (
                                plagiarism_score,
                                uniqueness,
                                plagiarism_passed,
                                plagiarism_error_msg,
                            ) = await _check_plagiarism_quality(
                                humanized_content,
                                settings.QUALITY_MIN_PLAGIARISM_UNIQUENESS,
                            )
                            final_plagiarism_score = plagiarism_score  # Save for DB

                            if not plagiarism_passed and settings.QUALITY_GATES_ENABLED:
                                gates_passed = False
                                attempt_errors.append(plagiarism_error_msg)
                                logger.warning(
                                    f"❌ Plagiarism gate FAILED: {plagiarism_error_msg}"
                                )
                            else:
                                logger.info(
                                    f"✅ Plagiarism gate: {uniqueness:.1f}% unique (passed={plagiarism_passed})"
                                )

                            # GATE 3: AI Detection Check (ALWAYS RUN, includes multi-pass humanization)
                            (
                                ai_score,
                                humanized_content,
                                provider_used,
                                ai_passed,
                                ai_error_msg,
                            ) = await _check_ai_detection_quality(
                                humanized_content,
                                settings.QUALITY_MAX_AI_DETECTION_SCORE,
                                humanizer,
                                document.ai_provider,
                                document.ai_model,
                            )
                            final_ai_score = ai_score  # Save for DB

                            if not ai_passed and settings.QUALITY_GATES_ENABLED:
                                gates_passed = False
                                attempt_errors.append(ai_error_msg)
                                logger.warning(
                                    f"❌ AI detection gate FAILED: {ai_error_msg}"
                                )
                            else:
                                logger.info(
                                    f"✅ AI detection gate: {ai_score:.1f}% AI (passed={ai_passed})"
                                )

                            # ========== QUALITY GATES DECISION ==========

                            if not settings.QUALITY_GATES_ENABLED or gates_passed:
                                # ALL GATES PASSED or GATES DISABLED ✅
                                final_content = humanized_content
                                quality_errors = []  # Clear errors
                                logger.info(
                                    f"✅ Section {section_index} passed all quality gates (enabled={settings.QUALITY_GATES_ENABLED})"
                                )
                                break  # Exit regeneration loop, save section

                            elif attempt < settings.QUALITY_MAX_REGENERATE_ATTEMPTS:
                                # GATES FAILED but ATTEMPTS REMAIN → REGENERATE
                                quality_errors = attempt_errors
                                logger.warning(
                                    f"⚠️ Section {section_index} attempt {attempt_num} failed quality gates: "
                                    f"{', '.join(attempt_errors)}. Regenerating..."
                                )

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
                                raise QualityThresholdNotMetError(detail=error_detail)

                        # ========== REGENERATION LOOP END ==========

                        # If we reached here, section passed all quality gates
                        # Run final quality validation (non-blocking, for stats only)

                        try:
                            logger.info(
                                f"📊 Running quality validation for section {section_index}..."
                            )

                            quality_validator = QualityValidator()
                            quality_result = await quality_validator.validate_section(
                                content=final_content,
                                outline_section={
                                    "title": section_title,
                                    "target_word_count": current_section.get(
                                        "word_count", 500
                                    ),
                                },
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
                        section = section_result_db.scalar_one_or_none()

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

                        await db.commit()
                        logger.info(
                            f"Section {section_index} completed - "
                            f"Grammar: {final_grammar_score:.1f if final_grammar_score else 'N/A'}, "
                            f"Plagiarism: {final_plagiarism_score:.1f if final_plagiarism_score else 'N/A'}%, "
                            f"AI Detection: {final_ai_score:.1f if final_ai_score else 'N/A'}%, "
                            f"Quality: {final_quality_score:.1f if final_quality_score else 'N/A'}"
                        )

                        # WebSocket: Send quality check completion
                        await manager.send_progress(
                            user_id,
                            {
                                "stage": "quality_check",
                                "progress": min(95, 50 + (section_index / total_sections) * 40),
                                "message": f"Section {section_index} quality validated",
                                "quality_score": final_quality_score,
                                "quality_passed": True,
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
                            .values(status="failed_quality", error_message=str(e))
                        )
                        await db.commit()

                        # Send WebSocket error notification
                        await manager.send_error(
                            user_id,
                            {
                                "error": "quality_threshold_not_met",
                                "section": section_index,
                                "message": f"Section {section_index} quality validation failed after {settings.QUALITY_MAX_REGENERATE_ATTEMPTS + 1} attempts",
                                "details": str(e),
                            },
                        )

                        # Continue with next section (partial completion strategy)
                        continue

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
                        # Continue with next section instead of failing completely
                        continue

                # Step 4: Check if all sections completed
                sections_result = await db.execute(
                    select(DocumentSection).where(
                        DocumentSection.document_id == document_id,
                        DocumentSection.status == "completed",
                    )
                )
                completed_sections = sections_result.scalars().all()

                if len(completed_sections) == 0:
                    logger.error(f"No sections completed for document {document_id}")
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed")
                    )
                    await db.commit()
                    return

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

                # ✅ TASK 3.7.3: Clear checkpoint on success
                try:
                    redis = await get_redis()
                    await redis.delete(f"checkpoint:doc:{document_id}")
                    logger.info("✅ Checkpoint cleared after successful completion")
                except Exception as checkpoint_error:
                    # ⚠️ Non-critical: log warning
                    logger.warning(f"⚠️ Failed to clear checkpoint: {checkpoint_error}")

                logger.info(f"Document {document_id} generation completed successfully")

                # Step 7: Send email notification to user
                try:
                    from app.models.auth import User
                    from app.services.notification_service import notification_service

                    user_result = await db.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = user_result.scalar_one_or_none()

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
                        user = user_result.scalar_one_or_none()

                        if user and user.email:
                            await (
                                notification_service.send_document_failed_notification(
                                    email=user.email,
                                    document_title=document.title
                                    if document
                                    else "Unknown",
                                    error_message=error_message[:200],  # Limit length
                                )
                            )
                    except Exception as email_error:
                        logger.warning(f"Failed to send failure email: {email_error}")
                except Exception:
                    logger.error(
                        f"Failed to update document {document_id} status to failed"
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
                document = result.scalar_one_or_none()

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
