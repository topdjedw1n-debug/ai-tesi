"""Durable generation worker: lease, recovery, retry, and shutdown coverage."""

import asyncio
import inspect
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentOutline,
    DocumentProvenance,
    DocumentSection,
    DocumentSource,
    ProductionCase,
)
from app.services import generation_worker as generation_worker_module
from app.services.background_jobs import (
    BackgroundJobService,
    _export_document_with_fence,
)
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_worker import (
    GenerationLeaseLostError,
    GenerationWorker,
    claim_next_generation_job,
    complete_generation_job,
    lock_generation_lease_for_mutation,
    persist_generation_section,
    release_generation_lease_for_shutdown,
    reschedule_or_fail_generation_job,
    update_generation_document,
    utc_now,
)


async def _seed_job(
    db_session,
    *,
    email: str,
    status: str = "queued",
    attempt_count: int = 0,
    max_attempts: int = 3,
    lease_owner: str | None = None,
    lease_expires_at=None,
) -> tuple[Document, AIGenerationJob]:
    user = User(email=email, full_name="Worker Test", is_active=True)
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Durable generation",
        topic="Crash recovery for long-running academic generation",
        status="generating",
        additional_requirements="Extracted UNIBO methodology text",
        requirements_file_processed=True,
        citation_style="apa",
    )
    db_session.add(document)
    await db_session.flush()
    run_requirements = "Use the persisted methodic"
    job = AIGenerationJob(
        user_id=user.id,
        document_id=document.id,
        job_type="full_document",
        status=status,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        request_payload={
            "additional_requirements": run_requirements,
            "generation_contract_sha256": generation_contract_sha256(
                document, None, run_requirements
            ),
        },
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return document, job


def test_worker_lock_order_is_job_then_document_then_case():
    claim_source = inspect.getsource(generation_worker_module._claim_job)
    mutation_source = inspect.getsource(generation_worker_module._lock_generation_lease)

    assert (
        claim_source.index("select(AIGenerationJob.id)")
        < claim_source.index("select(Document)")
        < claim_source.index("select(ProductionCase)")
    )
    assert (
        mutation_source.index("select(AIGenerationJob)")
        < mutation_source.index("select(Document.id)")
        < mutation_source.index("select(ProductionCase.id)")
    )


@pytest.mark.asyncio
async def test_only_one_worker_can_lease_a_queued_job(db_session):
    _, job = await _seed_job(db_session, email="worker-single-owner@example.com")
    job_id = int(job.id)
    now = utc_now()

    first = await claim_next_generation_job(
        db_session, worker_id="worker-a", lease_seconds=120, now=now
    )
    second = await claim_next_generation_job(
        db_session, worker_id="worker-b", lease_seconds=120, now=now
    )

    assert first is not None
    assert first.id == job_id
    assert first.lease_owner == "worker-a"
    assert first.attempt_count == 1
    assert first.additional_requirements == "Use the persisted methodic"
    assert second is None


@pytest.mark.asyncio
async def test_expired_running_lease_is_recovered_by_new_worker(db_session):
    now = utc_now()
    _, job = await _seed_job(
        db_session,
        email="worker-recovery@example.com",
        status="running",
        attempt_count=1,
        lease_owner="dead-worker",
        lease_expires_at=now - timedelta(seconds=1),
    )

    recovered = await claim_next_generation_job(
        db_session, worker_id="replacement-worker", lease_seconds=120, now=now
    )

    assert recovered is not None
    assert recovered.id == job.id
    assert recovered.lease_owner == "replacement-worker"
    assert recovered.attempt_count == 2


@pytest.mark.asyncio
async def test_graceful_shutdown_requeues_without_consuming_attempt(db_session):
    _, job = await _seed_job(db_session, email="worker-shutdown@example.com")
    claimed = await claim_next_generation_job(
        db_session, worker_id="worker-a", now=utc_now()
    )
    assert claimed is not None

    released = await release_generation_lease_for_shutdown(
        db_session,
        job_id=job.id,
        worker_id="worker-a",
        lease_token=claimed.lease_token,
        now=utc_now(),
    )
    await db_session.refresh(job)

    assert released is True
    assert job.status == "queued"
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.attempt_count == 0


@pytest.mark.asyncio
async def test_retry_is_bounded_and_final_attempt_fails_document(db_session):
    document, job = await _seed_job(
        db_session,
        email="worker-bounded-retry@example.com",
        max_attempts=2,
    )
    start = utc_now()
    first = await claim_next_generation_job(db_session, worker_id="worker-a", now=start)
    assert first is not None

    decision = await reschedule_or_fail_generation_job(
        db_session,
        job_id=job.id,
        worker_id="worker-a",
        lease_token=first.lease_token,
        error=RuntimeError("temporary provider outage"),
        terminal=False,
        now=start,
    )
    assert decision == "retry"
    await db_session.refresh(document)
    assert document.status == "generating"

    second = await claim_next_generation_job(
        db_session,
        worker_id="worker-b",
        now=start + timedelta(minutes=10),
    )
    assert second is not None
    assert second.attempt_count == 2
    decision = await reschedule_or_fail_generation_job(
        db_session,
        job_id=job.id,
        worker_id="worker-b",
        lease_token=second.lease_token,
        error=RuntimeError("provider still unavailable"),
        terminal=False,
        now=start + timedelta(minutes=10),
    )

    await db_session.refresh(job)
    await db_session.refresh(document)
    assert decision == "failed"
    assert job.status == "failed"
    assert job.success is False
    assert document.status == "failed"


@pytest.mark.asyncio
async def test_polling_workers_do_not_double_deliver_claim(monkeypatch, db_session):
    _, job = await _seed_job(db_session, email="worker-poller@example.com")
    execute = AsyncMock(return_value=None)
    monkeypatch.setattr(BackgroundJobService, "generate_full_document_async", execute)

    first = GenerationWorker(worker_id="poller-a")
    second = GenerationWorker(worker_id="poller-b")
    assert await first.poll_once() is True
    assert await second.poll_once() is False

    execute.assert_awaited_once()
    assert execute.await_args.kwargs["job_id"] == job.id
    assert execute.await_args.kwargs["lease_owner"] == "poller-a"
    assert execute.await_args.kwargs["lease_token"]
    assert (
        execute.await_args.kwargs["additional_requirements"]
        == "Use the persisted methodic"
    )


@pytest.mark.asyncio
async def test_cancelling_running_wrapper_requeues_and_keeps_checkpoint(
    monkeypatch, db_session
):
    _, job = await _seed_job(db_session, email="worker-cancel@example.com")
    pipeline_started = asyncio.Event()

    async def never_finishes(**_kwargs):
        pipeline_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        BackgroundJobService,
        "generate_full_document",
        AsyncMock(side_effect=never_finishes),
    )
    monkeypatch.setattr(
        "app.services.background_jobs.manager.send_progress", AsyncMock()
    )
    checkpoint_clear = AsyncMock()
    monkeypatch.setattr(
        "app.services.background_jobs._clear_generation_checkpoint",
        checkpoint_clear,
    )

    task = asyncio.create_task(
        BackgroundJobService.generate_full_document_async(
            document_id=job.document_id,
            user_id=job.user_id,
            job_id=job.id,
        )
    )
    await asyncio.wait_for(pipeline_started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    refreshed = (
        await db_session.execute(
            select(AIGenerationJob).where(AIGenerationJob.id == job.id)
        )
    ).scalar_one()
    assert refreshed.status == "queued"
    assert refreshed.lease_owner is None
    assert refreshed.attempt_count == 0
    checkpoint_clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_attempt_cannot_mutate_generation_or_leave_artifact(
    monkeypatch, db_session
):
    document, job = await _seed_job(
        db_session, email="worker-fencing-token@example.com"
    )
    document_id = int(document.id)
    job_id = int(job.id)
    user_id = int(job.user_id)
    start = utc_now()
    first = await claim_next_generation_job(
        db_session,
        worker_id="worker-a",
        lease_seconds=5,
        now=start,
    )
    assert first is not None

    section = await persist_generation_section(
        db_session,
        job_id=job_id,
        worker_id="worker-a",
        lease_token=first.lease_token,
        document_id=document_id,
        section_index=1,
        values={
            "title": "Introduzione",
            "content": "Accepted content from the first owned attempt.",
            "status": "completed",
        },
        now=start + timedelta(seconds=1),
    )
    assert section.content == "Accepted content from the first owned attempt."

    replacement = await claim_next_generation_job(
        db_session,
        worker_id="worker-b",
        lease_seconds=120,
        now=start + timedelta(seconds=6),
    )
    assert replacement is not None
    assert replacement.lease_token != first.lease_token

    with pytest.raises(GenerationLeaseLostError):
        await persist_generation_section(
            db_session,
            job_id=job_id,
            worker_id="worker-a",
            lease_token=first.lease_token,
            document_id=document_id,
            section_index=1,
            values={"content": "STALE SECTION", "status": "completed"},
        )
    with pytest.raises(GenerationLeaseLostError):
        await update_generation_document(
            db_session,
            job_id=job_id,
            worker_id="worker-a",
            lease_token=first.lease_token,
            document_id=document_id,
            values={"content": "STALE DOCUMENT", "status": "completed"},
        )
    assert (
        await complete_generation_job(
            db_session,
            job_id=job_id,
            worker_id="worker-a",
            lease_token=first.lease_token,
        )
        is False
    )

    evidence_callback_reached = False

    async def stale_evidence_write() -> None:
        nonlocal evidence_callback_reached
        await lock_generation_lease_for_mutation(
            db_session,
            job_id=job_id,
            worker_id="worker-a",
            lease_token=first.lease_token,
            document_id=document_id,
        )
        evidence_callback_reached = True
        db_session.add_all(
            [
                DocumentOutline(
                    document_id=document_id,
                    outline_data={"sections": []},
                    total_sections=0,
                ),
                DocumentSource(document_id=document_id, title="Stale source"),
                DocumentProvenance(
                    document_id=document_id,
                    stage="generation",
                    event_type="stale_event",
                ),
            ]
        )
        await db_session.commit()

    with pytest.raises(GenerationLeaseLostError):
        await stale_evidence_write()
    assert evidence_callback_reached is False

    document_service = AsyncMock()
    document_service.export_document.return_value = {
        "storage_path": "s3://documents/stale-attempt.docx",
        "artifact_sha256": "a" * 64,
        "format": "docx",
    }
    storage = AsyncMock()
    storage.delete_file.return_value = True
    monkeypatch.setattr("app.services.background_jobs.StorageService", lambda: storage)
    with pytest.raises(GenerationLeaseLostError):
        await _export_document_with_fence(
            db_session,
            document_service=document_service,
            document_id=document_id,
            user_id=user_id,
            job_id=job_id,
            lease_owner="worker-a",
            lease_token=first.lease_token,
        )
    storage.delete_file.assert_awaited_once_with("s3://documents/stale-attempt.docx")

    db_session.expire_all()
    persisted_document = await db_session.get(Document, document_id)
    persisted_section = (
        await db_session.execute(
            select(DocumentSection).where(
                DocumentSection.document_id == document_id,
                DocumentSection.section_index == 1,
            )
        )
    ).scalar_one()
    assert persisted_document.content is None
    assert persisted_document.docx_path is None
    assert persisted_section.content == "Accepted content from the first owned attempt."
    assert (
        await db_session.execute(
            select(DocumentOutline).where(DocumentOutline.document_id == document_id)
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(DocumentSource).where(DocumentSource.document_id == document_id)
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(DocumentProvenance).where(
                DocumentProvenance.document_id == document_id
            )
        )
    ).scalar_one_or_none() is None

    await update_generation_document(
        db_session,
        job_id=job_id,
        worker_id="worker-b",
        lease_token=replacement.lease_token,
        document_id=document_id,
        values={"content": "CURRENT DOCUMENT", "status": "sections_generated"},
    )
    assert await complete_generation_job(
        db_session,
        job_id=job_id,
        worker_id="worker-b",
        lease_token=replacement.lease_token,
    )
    db_session.expire_all()
    completed_document = await db_session.get(Document, document_id)
    assert completed_document.content == "CURRENT DOCUMENT"
    assert completed_document.status == "completed"


@pytest.mark.asyncio
async def test_worker_quarantines_invalid_contract_and_revokes_release(db_session):
    document, job = await _seed_job(
        db_session, email="worker-invalid-contract@example.com"
    )
    document_id = int(document.id)
    job_id = int(job.id)
    # vancouver is not renderable by the citation formatter -> the worker
    # must refuse the row at the trust boundary (universal contract, 2026-07-11)
    document.citation_style = "vancouver"
    production_case = ProductionCase(
        document_id=document_id,
        client_user_id=job.user_id,
        generation_status="completed",
        delivery_status="delivered",
        release_status="released",
        released_docx_path="s3://documents/released.docx",
        released_docx_sha256="b" * 64,
        release_version=3,
    )
    db_session.add(production_case)
    await db_session.commit()
    production_case_id = int(production_case.id)

    claimed = await claim_next_generation_job(
        db_session, worker_id="contract-validator", now=utc_now()
    )
    assert claimed is None

    db_session.expire_all()
    quarantined_job = await db_session.get(AIGenerationJob, job_id)
    quarantined_document = await db_session.get(Document, document_id)
    quarantined_case = await db_session.get(ProductionCase, production_case_id)
    assert quarantined_job.status == "failed"
    assert quarantined_job.lease_owner is None
    assert quarantined_job.lease_token is None
    assert "unsupported citation style" in quarantined_job.error_message
    assert quarantined_document.status == "failed"
    assert quarantined_case.generation_status == "failed"
    assert quarantined_case.delivery_status == "not_ready"
    assert quarantined_case.release_status == "blocked"
    assert quarantined_case.released_docx_path is None
    assert quarantined_case.released_docx_sha256 is None
    assert quarantined_case.release_version == 4
