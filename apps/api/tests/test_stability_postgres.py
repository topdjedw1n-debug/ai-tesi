"""Real PostgreSQL transactions for S2/T05/T10; skips are never acceptance."""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1.endpoints.generate import enqueue_full_document
from app.core.database import AsyncSessionLocal
from app.models.auth import User
from app.models.document import AIGenerationJob, DocumentProvenance
from app.schemas.document import AsyncGenerationRequest, GenerationResumeRequest
from app.services.generation_pause import PAUSE_KEY, lock_generation_pause
from app.services.generation_recovery import resume_generation, terminal_fingerprint
from app.services.generation_worker import (
    cancel_active_generation_job,
    claim_next_generation_job,
)
from app.services.settings_service import SettingsService
from tests import test_release_evidence_postgres as release_pg
from tests.test_stability_recovery import stopped_work

postgres = release_pg.postgres
pytestmark = pytest.mark.asyncio


async def seed(postgres):
    async with AsyncSessionLocal() as db:
        doc, job, owner = await stopped_work(db)
        return int(doc.id), int(job.id), int(owner.id), terminal_fingerprint(job)


async def resume(doc_id, owner_id, fingerprint, intent):
    async with AsyncSessionLocal() as db:
        owner = await db.get(User, owner_id)
        job = await resume_generation(
            db,
            doc_id,
            owner,
            GenerationResumeRequest(
                intent_id=intent, expected_fingerprint=fingerprint, confirm_paid=True
            ),
        )
        return int(job.id), job.status


async def test_two_resume_intents_get_one_grant_and_two_receipts(postgres):
    doc_id, job_id, owner_id, fingerprint = await seed(postgres)
    results = await asyncio.wait_for(
        asyncio.gather(
            resume(doc_id, owner_id, fingerprint, "concurrent-first"),
            resume(doc_id, owner_id, fingerprint, "concurrent-second"),
        ),
        timeout=10,
    )
    assert {r[0] for r in results} == {job_id}
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, job_id)
        assert (job.attempt_count, job.max_attempts, job.total_tokens) == (3, 6, 1000)
        events = list(
            (
                await db.execute(
                    select(DocumentProvenance).where(
                        DocumentProvenance.event_type == "generation_intent_receipt"
                    )
                )
            ).scalars()
        )
        assert len(events) == 2 and sum(e.payload["granted"] for e in events) == 1


async def test_resume_and_default_post_preserve_same_job(postgres):
    doc_id, job_id, owner_id, fingerprint = await seed(postgres)

    async def start():
        async with AsyncSessionLocal() as db:
            owner = await db.get(User, owner_id)
            try:
                return (
                    await enqueue_full_document(
                        AsyncGenerationRequest(
                            document_id=doc_id, intent_id="default-start"
                        ),
                        owner,
                        db,
                    )
                ).job_id
            except HTTPException as error:
                await db.rollback()
                assert error.status_code == 409
                return None

    results = await asyncio.wait_for(
        asyncio.gather(
            resume(doc_id, owner_id, fingerprint, "resume-with-post"), start()
        ),
        timeout=10,
    )
    assert results[0][0] == job_id and results[1] in {None, job_id}
    async with AsyncSessionLocal() as db:
        assert len(list((await db.execute(select(AIGenerationJob))).scalars())) == 1


async def test_two_workers_claim_only_one_owner(postgres):
    doc_id, job_id, owner_id, fingerprint = await seed(postgres)
    await resume(doc_id, owner_id, fingerprint, "before-workers")

    async def claim(name):
        async with AsyncSessionLocal() as db:
            return await claim_next_generation_job(db, worker_id=name)

    results = await asyncio.wait_for(
        asyncio.gather(claim("first-worker"), claim("second-worker")), timeout=10
    )
    assert sum(result is not None for result in results) == 1
    assert next(r.id for r in results if r is not None) == job_id


async def test_cancel_and_resume_serialize_without_losing_history(postgres):
    doc_id, job_id, owner_id, fingerprint = await seed(postgres)
    # Terminal resume followed by cancel is a lawful pair of historical actions.
    await resume(doc_id, owner_id, fingerprint, "before-cancel")
    async with AsyncSessionLocal() as db:
        await cancel_active_generation_job(
            db, document_id=doc_id, cancelled_by=f"user:{owner_id}"
        )
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, job_id)
        next_fingerprint = terminal_fingerprint(job)

    async def cancel():
        async with AsyncSessionLocal() as db:
            return await cancel_active_generation_job(
                db, document_id=doc_id, cancelled_by=f"user:{owner_id}"
            )

    await asyncio.wait_for(
        asyncio.gather(
            resume(doc_id, owner_id, next_fingerprint, "after-cancel"), cancel()
        ),
        timeout=10,
    )
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, job_id)
        assert job.status in {"queued", "cancelled"}
        assert job.total_tokens == 1000 and job.attempt_count == 3
        events = list((await db.execute(select(DocumentProvenance))).scalars())
        assert sum(e.event_type == "generation_resume" for e in events) == 2
        assert any(e.event_type == "generation_cancelled" for e in events)


async def test_pause_wins_before_waiting_resume(postgres):
    doc_id, job_id, owner_id, fingerprint = await seed(postgres)
    async with AsyncSessionLocal() as paused:
        await lock_generation_pause(paused)
        contender = asyncio.create_task(
            resume(doc_id, owner_id, fingerprint, "paused-resume")
        )
        try:
            await SettingsService(paused).update_setting(
                PAUSE_KEY, True, "generation", owner_id
            )
            assert not contender.done()
            await paused.commit()
            with pytest.raises(HTTPException) as error:
                await asyncio.wait_for(contender, timeout=10)
            assert error.value.status_code == 503
        finally:
            if not contender.done():
                contender.cancel()
                await asyncio.gather(contender, return_exceptions=True)
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, job_id)
        assert job.status == "failed" and job.max_attempts == 3


async def test_resume_and_admin_default_post_preserve_one_job(postgres):
    from starlette.requests import Request

    from app.api.v1.endpoints.admin_documents import retry_document_generation

    doc_id, job_id, owner_id, fingerprint = await seed(postgres)

    async def admin_start():
        async with AsyncSessionLocal() as db:
            owner = await db.get(User, owner_id)
            try:
                result = await retry_document_generation(
                    doc_id,
                    Request({"type": "http", "headers": []}),
                    owner,
                    db,
                    {"intent_id": "admin-join-intent"},
                )
                return result["job_id"]
            except HTTPException as error:
                assert error.status_code == 409
                return None

    results = await asyncio.wait_for(
        asyncio.gather(
            resume(doc_id, owner_id, fingerprint, "resume-admin-race"), admin_start()
        ),
        timeout=10,
    )
    assert results[0][0] == job_id and results[1] in {None, job_id}
    async with AsyncSessionLocal() as db:
        jobs = list((await db.execute(select(AIGenerationJob))).scalars())
        assert len(jobs) == 1 and jobs[0].max_attempts == 6


async def test_stale_worker_cannot_write_under_postgres(postgres, monkeypatch):
    from tests.test_generation_worker import (
        test_stale_attempt_cannot_mutate_generation_or_leave_artifact,
    )

    async with AsyncSessionLocal() as db:
        await test_stale_attempt_cannot_mutate_generation_or_leave_artifact(
            monkeypatch, db
        )


@pytest.mark.parametrize("path", ["manager", "admin", "operator"])
async def test_pause_blocks_every_shared_start_path(postgres, path):
    from starlette.requests import Request

    from app.api.v1.endpoints.admin_documents import retry_document_generation

    doc_id, job_id, owner_id, fingerprint = await seed(postgres)
    async with AsyncSessionLocal() as db:
        await SettingsService(db).update_setting(
            PAUSE_KEY, True, "generation", owner_id
        )
        await db.commit()
    async with AsyncSessionLocal() as db:
        owner = await db.get(User, owner_id)
        with pytest.raises(HTTPException) as error:
            if path == "admin":
                await retry_document_generation(
                    doc_id, Request({"type": "http", "headers": []}), owner, db
                )
            else:
                await enqueue_full_document(
                    AsyncGenerationRequest(document_id=doc_id), owner, db
                )
        assert error.value.status_code == 503
        await db.rollback()
        assert (await db.get(AIGenerationJob, job_id)).max_attempts == 3


async def test_committed_deletion_intent_blocks_waiting_resume(postgres):
    from datetime import UTC, datetime

    doc_id, job_id, owner_id, fingerprint = await seed(postgres)
    async with AsyncSessionLocal() as deleting:
        owner = (
            await deleting.execute(
                select(User).where(User.id == owner_id).with_for_update()
            )
        ).scalar_one()
        contender = asyncio.create_task(
            resume(doc_id, owner_id, fingerprint, "delete-race")
        )
        try:
            # Same durable phase-1 marker and lock used by GDPRService; the
            # resume must re-read the owner after waiting on that lock.
            owner.deletion_requested_at = datetime.now(UTC)
            await deleting.flush()
            assert not contender.done()
            await deleting.commit()
            with pytest.raises(HTTPException) as error:
                await asyncio.wait_for(contender, timeout=10)
            assert error.value.status_code in {403, 409}
        finally:
            if not contender.done():
                contender.cancel()
                await asyncio.gather(contender, return_exceptions=True)
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, job_id)
        assert job.status == "failed" and job.max_attempts == 3
        assert job.total_tokens == 1000
        receipts = list(
            (
                await db.execute(
                    select(DocumentProvenance).where(
                        DocumentProvenance.event_type == "generation_intent_receipt"
                    )
                )
            ).scalars()
        )
        assert receipts == []
