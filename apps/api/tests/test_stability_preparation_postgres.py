"""Real PostgreSQL: a pending plan-preparation reply never holds the Job row.

Job 15 replay (2026-09-08; real API/worker/PostgreSQL, synthetic SDK reply):
with the whole preparation inside ``hold_generation_job_lease`` the heartbeat
did not advance during an 11.5 s held provider call, cancellation finished only
after the provider released, and the late answer still rewrote the outline.
The lease guard must wrap only the durable writes; the external wait runs
outside it. Requires M0_03_TEST_DATABASE_URL (the ``postgres`` fixture);
skips are never acceptance.
"""

import asyncio
import copy
import functools
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    DocumentSection,
)
from app.services import plan_preparation
from app.services.academic_context import digest
from app.services.cost_estimator import UsageTracker
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_operations import journal_usage
from app.services.generation_outcomes import GenerationStageError
from app.services.generation_profile import generation_profile_sha256
from app.services.generation_worker import (
    GenerationLeaseLostError,
    cancel_active_generation_job,
    claim_next_generation_job,
    hold_generation_job_lease,
    renew_generation_lease,
    utc_now,
)
from app.services.plan_preparation import prepare_final_plan
from tests import test_release_evidence_postgres as release_pg
from tests.test_academic_quality import example
from tests.test_stability_plan_budget import MODEL, _answer

postgres = release_pg.postgres
pytestmark = pytest.mark.asyncio

RUN_REQUIREMENTS = "Preserve exactly these four chapters."
PREPARATION = "academic_plan_preparation"


async def leased_work():
    """A provisional plan with one pruned key, enqueued and claimed by worker-a.

    The pruned key forces a model reconciliation; the frozen pack, preflight
    trace and contract fingerprints are the same immutable inputs the worker
    binds to.
    """
    doc, _, pack = example()
    valid = copy.deepcopy(doc.outline)
    doc.outline = copy.deepcopy(doc.outline)
    doc.outline["sections"][0]["evidence_keys"] = ["Pruned2020"]
    async with AsyncSessionLocal() as db:
        user = User(
            email="preparation-lease@example.com",
            full_name="Preparation lease",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        doc.user_id = user.id
        db.add(doc)
        db.add(
            DocumentProvenance(
                document_id=doc.id,
                stage="retrieval",
                event_type="source_pack_preflight",
                payload={
                    "sha256": pack.sha256(),
                    "retrieval_trace": [
                        {
                            "provider": "search_openalex",
                            "query": "care",
                            "retrieved_at": "2026-09-08T00:00:00+00:00",
                            "status": "returned",
                            "count": 1,
                        }
                    ],
                    "candidates": 1,
                    "verified": 1,
                    "rejected_by_reason": {},
                },
            )
        )
        await db.flush()
        job = AIGenerationJob(
            user_id=user.id,
            document_id=doc.id,
            job_type="full_document",
            status="queued",
            attempt_count=0,
            max_attempts=3,
            request_payload={
                "profile_sha256": generation_profile_sha256(doc, int(user.id)),
                "additional_requirements": RUN_REQUIREMENTS,
                "generation_contract_sha256": generation_contract_sha256(
                    doc, None, RUN_REQUIREMENTS
                ),
            },
        )
        db.add(job)
        await db.commit()
        doc_id, job_id = int(doc.id), int(job.id)
    async with AsyncSessionLocal() as db:
        claimed = await claim_next_generation_job(db, worker_id="worker-a")
    assert claimed is not None and claimed.id == job_id
    return SimpleNamespace(
        doc_id=doc_id,
        job_id=job_id,
        owner=claimed.lease_owner,
        token=claimed.lease_token,
        pack=pack,
        valid=valid,
        outline_sha=digest(doc.outline),
    )


def _usage(work):
    usage = UsageTracker()
    usage.generation_context = {
        "document_id": work.doc_id,
        "job_id": work.job_id,
        "worker_attempt": 1,
    }
    return usage


async def _prepare(work, *, ai_service=None, usage=None, owner=None, token=None):
    """Run the stage exactly as the worker does: its own session, guarded writes."""
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, work.doc_id)
        job = await db.get(AIGenerationJob, work.job_id)
        return await prepare_final_plan(
            db,
            document,
            job,
            work.pack,
            usage_tracker=usage,
            ai_service=ai_service,
            persist_guard=functools.partial(
                hold_generation_job_lease,
                job_id=work.job_id,
                worker_id=owner or work.owner,
                lease_token=token or work.token,
                document_id=work.doc_id,
            ),
        )


def _held_transport(monkeypatch, reply):
    """Real AIService on a synthetic Anthropic SDK whose reply waits for release."""
    held, release = asyncio.Event(), asyncio.Event()

    async def create(**kwargs):
        held.set()
        await release.wait()
        answer = reply()
        if isinstance(answer, BaseException):
            raise answer
        return answer

    sdk = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(side_effect=create)),
        close=AsyncMock(),
    )
    monkeypatch.setattr("anthropic.AsyncAnthropic", MagicMock(return_value=sdk))
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "fixture-never-sent")
    monkeypatch.setattr(settings, "AI_FALLBACK_CHAIN", f"anthropic:{MODEL}")
    real_service = plan_preparation.AIService

    def factory(db, **kwargs):
        service = real_service(db, **kwargs)
        service._anthropic_retry.delays = [0]
        return service

    monkeypatch.setattr(plan_preparation, "AIService", factory)
    return sdk, held, release


async def _events(db, doc_id):
    return list(
        (
            await db.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.document_id == doc_id)
                .order_by(DocumentProvenance.id)
            )
        ).scalars()
    )


async def _section_count(db, doc_id):
    return await db.scalar(
        select(func.count())
        .select_from(DocumentSection)
        .where(DocumentSection.document_id == doc_id)
    )


async def _lease(job_id):
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, job_id)
        return (
            job.status,
            job.lease_owner,
            job.lease_token,
            job.heartbeat_at,
            job.lease_expires_at,
        )


async def _renew(work):
    async with AsyncSessionLocal() as db:
        return await asyncio.wait_for(
            renew_generation_lease(
                db, job_id=work.job_id, worker_id=work.owner, lease_token=work.token
            ),
            timeout=5,
        )


async def test_cancel_and_heartbeat_do_not_wait_behind_a_pending_preparation(
    postgres, monkeypatch
):
    sdk, held, release = _held_transport(
        monkeypatch,
        lambda: _answer(json.dumps(example()[0].outline), out=5200, rid="late"),
    )
    work = await leased_work()
    task = asyncio.create_task(_prepare(work, usage=_usage(work)))
    try:
        await asyncio.wait_for(held.wait(), timeout=10)
        _, _, _, heartbeat_before, expiry_before = await _lease(work.job_id)
        async with AsyncSessionLocal() as db:
            types = [e.event_type for e in await _events(db, work.doc_id)]
        assert types == [
            "source_pack_preflight",
            PREPARATION + "_started",
            "generation_provider_attempt",
        ]
        # The heartbeat renews while the reply is pending: no Job row is held.
        assert await _renew(work)
        _, _, _, heartbeat_after, expiry_after = await _lease(work.job_id)
        assert heartbeat_after > heartbeat_before and expiry_after > expiry_before
        # Cancellation completes while the provider still has not answered.
        async with AsyncSessionLocal() as db:
            cancelled = await asyncio.wait_for(
                cancel_active_generation_job(
                    db, document_id=work.doc_id, cancelled_by="user:test"
                ),
                timeout=5,
            )
        assert cancelled == work.job_id
        assert not release.is_set() and not task.done()
    finally:
        release.set()
    with pytest.raises(GenerationLeaseLostError):
        await asyncio.wait_for(task, timeout=10)
    assert sdk.messages.create.await_count == 1
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, work.job_id)
        document = await db.get(Document, work.doc_id)
        assert (job.status, job.lease_owner, job.lease_token) == (
            "cancelled",
            None,
            None,
        )
        assert document.status == "failed"
        # The late, valid answer changed nothing the cancelled job owned.
        assert digest(document.outline) == work.outline_sha
        assert document.outline["sections"][0]["evidence_keys"] == ["Pruned2020"]
        assert await _section_count(db, work.doc_id) == 0
        events = await _events(db, work.doc_id)
        types = [e.event_type for e in events]
        assert PREPARATION not in types
        assert types.count(PREPARATION + "_started") == 1
        assert "generation_cancelled" in types
        # Spend that happened is still on record: the reply's receipt lands.
        receipts = [
            e.payload for e in events if e.event_type == "generation_provider_attempt"
        ]
        assert [r["outcome"] for r in receipts] == ["started", "received"]
        assert {r["stage"] for r in receipts} == {PREPARATION}
        confirmed, unknown = await journal_usage(db, work.doc_id, work.job_id)
        assert (confirmed.total_tokens, unknown) == (32846 + 5200, 0)


async def test_late_failure_after_takeover_is_fenced_and_the_new_owner_proceeds(
    postgres,
):
    work = await leased_work()
    held, release = asyncio.Event(), asyncio.Event()

    async def provider(*args, **kwargs):
        held.set()
        await release.wait()
        raise TimeoutError()

    stale = SimpleNamespace(call_with_fallback=AsyncMock(side_effect=provider))
    task = asyncio.create_task(_prepare(work, ai_service=stale))
    try:
        await asyncio.wait_for(held.wait(), timeout=10)
        # Missed heartbeats: the lease expires while the reply is pending and
        # another worker takes the job over, which the free row allows.
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AIGenerationJob)
                .where(AIGenerationJob.id == work.job_id)
                .values(lease_expires_at=utc_now() - timedelta(seconds=1))
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            replacement = await asyncio.wait_for(
                claim_next_generation_job(db, worker_id="worker-b"), timeout=5
            )
        assert replacement is not None and replacement.id == work.job_id
        assert replacement.lease_token != work.token
        assert replacement.attempt_count == 2
        new_lease = await _lease(work.job_id)
    finally:
        release.set()
    with pytest.raises(GenerationLeaseLostError):
        await asyncio.wait_for(task, timeout=10)
    async with AsyncSessionLocal() as db:
        # The stale attempt's failure is not written and the replacement
        # owner's lease is untouched (not renewed, not cleared).
        assert await _lease(work.job_id) == new_lease
        assert new_lease[:3] == ("running", "worker-b", replacement.lease_token)
        events = await _events(db, work.doc_id)
        assert [e.event_type for e in events] == [
            "source_pack_preflight",
            PREPARATION + "_started",
        ]
        assert events[-1].payload["worker_attempt"] == 1
        assert digest((await db.get(Document, work.doc_id)).outline) == work.outline_sha
    # The replacement owner reconciles the same immutable inputs afresh.
    fresh = SimpleNamespace(call_with_fallback=AsyncMock(return_value=work.valid))
    result = await _prepare(
        work, ai_service=fresh, owner="worker-b", token=replacement.lease_token
    )
    assert result["status"] == "completed" and result["worker_attempt"] == 2
    assert stale.call_with_fallback.await_count == 1
    assert fresh.call_with_fallback.await_count == 1
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, work.doc_id)
        assert digest(document.outline) == result["output_sha256"]
        assert document.outline["sections"][0]["evidence_keys"] == ["Author2024"]
        events = await _events(db, work.doc_id)
        assert [e.event_type for e in events] == [
            "source_pack_preflight",
            PREPARATION + "_started",
            PREPARATION + "_started",
            PREPARATION,
        ]
        assert [e.payload["worker_attempt"] for e in events[1:]] == [1, 2, 2]
        status, owner, token, _, expiry = await _lease(work.job_id)
        assert (status, owner) == ("running", "worker-b")
        assert token == replacement.lease_token
        assert expiry > new_lease[4]  # the owned guard renewed on the way out


async def test_delayed_failure_under_a_renewed_lease_is_classified_and_accounted(
    postgres, monkeypatch
):
    sdk, held, release = _held_transport(
        monkeypatch,
        lambda: _answer(json.dumps({"answer": "Ho letto il piano."}), out=40),
    )
    work = await leased_work()
    task = asyncio.create_task(_prepare(work, usage=_usage(work)))
    try:
        await asyncio.wait_for(held.wait(), timeout=10)
        # The reply outlives the original lease window; heartbeats alone keep
        # the attempt owned, which only works when the row is not held.
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AIGenerationJob)
                .where(AIGenerationJob.id == work.job_id)
                .values(lease_expires_at=utc_now() + timedelta(seconds=2))
            )
            await db.commit()
        assert await _renew(work)
        _, _, _, _, renewed_expiry = await _lease(work.job_id)
        assert renewed_expiry > utc_now() + timedelta(seconds=60)
        await asyncio.sleep(2.1)  # The reply really outlives the original 2 s lease.
    finally:
        release.set()
    with pytest.raises(GenerationStageError) as error:
        await asyncio.wait_for(task, timeout=10)
    assert error.value.reason_code == "review_temporarily_unavailable"
    assert sdk.messages.create.await_count == 1
    async with AsyncSessionLocal() as db:
        status, owner, token, _, expiry = await _lease(work.job_id)
        assert (status, owner, token) == ("running", work.owner, work.token)
        assert expiry >= renewed_expiry
        assert digest((await db.get(Document, work.doc_id)).outline) == work.outline_sha
        events = await _events(db, work.doc_id)
        (finished,) = (e for e in events if e.event_type == PREPARATION)
        assert (
            finished.payload["status"],
            finished.payload["outcome"],
            finished.payload["reason_code"],
            finished.payload["worker_attempt"],
        ) == ("unchecked", "unusable", "review_temporarily_unavailable", 1)
        receipts = [
            e.payload for e in events if e.event_type == "generation_provider_attempt"
        ]
        assert [r["outcome"] for r in receipts] == ["started", "received"]
        confirmed, unknown = await journal_usage(db, work.doc_id, work.job_id)
        assert (confirmed.total_tokens, unknown) == (32846 + 40, 0)
