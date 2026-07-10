"""Durable database-backed worker for full-document generation.

The API transaction only creates an ``AIGenerationJob`` row. Every API process
may poll the same table, but an atomic row lease makes one process the sole
executor. A heartbeat extends that lease; an expired lease is recoverable after
a crash, while bounded attempts prevent a permanently broken job from looping
forever.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.config import settings
from app.models.document import (
    AIGenerationJob,
    ArtifactDeletionOutbox,
    Document,
    DocumentSection,
    ProductionCase,
)
from app.services.generation_contract import (
    generation_contract_error,
    generation_contract_sha256,
)

if TYPE_CHECKING:
    from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

RetryDecision = Literal["retry", "failed", "lost"]


class GenerationLeaseLostError(RuntimeError):
    """The current process is no longer allowed to mutate this generation."""


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp suitable for PostgreSQL TIMESTAMPTZ."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class ClaimedGenerationJob:
    """Immutable execution input captured by a successful lease acquisition."""

    id: int
    document_id: int
    user_id: int
    lease_owner: str
    lease_token: str
    attempt_count: int
    max_attempts: int
    request_payload: dict[str, Any]

    @property
    def additional_requirements(self) -> str | None:
        value = self.request_payload.get("additional_requirements")
        return str(value) if value is not None else None


def _generation_contract_error(
    *,
    document: Document | None,
    production_case: ProductionCase | None,
    job_user_id: int | None,
    request_payload: Any,
    require_running_token: bool = False,
    lease_owner: str | None = None,
    lease_token: str | None = None,
    lease_expires_at: datetime | None = None,
) -> str | None:
    """Return why a durable full-document job is unsafe to execute.

    This is deliberately independent from the HTTP endpoint.  A row can be
    inserted by a payment webhook, an older deployment, or direct SQL, so the
    worker must enforce the Italian MVP contract again at the trust boundary.
    """
    if document is None:
        return "document does not exist"
    if job_user_id is None or int(document.user_id) != int(job_user_id):
        return "job user does not own the document"
    if not isinstance(request_payload, dict):
        return "request_payload must be a JSON object"
    if "additional_requirements" not in request_payload:
        return "request_payload is missing additional_requirements"
    run_requirements = request_payload.get("additional_requirements")
    if run_requirements is not None and not isinstance(run_requirements, str):
        return "additional_requirements must be text or null"
    document_error = generation_contract_error(document)
    if document_error is not None:
        return document_error
    stored_contract = request_payload.get("generation_contract_sha256")
    if not isinstance(stored_contract, str) or len(stored_contract) != 64:
        return "request_payload is missing generation_contract_sha256"
    expected_contract = generation_contract_sha256(
        document,
        production_case,
        run_requirements,
    )
    if stored_contract != expected_contract:
        return "generation contract changed after enqueue"
    if require_running_token and (
        not lease_owner or not lease_token or lease_expires_at is None
    ):
        return "running job has no complete fencing lease"
    return None


async def _revoke_failed_generation_release(
    db: AsyncSession, *, document_id: int
) -> None:
    """Fail closed: a failed generation cannot keep a releasable snapshot."""
    await db.execute(
        update(ProductionCase)
        .where(ProductionCase.document_id == document_id)
        .values(
            generation_status="failed",
            delivery_status="not_ready",
            release_status="blocked",
            released_at=None,
            released_docx_path=None,
            released_pdf_path=None,
            released_docx_sha256=None,
            released_pdf_sha256=None,
            release_version=func.coalesce(ProductionCase.release_version, 0) + 1,
        )
    )


def _claimable_predicate(now: datetime):
    queued_due = and_(
        AIGenerationJob.status == "queued",
        or_(
            AIGenerationJob.available_at.is_(None),
            AIGenerationJob.available_at <= now,
        ),
    )
    stale_running = and_(
        AIGenerationJob.status == "running",
        or_(
            AIGenerationJob.lease_expires_at.is_(None),
            AIGenerationJob.lease_expires_at <= now,
        ),
    )
    attempts_left = func.coalesce(AIGenerationJob.attempt_count, 0) < func.coalesce(
        AIGenerationJob.max_attempts, settings.GENERATION_JOB_MAX_ATTEMPTS
    )
    return and_(or_(queued_due, stale_running), attempts_left)


async def _claim_job(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_seconds: int,
    now: datetime | None,
) -> ClaimedGenerationJob | None:
    """Compare-and-swap one eligible row into a leased running state."""
    lease_token = uuid.uuid4().hex

    # Global cross-path order is Job -> Document -> ProductionCase. Acquire the
    # job row before reading the clock so a contender that waited on the lock
    # cannot create an already-expired lease.
    locked_job_id = (
        await db.execute(
            select(AIGenerationJob.id)
            .where(AIGenerationJob.id == job_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if locked_job_id is None:
        await db.rollback()
        return None
    claim_time = now or utc_now()
    lease_expires_at = claim_time + timedelta(seconds=max(1, lease_seconds))

    result = await db.execute(
        update(AIGenerationJob)
        .where(
            AIGenerationJob.id == job_id,
            _claimable_predicate(claim_time),
        )
        .values(
            status="running",
            lease_owner=worker_id,
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
            heartbeat_at=claim_time,
            attempt_count=func.coalesce(AIGenerationJob.attempt_count, 0) + 1,
            completed_at=None,
        )
        .returning(
            AIGenerationJob.id,
            AIGenerationJob.document_id,
            AIGenerationJob.user_id,
            AIGenerationJob.lease_owner,
            AIGenerationJob.lease_token,
            AIGenerationJob.attempt_count,
            AIGenerationJob.max_attempts,
            AIGenerationJob.request_payload,
        )
    )
    row = result.first()
    if row is None:
        await db.rollback()
        return None

    mapping = row._mapping
    document = None
    production_case = None
    if mapping["document_id"] is not None:
        document = (
            await db.execute(
                select(Document)
                .where(Document.id == int(mapping["document_id"]))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        production_case = (
            await db.execute(
                select(ProductionCase)
                .where(ProductionCase.document_id == int(mapping["document_id"]))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    contract_error = _generation_contract_error(
        document=document,
        production_case=production_case,
        job_user_id=mapping["user_id"],
        request_payload=mapping["request_payload"],
        require_running_token=True,
        lease_owner=mapping["lease_owner"],
        lease_token=mapping["lease_token"],
        lease_expires_at=lease_expires_at,
    )
    if contract_error is not None:
        # Invalid/legacy rows are quarantined while this claim still owns the
        # job lock. They can never fall through to the generation pipeline.
        await db.execute(
            update(AIGenerationJob)
            .where(
                AIGenerationJob.id == job_id,
                AIGenerationJob.lease_owner == worker_id,
                AIGenerationJob.lease_token == lease_token,
            )
            .values(
                status="failed",
                success=False,
                error_message=f"Quarantined generation job: {contract_error}"[:500],
                completed_at=claim_time,
                heartbeat_at=claim_time,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
            )
        )
        if document is not None and document.status != "failed_quality":
            document.status = "failed"
            await _revoke_failed_generation_release(db, document_id=int(document.id))
        await db.commit()
        logger.error("Quarantined generation job %s: %s", job_id, contract_error)
        return None

    await db.commit()
    return ClaimedGenerationJob(
        id=int(mapping["id"]),
        document_id=int(mapping["document_id"]),
        user_id=int(mapping["user_id"]),
        lease_owner=str(mapping["lease_owner"]),
        lease_token=str(mapping["lease_token"]),
        attempt_count=int(mapping["attempt_count"] or 0),
        max_attempts=int(
            mapping["max_attempts"] or settings.GENERATION_JOB_MAX_ATTEMPTS
        ),
        request_payload=dict(mapping["request_payload"] or {}),
    )


async def claim_next_generation_job(
    db: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int | None = None,
    now: datetime | None = None,
) -> ClaimedGenerationJob | None:
    """Atomically lease the oldest recoverable full-document job.

    Candidate discovery is intentionally non-locking. ``_claim_job`` locks the
    selected Job first and the conditional UPDATE remains the compare-and-swap
    arbiter when workers discover the same row.
    """
    claim_time = now or utc_now()
    lease_seconds = lease_seconds or settings.GENERATION_JOB_LEASE_SECONDS
    candidate_result = await db.execute(
        select(AIGenerationJob.id)
        .where(
            AIGenerationJob.job_type == "full_document",
            _claimable_predicate(claim_time),
        )
        .order_by(
            # Resume stale paid work before beginning a new queued document.
            case((AIGenerationJob.status == "running", 0), else_=1),
            AIGenerationJob.available_at.asc(),
            AIGenerationJob.started_at.asc(),
            AIGenerationJob.id.asc(),
        )
        .limit(1)
    )
    candidate_id = candidate_result.scalar_one_or_none()
    if candidate_id is None:
        await db.rollback()
        return None
    return await _claim_job(
        db,
        job_id=int(candidate_id),
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        now=now,
    )


async def claim_generation_job_by_id(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_seconds: int | None = None,
    now: datetime | None = None,
) -> ClaimedGenerationJob | None:
    """Lease a specific job for backwards-compatible direct task delivery."""
    return await _claim_job(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds or settings.GENERATION_JOB_LEASE_SECONDS,
        now=now,
    )


async def generation_lease_is_owned(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    now: datetime | None = None,
) -> bool:
    check_time = now or utc_now()
    result = await db.execute(
        select(AIGenerationJob.id).where(
            AIGenerationJob.id == job_id,
            AIGenerationJob.status == "running",
            AIGenerationJob.lease_owner == worker_id,
            AIGenerationJob.lease_token == lease_token,
            AIGenerationJob.lease_expires_at.is_not(None),
            AIGenerationJob.lease_expires_at > check_time,
        )
    )
    return result.scalar_one_or_none() is not None


async def _lock_generation_lease(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    document_id: int | None = None,
    lock_case: bool = False,
    now: datetime | None = None,
) -> AIGenerationJob | None:
    """Lock Job -> Document -> optional Case and validate the fencing lease."""
    predicates = [
        AIGenerationJob.id == job_id,
        AIGenerationJob.status == "running",
        AIGenerationJob.lease_owner == worker_id,
        AIGenerationJob.lease_token == lease_token,
    ]
    if document_id is not None:
        predicates.append(AIGenerationJob.document_id == document_id)
    result = await db.execute(
        select(AIGenerationJob)
        .where(*predicates)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    check_time = now or utc_now()
    expiry = job.lease_expires_at if job is not None else None
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if job is None or expiry is None or expiry <= check_time:
        return None

    resolved_document_id = job.document_id
    if resolved_document_id is not None:
        locked_document = (
            await db.execute(
                select(Document.id)
                .where(Document.id == int(resolved_document_id))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if locked_document is None:
            return None
        if lock_case:
            await db.execute(
                select(ProductionCase.id)
                .where(ProductionCase.document_id == int(resolved_document_id))
                .with_for_update()
            )
    return job


def _lease_lost(job_id: int) -> GenerationLeaseLostError:
    return GenerationLeaseLostError(
        f"Generation lease for job {job_id} is expired or owned by another attempt"
    )


async def lock_generation_lease_for_mutation(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    document_id: int,
    lock_case: bool = False,
) -> None:
    """Acquire the generation locks in the caller's current transaction."""
    lease = await _lock_generation_lease(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_token=lease_token,
        document_id=document_id,
        lock_case=lock_case,
    )
    if lease is None:
        await db.rollback()
        raise _lease_lost(job_id)


async def persist_generation_section(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    document_id: int,
    section_index: int,
    values: dict[str, Any],
    now: datetime | None = None,
) -> DocumentSection:
    """Upsert one section while holding the lease row lock until commit.

    Claim/recovery updates the same job row, so another worker cannot take the
    job between the ownership check and this section write.
    """
    lease = await _lock_generation_lease(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_token=lease_token,
        document_id=document_id,
        now=now,
    )
    if lease is None:
        await db.rollback()
        raise _lease_lost(job_id)

    result = await db.execute(
        select(DocumentSection)
        .where(
            DocumentSection.document_id == document_id,
            DocumentSection.section_index == section_index,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    section = result.scalar_one_or_none()
    if section is None:
        section = DocumentSection(
            document_id=document_id,
            section_index=section_index,
            title=str(values.get("title") or f"Section {section_index}"),
        )
        db.add(section)

    allowed = {
        "title",
        "content",
        "status",
        "word_count",
        "grammar_score",
        "plagiarism_score",
        "ai_detection_score",
        "quality_score",
        "tokens_used",
        "completed_at",
        "bibliography",
        "pack_keys_used",
        "quality_panel",
    }
    for key, value in values.items():
        if key in allowed:
            setattr(section, key, value)
    await db.flush()
    await db.commit()
    return section


async def update_generation_section_status(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    document_id: int,
    section_index: int,
    status: str,
    now: datetime | None = None,
) -> None:
    """Change a section state under the same lease lock as the write."""
    lease = await _lock_generation_lease(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_token=lease_token,
        document_id=document_id,
        now=now,
    )
    if lease is None:
        await db.rollback()
        raise _lease_lost(job_id)
    await db.execute(
        update(DocumentSection)
        .where(
            DocumentSection.document_id == document_id,
            DocumentSection.section_index == section_index,
        )
        .values(status=status)
    )
    await db.commit()


async def update_generation_document(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    document_id: int,
    values: dict[str, Any],
    now: datetime | None = None,
) -> None:
    """Persist generation-owned document fields in the lease transaction."""
    failing = values.get("status") == "failed"
    lease = await _lock_generation_lease(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_token=lease_token,
        document_id=document_id,
        lock_case=failing,
        now=now,
    )
    if lease is None:
        await db.rollback()
        raise _lease_lost(job_id)
    allowed = {"content", "status", "completed_at"}
    safe_values = {key: value for key, value in values.items() if key in allowed}
    if not safe_values:
        await db.rollback()
        raise ValueError("No permitted generation document fields supplied")
    await db.execute(
        update(Document).where(Document.id == document_id).values(**safe_values)
    )
    if failing:
        await _revoke_failed_generation_release(db, document_id=document_id)
    await db.commit()


async def persist_generation_artifact(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    document_id: int,
    artifact_format: Literal["docx", "pdf"],
    storage_path: str,
    artifact_sha256: str,
    now: datetime | None = None,
) -> str | None:
    """Atomically bind uploaded bytes to the document under the current lease.

    Returns the replaced object path so the caller can remove it after the DB
    pointer safely references the new object.
    """
    lease = await _lock_generation_lease(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_token=lease_token,
        document_id=document_id,
        now=now,
    )
    if lease is None:
        await db.rollback()
        raise _lease_lost(job_id)
    document = (
        await db.execute(
            select(Document)
            .where(Document.id == document_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    path_field = f"{artifact_format}_path"
    hash_field = f"{artifact_format}_sha256"
    previous_path = getattr(document, path_field)
    setattr(document, path_field, storage_path)
    setattr(document, hash_field, artifact_sha256)
    await db.commit()
    return str(previous_path) if previous_path else None


@asynccontextmanager
async def hold_generation_job_lease(
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    document_id: int,
    lease_seconds: int | None = None,
) -> AsyncIterator[None]:
    """Hold only the Job row across a helper that performs several commits.

    Citation/claim stages mutate evidence rows over multiple transactions. They
    do not acquire a Document row lock in the normal path, so a Job-only guard
    prevents takeover between their commits without the export self-deadlock.
    """
    async with database.AsyncSessionLocal() as lock_db:
        job = (
            await lock_db.execute(
                select(AIGenerationJob)
                .where(
                    AIGenerationJob.id == job_id,
                    AIGenerationJob.document_id == document_id,
                    AIGenerationJob.status == "running",
                    AIGenerationJob.lease_owner == worker_id,
                    AIGenerationJob.lease_token == lease_token,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        acquired_at = utc_now()
        expiry = job.lease_expires_at if job is not None else None
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if job is None or expiry is None or expiry <= acquired_at:
            await lock_db.rollback()
            raise _lease_lost(job_id)
        try:
            yield
        except BaseException:
            await lock_db.rollback()
            raise
        else:
            renewed_at = utc_now()
            job.heartbeat_at = renewed_at
            job.lease_expires_at = renewed_at + timedelta(
                seconds=lease_seconds or settings.GENERATION_JOB_LEASE_SECONDS
            )
            await lock_db.commit()


async def renew_generation_lease(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    lease_seconds: int | None = None,
    now: datetime | None = None,
) -> bool:
    """Extend a lease only if the caller is still the recorded owner."""
    # Take the row lock before reading the clock. A heartbeat can wait behind a
    # fenced multi-write stage; using a timestamp captured before that wait can
    # shorten the lease into the past when it finally resumes.
    job = (
        await db.execute(
            select(AIGenerationJob)
            .where(
                AIGenerationJob.id == job_id,
                AIGenerationJob.status == "running",
                AIGenerationJob.lease_owner == worker_id,
                AIGenerationJob.lease_token == lease_token,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    heartbeat_at = now or utc_now()
    current_expiry = job.lease_expires_at if job is not None else None
    if current_expiry is not None and current_expiry.tzinfo is None:
        current_expiry = current_expiry.replace(tzinfo=UTC)
    if job is None or current_expiry is None or current_expiry <= heartbeat_at:
        await db.rollback()
        return False
    job.heartbeat_at = heartbeat_at
    job.lease_expires_at = heartbeat_at + timedelta(
        seconds=lease_seconds or settings.GENERATION_JOB_LEASE_SECONDS
    )
    await db.commit()
    return True


async def complete_generation_job(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    now: datetime | None = None,
) -> bool:
    """Atomically mark both the job and its document successful."""
    job = await _lock_generation_lease(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_token=lease_token,
        now=now,
    )
    if job is None:
        await db.rollback()
        return False
    completed_at = now or utc_now()

    job.status = "completed"
    job.progress = 100
    job.success = True
    job.error_message = None
    job.completed_at = completed_at
    job.heartbeat_at = completed_at
    job.lease_owner = None
    job.lease_token = None
    job.lease_expires_at = None
    if job.document_id is not None:
        await db.execute(
            update(Document)
            .where(Document.id == job.document_id)
            .values(status="completed", completed_at=completed_at)
        )
    await db.commit()
    return True


async def release_generation_lease_for_shutdown(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    now: datetime | None = None,
) -> bool:
    """Immediately requeue a gracefully cancelled attempt without consuming it."""
    released_at = now or utc_now()
    result = await db.execute(
        update(AIGenerationJob)
        .where(
            AIGenerationJob.id == job_id,
            AIGenerationJob.status == "running",
            AIGenerationJob.lease_owner == worker_id,
            AIGenerationJob.lease_token == lease_token,
        )
        .values(
            status="queued",
            available_at=released_at,
            heartbeat_at=released_at,
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
            # A controlled deploy/restart is not a failed execution attempt.
            attempt_count=case(
                (AIGenerationJob.attempt_count > 0, AIGenerationJob.attempt_count - 1),
                else_=0,
            ),
        )
        .returning(AIGenerationJob.id)
    )
    released = result.scalar_one_or_none() is not None
    await db.commit()
    return released


async def enqueue_artifact_deletions(
    db: AsyncSession, paths: list[str], *, reason: str = "superseded"
) -> int:
    """Persist deletion intents in the CALLER's transaction (no commit here).

    Best-effort post-commit cleanup used to be the only deletion attempt: a
    storage failure was logged and the blob stayed forever (audit
    2026-07-10). Enqueued rows survive the crash of whoever tried first and
    are retried by the worker sweep. Duplicates are ignored so re-invalidating
    the same artifact is idempotent.
    """
    unique = list(dict.fromkeys(str(p) for p in paths if p))
    if not unique:
        return 0
    existing = set(
        (
            await db.execute(
                select(ArtifactDeletionOutbox.file_path).where(
                    ArtifactDeletionOutbox.file_path.in_(unique)
                )
            )
        ).scalars()
    )
    added = 0
    for path in unique:
        if path in existing:
            continue
        try:
            async with db.begin_nested():
                db.add(ArtifactDeletionOutbox(file_path=path, reason=reason))
                await db.flush()
            added += 1
        except IntegrityError:
            # A concurrent enqueue won the unique constraint — same outcome.
            continue
    return added


async def clear_artifact_deletion_entries(db: AsyncSession, paths: list[str]) -> None:
    """Drop outbox rows whose blobs were confirmed deleted elsewhere."""
    unique = [str(p) for p in dict.fromkeys(paths) if p]
    if not unique:
        return
    await db.execute(
        delete(ArtifactDeletionOutbox).where(
            ArtifactDeletionOutbox.file_path.in_(unique)
        )
    )
    await db.commit()


async def process_artifact_deletion_outbox(
    db: AsyncSession,
    *,
    storage: StorageService | None = None,
    now: datetime | None = None,
    limit: int = 10,
) -> tuple[int, int]:
    """Retry due storage deletions; returns (processed, confirmed_deleted).

    Failure backs the row off exponentially (60s .. 6h) instead of dropping
    it; success removes the row. Deleting an already-absent object counts as
    success (S3 semantics), so rows for blobs cleaned by the immediate
    post-commit attempt drain on the first sweep.
    """
    sweep_time = now or utc_now()
    rows = (
        (
            await db.execute(
                select(ArtifactDeletionOutbox)
                .where(ArtifactDeletionOutbox.next_attempt_at <= sweep_time)
                .order_by(
                    ArtifactDeletionOutbox.next_attempt_at.asc(),
                    ArtifactDeletionOutbox.id.asc(),
                )
                .limit(limit)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        await db.rollback()
        return (0, 0)

    if storage is None:
        from app.services.storage_service import StorageService

        storage = StorageService()

    confirmed = 0
    for row in rows:
        error: str | None = None
        try:
            deleted = await storage.delete_file(str(row.file_path))
        except Exception as exc:
            deleted = False
            error = str(exc)
        if deleted:
            await db.delete(row)
            confirmed += 1
        else:
            row.attempts = int(row.attempts or 0) + 1
            backoff = min(21600, 60 * (2 ** max(0, row.attempts - 1)))
            row.next_attempt_at = sweep_time + timedelta(seconds=backoff)
            row.last_error = (error or "storage did not confirm deletion")[:500]
    await db.commit()
    return (len(rows), confirmed)


async def write_generation_usage_monotonic(
    db: AsyncSession, *, job_id: int, total_tokens: int, cost_cents: int
) -> bool:
    """Unfenced, upward-only usage write for cancel/shutdown unwinding.

    After a cancel or lease loss the job row is no longer
    running-with-our-token, so the fenced usage write matches zero rows and
    the in-flight section's spend vanishes from accounting (audit
    2026-07-10). Spend is append-only truth, not content: key the write by
    job id alone, but only ever move totals UPWARD so a replacement owner's
    larger numbers are never clobbered. Returns True when the row advanced.
    """
    result = await db.execute(
        update(AIGenerationJob)
        .where(
            AIGenerationJob.id == job_id,
            func.coalesce(AIGenerationJob.total_tokens, 0) < int(total_tokens),
        )
        .values(total_tokens=int(total_tokens), cost_cents=int(cost_cents))
        .returning(AIGenerationJob.id)
    )
    advanced = result.scalar_one_or_none() is not None
    await db.commit()
    return advanced


async def cancel_active_generation_job(
    db: AsyncSession,
    *,
    document_id: int,
    cancelled_by: str,
    now: datetime | None = None,
) -> int | None:
    """Terminally cancel the active full-document job for a document.

    Clearing the lease token fences the running executor out of every
    subsequent write (sections, sources, evidence, artifacts, completion),
    and `cancelled` is outside the claimable predicate, so neither the
    poll loop nor the retry path can resurrect the job. Same cross-path
    lock order as everywhere: Job -> Document -> ProductionCase.
    """
    job_id = (
        await db.execute(
            select(AIGenerationJob.id)
            .where(
                AIGenerationJob.document_id == document_id,
                AIGenerationJob.job_type == "full_document",
                AIGenerationJob.status.in_(("queued", "running")),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if job_id is None:
        await db.rollback()
        return None

    cancel_time = now or utc_now()
    cancelled_id = (
        await db.execute(
            update(AIGenerationJob)
            .where(
                AIGenerationJob.id == job_id,
                AIGenerationJob.status.in_(("queued", "running")),
            )
            .values(
                status="cancelled",
                success=False,
                error_message=f"Cancelled by {cancelled_by}"[:500],
                completed_at=cancel_time,
                heartbeat_at=cancel_time,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
            )
            .returning(AIGenerationJob.id)
        )
    ).scalar_one_or_none()
    if cancelled_id is None:
        await db.rollback()
        return None

    await db.execute(
        select(Document.id).where(Document.id == document_id).with_for_update()
    )
    await db.execute(
        select(ProductionCase.id)
        .where(ProductionCase.document_id == document_id)
        .with_for_update()
    )
    # A cancelled run is a failed run for delivery purposes: the document
    # becomes retryable and no releasable snapshot may survive it.
    await db.execute(
        update(Document)
        .where(Document.id == document_id, Document.status != "failed_quality")
        .values(status="failed")
    )
    await _revoke_failed_generation_release(db, document_id=document_id)
    await db.commit()
    logger.info(
        "Cancelled generation job %s for document %s (%s)",
        cancelled_id,
        document_id,
        cancelled_by,
    )
    return int(cancelled_id)


async def reschedule_or_fail_generation_job(
    db: AsyncSession,
    *,
    job_id: int,
    worker_id: str,
    lease_token: str,
    error: Exception,
    terminal: bool,
    now: datetime | None = None,
) -> RetryDecision:
    """Persist bounded retry state without ever overwriting a new owner."""
    job = await _lock_generation_lease(
        db,
        job_id=job_id,
        worker_id=worker_id,
        lease_token=lease_token,
        lock_case=True,
        now=now,
    )
    if job is None:
        await db.rollback()
        return "lost"
    failure_time = now or utc_now()

    attempts = int(job.attempt_count or 0)
    max_attempts = int(job.max_attempts or settings.GENERATION_JOB_MAX_ATTEMPTS)
    error_message = str(error)[:500]
    should_fail = terminal or attempts >= max_attempts

    if should_fail:
        job.status = "failed"
        job.success = False
        job.error_message = error_message
        job.completed_at = failure_time
        job.heartbeat_at = failure_time
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        await db.execute(
            update(Document)
            .where(
                Document.id == job.document_id,
                Document.status != "failed_quality",
            )
            .values(status="failed")
        )
        if job.document_id is not None:
            await _revoke_failed_generation_release(
                db, document_id=int(job.document_id)
            )
        decision: RetryDecision = "failed"
    else:
        base = max(1, settings.GENERATION_JOB_RETRY_BASE_SECONDS)
        max_delay = max(base, settings.GENERATION_JOB_RETRY_MAX_SECONDS)
        delay = min(max_delay, base * (2 ** max(0, attempts - 1)))
        job.status = "queued"
        job.error_message = error_message
        job.completed_at = None
        job.available_at = failure_time + timedelta(seconds=delay)
        job.heartbeat_at = failure_time
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        await db.execute(
            update(Document)
            .where(Document.id == job.document_id)
            .values(status="generating")
        )
        decision = "retry"

    await db.commit()
    return decision


async def fail_exhausted_generation_jobs(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 25
) -> int:
    """Fail jobs that crashed on their final allowed lease attempt."""
    discovery_time = now or utc_now()
    expired_running = and_(
        AIGenerationJob.status == "running",
        or_(
            AIGenerationJob.lease_expires_at.is_(None),
            AIGenerationJob.lease_expires_at <= discovery_time,
        ),
    )
    exhausted_queued = AIGenerationJob.status == "queued"
    candidates = (
        await db.execute(
            select(AIGenerationJob.id, AIGenerationJob.document_id)
            .where(
                AIGenerationJob.job_type == "full_document",
                or_(expired_running, exhausted_queued),
                func.coalesce(AIGenerationJob.attempt_count, 0)
                >= func.coalesce(
                    AIGenerationJob.max_attempts,
                    settings.GENERATION_JOB_MAX_ATTEMPTS,
                ),
            )
            .order_by(AIGenerationJob.started_at.asc(), AIGenerationJob.id.asc())
            .limit(limit)
        )
    ).all()
    failed = 0
    for candidate_id, _document_id in candidates:
        failure_time = now or utc_now()
        job = (
            await db.execute(
                select(AIGenerationJob)
                .where(
                    AIGenerationJob.id == candidate_id,
                    AIGenerationJob.job_type == "full_document",
                    or_(
                        and_(
                            AIGenerationJob.status == "running",
                            or_(
                                AIGenerationJob.lease_expires_at.is_(None),
                                AIGenerationJob.lease_expires_at <= failure_time,
                            ),
                        ),
                        AIGenerationJob.status == "queued",
                    ),
                    func.coalesce(AIGenerationJob.attempt_count, 0)
                    >= func.coalesce(
                        AIGenerationJob.max_attempts,
                        settings.GENERATION_JOB_MAX_ATTEMPTS,
                    ),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if job is None:
            await db.rollback()
            continue
        if job.document_id is not None:
            await db.execute(
                select(Document.id)
                .where(Document.id == job.document_id)
                .with_for_update()
            )
            await db.execute(
                select(ProductionCase.id)
                .where(ProductionCase.document_id == job.document_id)
                .with_for_update()
            )
        job.status = "failed"
        job.success = False
        job.error_message = (
            job.error_message or "Generation worker stopped before completion"
        )[:500]
        job.completed_at = failure_time
        job.heartbeat_at = failure_time
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        if job.document_id is not None:
            await db.execute(
                update(Document)
                .where(
                    Document.id == job.document_id,
                    Document.status != "failed_quality",
                )
                .values(status="failed")
            )
            await _revoke_failed_generation_release(
                db, document_id=int(job.document_id)
            )
        await db.commit()
        failed += 1
    return failed


async def quarantine_invalid_generation_jobs(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 100
) -> int:
    """Fail active rows that cannot satisfy the worker execution contract."""
    candidates = (
        await db.execute(
            select(AIGenerationJob.id, AIGenerationJob.document_id)
            .where(
                AIGenerationJob.job_type == "full_document",
                AIGenerationJob.status.in_(["queued", "running"]),
            )
            .order_by(AIGenerationJob.id.asc())
            .limit(limit)
        )
    ).all()
    quarantined = 0
    for candidate_id, _document_id in candidates:
        job = (
            await db.execute(
                select(AIGenerationJob)
                .where(
                    AIGenerationJob.id == candidate_id,
                    AIGenerationJob.job_type == "full_document",
                    AIGenerationJob.status.in_(["queued", "running"]),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if job is None:
            await db.rollback()
            continue
        document = None
        production_case = None
        if job.document_id is not None:
            document = (
                await db.execute(
                    select(Document)
                    .where(Document.id == job.document_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            production_case = (
                await db.execute(
                    select(ProductionCase)
                    .where(ProductionCase.document_id == job.document_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
        contract_error = _generation_contract_error(
            document=document,
            production_case=production_case,
            job_user_id=job.user_id,
            request_payload=job.request_payload,
            require_running_token=job.status == "running",
            lease_owner=job.lease_owner,
            lease_token=job.lease_token,
            lease_expires_at=job.lease_expires_at,
        )
        if contract_error is None:
            await db.rollback()
            continue
        quarantined_at = now or utc_now()
        job.status = "failed"
        job.success = False
        job.error_message = f"Quarantined generation job: {contract_error}"[:500]
        job.completed_at = quarantined_at
        job.heartbeat_at = quarantined_at
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        if document is not None and document.status != "failed_quality":
            document.status = "failed"
            await _revoke_failed_generation_release(db, document_id=int(document.id))
        quarantined += 1
        logger.error("Quarantined generation job %s: %s", job.id, contract_error)
        await db.commit()
    return quarantined


class GenerationWorker:
    """One polling worker instance per API process."""

    def __init__(self, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
        )
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        async with database.AsyncSessionLocal() as db:
            quarantined = await quarantine_invalid_generation_jobs(db)
        if quarantined:
            logger.error(
                "Generation worker quarantined %s unsafe active job(s)", quarantined
            )
        self._task = asyncio.create_task(
            self.run(), name=f"generation-worker:{self.worker_id}"
        )
        logger.info("Generation worker started: %s", self.worker_id)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
        logger.info("Generation worker stopped: %s", self.worker_id)

    async def run(self) -> None:
        poll_seconds = max(0.05, settings.GENERATION_WORKER_POLL_SECONDS)
        while True:
            try:
                worked = await self.poll_once()
                if not worked:
                    await asyncio.sleep(poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Generation worker polling iteration failed")
                await asyncio.sleep(poll_seconds)

    async def poll_once(self) -> bool:
        async with database.AsyncSessionLocal() as db:
            exhausted = await fail_exhausted_generation_jobs(db)
        if exhausted:
            logger.error("Failed %s exhausted generation job(s)", exhausted)

        # Storage-deletion retry sweep: cheap when the outbox is empty, and a
        # sweep failure must never stall generation work.
        try:
            async with database.AsyncSessionLocal() as db:
                processed, confirmed = await process_artifact_deletion_outbox(db)
            if processed:
                logger.info(
                    "Deletion outbox sweep: %s processed, %s confirmed",
                    processed,
                    confirmed,
                )
        except Exception:
            logger.exception("Artifact deletion outbox sweep failed")

        async with database.AsyncSessionLocal() as db:
            claimed = await claim_next_generation_job(
                db,
                worker_id=self.worker_id,
                lease_seconds=settings.GENERATION_JOB_LEASE_SECONDS,
            )
        if claimed is None:
            return False

        logger.info(
            "Worker %s claimed generation job %s (attempt %s/%s)",
            self.worker_id,
            claimed.id,
            claimed.attempt_count,
            claimed.max_attempts,
        )
        # Lazy import avoids a module cycle: background_jobs uses the lease
        # helpers above, while this worker invokes the actual pipeline.
        from app.services.background_jobs import BackgroundJobService

        await BackgroundJobService.generate_full_document_async(
            document_id=claimed.document_id,
            user_id=claimed.user_id,
            job_id=claimed.id,
            additional_requirements=claimed.additional_requirements,
            lease_owner=claimed.lease_owner,
            lease_token=claimed.lease_token,
        )
        return True
