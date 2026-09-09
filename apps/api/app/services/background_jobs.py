"""Full-document generation pipeline executed by the durable DB worker."""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.config import settings
from app.core.exceptions import (
    CitationIntegrityError,
    NotFoundError,
)
from app.models.document import (
    AIGenerationJob,
    Document,
)
from app.services.ai_detection_checker import AIDetectionChecker
from app.services.ai_pipeline.citation_formatter import (
    CitationStyle,
)
from app.services.ai_pipeline.humanizer import Humanizer
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_identity import sources_equivalent
from app.services.ai_pipeline.source_pack import (
    PackedSource,
    SourcePack,
    SourcePackBuilder,
)
from app.services.ai_service import AIService
from app.services.citation_verifier import (
    CitationVerifier,
)
from app.services.claim_verification_stage import (
    run_claim_verification_stage,
)
from app.services.cost_estimator import UsageTracker
from app.services.db_helpers import (
    safe_scalar_one_or_none as _safe_scalar_one_or_none,
)
from app.services.document_service import DocumentService
from app.services.generation_policy import (
    AdvisoryConfig,
    translation_cache,
    warning_mode,
)
from app.services.generation_worker import (
    GenerationLeaseLostError,
    claim_generation_job_by_id,
    enqueue_artifact_deletions,
    generation_lease_is_owned,
    persist_generation_artifact,
    renew_generation_lease,
)
from app.services.grammar_checker import GrammarChecker
from app.services.grounding_gate import GroundingResult
from app.services.plagiarism_checker import PlagiarismChecker
from app.services.quality_validator import QualityValidator
from app.services.source_verification_stage import (
    map_verification_status as _map_verification_status,  # noqa: F401
)
from app.services.source_verification_stage import (
    run_citation_verification_stage,
)
from app.services.storage_service import StorageService
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)

# Redis client for checkpoints (initialized on first use)
_redis_client: aioredis.Redis | None = None


def _resolve_citation_style(raw_style: str | None) -> CitationStyle:
    """Resolve a durable document setting without letting legacy data crash a job."""
    try:
        return CitationStyle(str(raw_style or "apa").lower())
    except ValueError:
        logger.warning(
            "Unsupported stored citation style %r; falling back to APA", raw_style
        )
        return CitationStyle.APA


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


async def _assert_generation_lease(
    job_id: int | None,
    lease_owner: str | None,
    lease_token: str | None,
) -> None:
    """Fence stale executors before they persist or export new work."""
    if job_id is None or lease_owner is None or lease_token is None:
        return
    async with database.AsyncSessionLocal() as lease_db:
        if not await generation_lease_is_owned(
            lease_db,
            job_id=job_id,
            worker_id=lease_owner,
            lease_token=lease_token,
        ):
            raise GenerationLeaseLostError(
                f"Generation lease for job {job_id} is owned by another worker"
            )


async def _export_document_with_fence(
    db: AsyncSession,
    *,
    document_service: DocumentService,
    document_id: int,
    user_id: int,
    job_id: int,
    lease_owner: str,
    lease_token: str,
) -> dict[str, Any]:
    """Upload then atomically bind an artifact, deleting any unbound blob."""
    export_task = asyncio.create_task(
        document_service.export_document(
            document_id=document_id,
            format="docx",
            user_id=user_id,
            persist_pointer=False,
        )
    )
    try:
        export_result = await asyncio.shield(export_task)
    except asyncio.CancelledError:
        # A synchronous SDK upload continues in its thread after cancellation.
        # Wait for its bounded result so an uploaded, unbound object is cleaned
        # before the executor exits. It must never acquire a document pointer.
        async def clean_up_cancelled_export() -> None:
            try:
                cancelled_result = await export_task
            except Exception:
                logger.exception("Export failed while cancelling job %s", job_id)
            else:
                cancelled_path = str(cancelled_result["storage_path"])
                try:
                    if not await StorageService().delete_file(cancelled_path):
                        raise RuntimeError("storage did not confirm deletion")
                except Exception:
                    await _enqueue_deletion_outbox_best_effort(
                        cancelled_path, "unbound"
                    )

        cleanup_task = asyncio.create_task(clean_up_cancelled_export())
        while not cleanup_task.done():
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError:
                continue
        cleanup_task.result()
        raise
    uploaded_path = str(export_result["storage_path"])
    storage = StorageService()
    binding_task = asyncio.create_task(
        persist_generation_artifact(
            db,
            job_id=job_id,
            worker_id=lease_owner,
            lease_token=lease_token,
            document_id=document_id,
            artifact_format="docx",
            storage_path=uploaded_path,
            artifact_sha256=str(export_result["artifact_sha256"]),
        )
    )
    try:
        previous_path = await asyncio.shield(binding_task)
    except asyncio.CancelledError:
        # A commit can win the race with cancellation. Resolve its outcome
        # before deciding whether the uploaded object is still unbound.
        while not binding_task.done():
            try:
                await asyncio.shield(binding_task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if binding_task.exception() is not None:
            try:
                if not await storage.delete_file(uploaded_path):
                    raise RuntimeError("storage did not confirm deletion")
            except Exception:
                await _enqueue_deletion_outbox_best_effort(uploaded_path, "unbound")
        raise
    except BaseException:
        try:
            if not await storage.delete_file(uploaded_path):
                raise RuntimeError("storage did not confirm deletion")
        except Exception as cleanup_error:
            logger.error(
                "Failed to delete unbound artifact %s: %s (outbox will retry)",
                uploaded_path,
                cleanup_error,
            )
            await _enqueue_deletion_outbox_best_effort(uploaded_path, "unbound")
        raise
    if previous_path and previous_path != uploaded_path:
        try:
            if not await storage.delete_file(previous_path):
                raise RuntimeError("storage did not confirm deletion")
        except Exception as cleanup_error:
            logger.warning(
                "Failed to delete replaced artifact %s: %s (outbox will retry)",
                previous_path,
                cleanup_error,
            )
            await _enqueue_deletion_outbox_best_effort(previous_path, "replaced")
    return export_result


async def _enqueue_deletion_outbox_best_effort(path: str, reason: str) -> None:
    """Record a failed blob deletion for the worker sweep to retry.

    Runs in its own short session because the caller's transaction is being
    unwound; if even this fails, the log line above is the last trace.
    """
    try:
        async with database.AsyncSessionLocal() as outbox_db:
            await enqueue_artifact_deletions(outbox_db, [path], reason=reason)
            await outbox_db.commit()
    except Exception:
        logger.exception("Failed to enqueue deletion outbox entry for %s", path)


async def _send_terminal_failure_notification(
    document_id: int, user_id: int, error_message: str
) -> None:
    """Notify only after the durable retry budget is genuinely exhausted."""
    try:
        from app.models.auth import User
        from app.services.notification_service import notification_service

        async with database.AsyncSessionLocal() as notification_db:
            user_result = await notification_db.execute(
                select(User).where(User.id == user_id)
            )
            user = _safe_scalar_one_or_none(
                user_result, "terminal_failure_email_user_lookup"
            )
            document_result = await notification_db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = _safe_scalar_one_or_none(
                document_result, "terminal_failure_email_document_lookup"
            )
        if user and user.email:
            await notification_service.send_document_failed_notification(
                email=user.email,
                document_title=document.title if document else "Unknown",
                error_message=error_message[:200],
            )
    except Exception as email_error:
        logger.warning("Failed to send terminal failure email: %s", email_error)


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
    user_id: int,
    job_id: int,
    document_id: int,
    interval: int = 10,
    *,
    lease_owner: str | None = None,
    lease_token: str | None = None,
    lease_seconds: int | None = None,
) -> bool:
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

            # Renew the durable DB lease before sending the cosmetic WebSocket
            # heartbeat. A missing/mismatched owner means another process owns
            # recovery now and this executor must stop.
            async with database.AsyncSessionLocal() as db:
                if lease_owner is not None and lease_token is not None:
                    renewed = await renew_generation_lease(
                        db,
                        job_id=job_id,
                        worker_id=lease_owner,
                        lease_token=lease_token,
                        lease_seconds=lease_seconds,
                    )
                    if not renewed:
                        logger.warning(
                            "Generation lease lost for job %s (owner %s)",
                            job_id,
                            lease_owner,
                        )
                        return False
                elif lease_owner is None and lease_token is None:
                    # Backwards-compatible status-only heartbeat for legacy
                    # direct tests and disabled legacy endpoints.
                    result = await db.execute(
                        select(AIGenerationJob).where(AIGenerationJob.id == job_id)
                    )
                    job = _safe_scalar_one_or_none(result, "heartbeat_job_lookup")
                    if not job or job.status not in ["running", "generating"]:
                        logger.info(
                            "Heartbeat stopped: job %s status=%s",
                            job_id,
                            job.status if job else "not_found",
                        )
                        return False
                else:
                    logger.error(
                        "Heartbeat stopped: incomplete fencing lease for job %s",
                        job_id,
                    )
                    return False

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
            return True
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
    usage_tracker: UsageTracker | None = None,
    academic_brief: dict[str, Any] | None = None,
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
        validator = QualityValidator(
            ai_service=AIService(db, usage_tracker=usage_tracker)
        )
        return await validator.validate_section(
            content=content,
            outline_section={
                "title": section_title,
                "target_word_count": target_word_count,
                "academic_context": academic_brief or {},
            },
        )
    except Exception as e:
        logger.error(f"Reviewer panel crashed for section '{section_title}': {e}")
        return None


# ========== Quality Gate Helper Functions (Task 3.2) ==========


# Bracketed in-text citation anchors ("[Rossi2021, 2021]", "[Smith2020;
# Lee2019]") — stripped before the LanguageTool check (see
# _check_grammar_quality). Same shape as text_utils._CITATION_RE.
_CITATION_ANCHOR_RE = re.compile(r"\[[^\]]*\]")

# Whitespace artifacts left by anchor stripping: "word [X] word" becomes
# "word   word" and "word [X]." becomes "word .". LanguageTool flags both
# (WHITESPACE_RULE / COMMA_PARENTHESIS_WHITESPACE) at -5 points each, so
# without normalisation the stripping CREATES more errors than it removes.
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,;:!?])")

# Markdown structure the writer emits ("# 1. Introduzione", "## 1.1 …",
# "**termine**", "- punto elenco"): LanguageTool reads the syntax characters
# as prose and flags casing/punctuation on every heading and list line
# (drill 2026-07-10, docs 52/56: 29-38 "grammar errors" on clean Italian).
# Strip the MARKUP, keep the text.
_MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1")
_MD_LIST_RE = re.compile(r"^\s{0,3}[-*+]\s+", re.MULTILINE)


def strip_citation_anchors(content: str) -> str:
    """Remove bracketed citation anchors plus markdown markup, and normalise
    the whitespace they leave behind, so LanguageTool sees clean prose."""
    text = _CITATION_ANCHOR_RE.sub(" ", content)
    text = _MD_HEADING_RE.sub("", text)
    text = _MD_EMPHASIS_RE.sub(r"\2", text)
    text = _MD_LIST_RE.sub("", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return text


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
        # Strip bracketed citation anchors ("[Rossi2021, 2021]") before the
        # check: LanguageTool flags them (casing/whitespace rules) and at
        # -5 points per match they tanked real grammar scores (95 -> 60-70).
        # Offsets are not mapped back — only count/score are used downstream.
        checked_text = strip_citation_anchors(content)
        grammar_checker = GrammarChecker()
        grammar_result = await grammar_checker.check_text(
            text=checked_text, language=language
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
            # Scale the budget with length so long sections aren't punished
            # for volume: the absolute value above becomes a floor for short
            # texts, and words/1000 * QUALITY_GRAMMAR_ERRORS_PER_1000 governs
            # beyond ~1000 words (Validation-6 length-bias fix).
            if settings.QUALITY_GRAMMAR_ERRORS_PER_1000 > 0:
                word_count = len(checked_text.split())
                effective_threshold = max(
                    effective_threshold,
                    int(word_count / 1000 * settings.QUALITY_GRAMMAR_ERRORS_PER_1000),
                )

            # Calculate score: max 100, -5 per issue
            score = max(0.0, 100.0 - (error_count * 5.0))

            passed = error_count <= effective_threshold
            error_msg = None
            if not passed:
                # Name the top offending rules: "38 errors" alone is
                # undiagnosable in production logs (drill 2026-07-10).
                rule_counts: dict[str, int] = {}
                for match in matches:
                    rule_id = "?"
                    if isinstance(match, dict):
                        rule = match.get("rule")
                        rule_id = str(
                            match.get("rule_id")
                            or (rule.get("id") if isinstance(rule, dict) else rule)
                            or "?"
                        )
                    rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
                top_rules = ", ".join(
                    f"{rule_id}x{count}"
                    for rule_id, count in sorted(
                        rule_counts.items(), key=lambda kv: -kv[1]
                    )[:5]
                )
                error_msg = (
                    f"Grammar: {error_count} errors "
                    f"(max: {effective_threshold}); top rules: {top_rules}"
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

            # If score too high, try multi-pass humanization (unless the
            # humanizer is disabled — Block-1 measures the raw writer).
            if (
                ai_score > threshold
                and settings.HUMANIZER_ENABLED
                and not warning_mode.get()
            ):
                logger.info(
                    f"AI score {ai_score:.1f}% > {threshold}%, running multi-pass..."
                )

                final_content, final_ai_score = await humanizer.humanize_multi_pass(
                    text=content,
                    provider=provider,
                    model=model,
                    target_ai_score=threshold - 5.0,  # Aim 5% below threshold
                    max_attempts=3,
                    preserve_citations=True,
                    language=language,
                    score_trace=score_trace,
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
        config=AdvisoryConfig(settings) if warning_mode.get() else settings,
        verifier_factory=CitationVerifier,
        send_progress=_safe_send_progress,
    )


# ========== Claim Faithfulness Helpers (Academic Quality Engine) ==========


async def _run_claim_verification_stage(
    db: AsyncSession,
    document_id: int,
    user_id: int,
    usage_tracker: UsageTracker | None = None,
    job_id: int | None = None,
) -> None:
    """
    Thin wrapper around claim_verification_stage.run_claim_verification_stage.

    Passes this module's globals (settings, AIService, _safe_send_progress)
    at call time so test monkeypatches on app.services.background_jobs keep
    reaching the stage.
    """

    def ai_service_factory(session: AsyncSession) -> AIService:
        return AIService(session, usage_tracker=usage_tracker)

    await run_claim_verification_stage(
        db,
        document_id,
        user_id,
        config=AdvisoryConfig(settings) if warning_mode.get() else settings,
        ai_service_factory=ai_service_factory,
        send_progress=_safe_send_progress,
        job_id=job_id,
    )


# ========== End Citation Verification Helpers ==========


async def _translate_pack_terms(
    ai_service: AIService,
    topic: str,
    section_titles: list[str] | None,
) -> tuple[str | None, list[str] | None]:
    """
    Translate topic + section titles to English for the bilingual source pack.

    One small LLM call (purpose="pack_translation"); its tokens fall into the
    caller's usage tracker like every other pipeline call. NEVER harder-fails
    the build: any provider error or malformed response degrades to
    (None, None) with a warning, and the pack is built monolingually as before.
    """
    titles = [t.strip() for t in (section_titles or []) if (t or "").strip()]
    prompt = (
        "Translate this academic thesis topic and section titles into English "
        "for scholarly literature search.\n"
        "Return ONLY a JSON object exactly of the form "
        '{"topic": "...", "section_titles": ["...", "..."]} with no other text.\n'
        f"Topic: {topic}\n"
        f"Section titles (JSON): {json.dumps(titles, ensure_ascii=False)}"
    )
    try:
        response = await ai_service.call_with_fallback(
            prompt, purpose="pack_translation"
        )
        alt_topic = response.get("topic")
        alt_titles = response.get("section_titles")
        if not isinstance(alt_topic, str) or not alt_topic.strip():
            raise ValueError(f"invalid translated topic: {alt_topic!r}")
        if not isinstance(alt_titles, list) or not all(
            isinstance(t, str) for t in alt_titles
        ):
            raise ValueError("invalid translated section_titles")
        return (
            alt_topic.strip(),
            [t.strip() for t in alt_titles if t.strip()],
        )
    except Exception as e:
        logger.warning(
            f"⚠️ Source-pack translation failed, building monolingual pack: {e}"
        )
        return None, None


def _merge_source_packs(
    base_pack: SourcePack,
    additional_pack: SourcePack,
    *,
    limit: int | None = None,
) -> SourcePack:
    """Preserve the base pack first; new candidates fill the remaining slots.

    Equivalent sources are kept once. Key collisions resolve in favour of the
    base pack; the additional source gets a suffixed key or is skipped. This
    keeps uploaded sources immutable and also lets preflight retain the
    already-selected topic pack while adding section-specific candidates.
    """
    resolved_limit = limit or settings.SOURCE_PACK_TARGET_SIZE
    taken = {ps.citation_key.lower() for ps in base_pack.sources}
    merged = list(base_pack.sources)
    for packed in getattr(additional_pack, "sources", None) or []:
        if len(merged) >= resolved_limit:
            break
        if any(
            sources_equivalent(existing.source, packed.source) for existing in merged
        ):
            continue
        key = packed.citation_key
        if key.lower() in taken:
            for suffix in "bcdefghijklmnopqrstuvwxyz":
                candidate = f"{key}{suffix}"
                if candidate.lower() not in taken:
                    key = candidate
                    break
            else:
                continue
            packed = PackedSource(packed.source, key, packed.on_topic_score)
        taken.add(key.lower())
        merged.append(packed)
    context_capacity = max(resolved_limit - len(merged), 0)
    merged_context = [
        *list(getattr(base_pack, "context_sources", None) or []),
        *list(getattr(additional_pack, "context_sources", None) or []),
    ][:context_capacity]
    pack = SourcePack(
        document_id=base_pack.document_id,
        topic=base_pack.topic,
        sources=merged,
        underfilled=len(merged) < resolved_limit,
        bilingual=bool(
            getattr(base_pack, "bilingual", False)
            or getattr(additional_pack, "bilingual", False)
        ),
        provider_errors=[
            *list(getattr(base_pack, "provider_errors", []) or []),
            *list(getattr(additional_pack, "provider_errors", []) or []),
        ],
        context_sources=merged_context,
        retrieval_trace=[*base_pack.retrieval_trace, *additional_pack.retrieval_trace],
    )
    pack.passages = base_pack.passages
    return pack


async def _build_source_pack(
    db: AsyncSession,
    document: Document,
    section_titles: list[str] | None = None,
    ai_service: AIService | None = None,
    *,
    target_size: int | None = None,
    allow_threshold_relaxation: bool = True,
    retrieval_page: int = 1,
    raise_on_provider_error: bool = True,
) -> Any:
    """
    Thin wrapper around SourcePackBuilder.build for the upfront source pack.

    Reads this module's `settings` global at call time so test monkeypatches on
    app.services.background_jobs keep working, mirroring the other stage
    wrappers. Returns a SourcePack (never raises — builder degrades gracefully).
    section_titles is set on the post-outline rebuild so queries cover every
    promised section, not just the bare topic.
    Provider exceptions are retained in the returned pack by default so an
    initial outage cannot be mistaken for a definitive lack of sources.

    When ai_service is provided, the bilingual flag is on and the document is
    not in English, topic + titles are first translated to English so the pack
    is queried and scored in both languages (translation failure degrades to
    the monolingual build). Translation lives HERE, not in the builder, so the
    builder stays pure/deterministic and the LLM spend lands in job usage.
    """
    alt_topic: str | None = None
    alt_titles: list[str] | None = None
    if warning_mode.get():
        from app.services.brief_source_scopes import brief_source_scopes

        section_titles = (
            brief_source_scopes(document.additional_requirements, document.outline)
            or section_titles
        )
    if (
        settings.SOURCE_PACK_BILINGUAL_ENABLED
        and ai_service is not None
        and not str(document.language or "").lower().startswith("en")
    ):
        translated_scopes = (
            (section_titles or [])[:4] if warning_mode.get() else section_titles
        )
        cache = translation_cache.get() if warning_mode.get() else None
        cache_key = json.dumps(
            [str(document.topic), translated_scopes], ensure_ascii=False
        )
        if cache is not None and cache_key in cache:
            alt_topic, alt_titles = cache[cache_key]
        else:
            alt_topic, alt_titles = await _translate_pack_terms(
                ai_service, str(document.topic), translated_scopes
            )
            if cache is not None:
                cache[cache_key] = (alt_topic, alt_titles)
    builder = SourcePackBuilder()
    return await builder.build(
        topic=str(document.topic),
        language=str(document.language),
        document_id=int(document.id),
        target_size=target_size or settings.SOURCE_PACK_TARGET_SIZE,
        min_on_topic_score=settings.SOURCE_PACK_MIN_ON_TOPIC_SCORE,
        section_titles=section_titles,
        alt_topic=alt_topic,
        alt_section_titles=alt_titles,
        allow_threshold_relaxation=allow_threshold_relaxation,
        retrieval_page=retrieval_page,
        raise_on_provider_error=raise_on_provider_error,
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
        f"no supporting listed source, omit the unsupported detail or disclose the evidence gap."
    )


def _claim_sources_for_attempt(
    persisted_sources: list[Any], section_result: dict[str, Any]
) -> list[Any]:
    """Add current legacy-RAG sources without duplicating persisted pack rows."""
    sources = list(persisted_sources)
    for raw in section_result.get("cited_sources") or []:
        candidate = SourceDoc(
            title=str(raw.get("title") or ""),
            authors=list(raw.get("authors") or []),
            year=int(raw.get("year") or 0),
            abstract=raw.get("abstract"),
            paper_id=raw.get("paper_id"),
            venue=raw.get("venue"),
            citation_count=raw.get("citation_count"),
            url=raw.get("url"),
            doi=raw.get("doi"),
            provider=raw.get("provider"),
            source_type=raw.get("source_type"),
        )
        if candidate.title and not any(
            sources_equivalent(existing, candidate) for existing in sources
        ):
            sources.append(candidate)
    return sources


def _augment_with_claim_feedback(
    base_requirements: str | None, summary: dict[str, Any]
) -> str:
    unsupported = [
        claim
        for claim in summary.get("claims") or []
        if claim.get("verdict") == "unsupported"
    ][:5]
    if not unsupported:
        return base_requirements or ""
    lines = []
    for claim in unsupported:
        lines.append(
            "- Claim: "
            + str(claim.get("sentence") or "")[:300]
            + " | Citation: "
            + str(claim.get("citation") or "")
            + " | Problem: "
            + str(claim.get("explanation") or "")[:240]
        )
    prefix = f"{base_requirements}\n\n" if base_requirements else ""
    return (
        prefix + "The previous draft contained cited claims that its sources did not "
        "support. For each item below, support it accurately, soften it, replace "
        "it with a supported claim, or remove it. Never invent evidence:\n"
        + "\n".join(lines)
    )


def _assert_rewrite_citation_keys_unchanged(
    original_keys: list[str] | None,
    rewritten_keys: list[str] | None,
    *,
    stage: str,
) -> None:
    """A rewrite may move citations, but it may not add or drop sources."""
    before = {str(key) for key in original_keys or [] if key}
    after = {str(key) for key in rewritten_keys or [] if key}
    if before == after:
        return
    added = sorted(after - before)
    removed = sorted(before - after)
    details: list[str] = []
    if added:
        details.append("added: " + ", ".join(added[:10]))
    if removed:
        details.append("removed: " + ", ".join(removed[:10]))
    raise CitationIntegrityError(
        detail=f"{stage} changed the section's citation set ({'; '.join(details)})"
    )


class BackgroundJobService:
    """Service for background document generation tasks"""

    @staticmethod
    async def generate_full_document_async(
        document_id,
        user_id,
        job_id,
        additional_requirements=None,
        lease_owner=None,
        lease_token=None,
    ):
        """Compatibility for existing queue callers; all execution uses v2."""
        from app.services.executor_v2.run import run
        from app.services.generation_worker import ClaimedGenerationJob

        async with database.AsyncSessionLocal() as db:
            if lease_owner is None:
                claimed = await claim_generation_job_by_id(
                    db, job_id=job_id, worker_id=f"direct:{uuid.uuid4().hex}"
                )
            else:
                row = await db.get(AIGenerationJob, job_id)
                claimed = ClaimedGenerationJob(
                    job_id,
                    document_id,
                    user_id,
                    lease_owner,
                    lease_token,
                    row.attempt_count,
                    row.max_attempts,
                    dict(row.request_payload or {}),
                )
        if claimed:
            await run(claimed)

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
