"""Same-job recovery and replacement behavior through the shared API services."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1.endpoints.generate import enqueue_full_document
from app.models.admin import SystemSetting
from app.models.auth import User
from app.models.document import AIGenerationJob, DocumentProvenance
from app.schemas.document import AsyncGenerationRequest, GenerationResumeRequest
from app.services.generation_outcomes import GenerationStageError
from app.services.generation_pause import PAUSE_KEY, require_generation_open
from app.services.generation_profile import generation_profile_sha256
from app.services.generation_recovery import (
    recovery_state,
    resume_generation,
    terminal_fingerprint,
)
from app.services.generation_worker import (
    claim_next_generation_job,
    reschedule_or_fail_generation_job,
    utc_now,
)
from tests.test_generation_worker import _seed_job


async def stopped_work(db, reason="provider_temporarily_unavailable"):
    document, job = await _seed_job(
        db,
        email="stability@example.com",
        status="failed",
        attempt_count=3,
        max_attempts=3,
    )
    document.status = "failed"
    job.total_tokens, job.cost_cents, job.claim_checks_used = 1000, 4, 7
    job.request_payload = {
        **job.request_payload,
        "last_outcome": {"stage": "review", "reason_code": reason},
    }
    await db.commit()
    owner = await db.get(User, job.user_id)
    return document, job, owner


def resume_request(job, intent="intent-first", fingerprint=None):
    return GenerationResumeRequest(
        intent_id=intent,
        expected_fingerprint=fingerprint or terminal_fingerprint(job),
        confirm_paid=True,
        confirm_access_restored=True,
    )


@pytest.mark.asyncio
async def test_one_grant_and_receipts_survive_later_failure(db_session):
    doc, job, owner = await stopped_work(db_session)
    request = resume_request(job)
    identity = job.id
    assert (await resume_generation(db_session, doc.id, owner, request)).id == identity
    assert (
        job.attempt_count,
        job.max_attempts,
        job.total_tokens,
        job.cost_cents,
        job.claim_checks_used,
    ) == (3, 6, 1000, 4, 7)
    joined = resume_request(job, "intent-second", request.expected_fingerprint)
    await resume_generation(db_session, doc.id, owner, joined)
    for _ in range(3):
        claimed = await claim_next_generation_job(db_session, worker_id="resumer")
        assert claimed is not None
        await reschedule_or_fail_generation_job(
            db_session,
            job_id=job.id,
            worker_id=claimed.lease_owner,
            lease_token=claimed.lease_token,
            error=GenerationStageError(
                "review_temporarily_unavailable", "fixture timeout", stage="review"
            ),
            terminal=False,
        )
        await db_session.refresh(job)
        job.available_at = utc_now()
        await db_session.commit()
    assert job.status == "failed" and job.attempt_count == 6
    for old in [request, joined]:
        result = await resume_generation(db_session, doc.id, owner, old)
        assert result.status == "failed" and result.max_attempts == 6
    stale = resume_request(job, "intent-stale", request.expected_fingerprint)
    with pytest.raises(HTTPException) as error:
        await resume_generation(db_session, doc.id, owner, stale)
    assert error.value.status_code == 409
    receipts = list(
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "generation_intent_receipt"
                )
            )
        ).scalars()
    )
    assert len(receipts) == 2 and sum(e.payload["granted"] for e in receipts) == 1


@pytest.mark.asyncio
async def test_default_start_cannot_erase_a_resumable_result(db_session):
    doc, job, owner = await stopped_work(db_session)
    doc.content = "Saved work must remain"
    await db_session.commit()
    before = terminal_fingerprint(job)
    with pytest.raises(HTTPException) as error:
        await enqueue_full_document(
            AsyncGenerationRequest(document_id=doc.id), owner, db_session
        )
    assert (
        error.value.status_code == 409
        and error.value.detail["reason_code"] == "resumable_job_exists"
    )
    assert (
        doc.content == "Saved work must remain" and terminal_fingerprint(job) == before
    )


@pytest.mark.asyncio
async def test_non_resumable_replacement_is_explicit_and_idempotent(
    db_session, monkeypatch
):
    doc, job, owner = await stopped_work(db_session, "academic_content_rejected")
    old_id = job.id
    doc.content = "Rejected original"
    await db_session.commit()
    monkeypatch.setattr(
        "app.api.v1.endpoints.generate._delete_superseded_artifacts", AsyncMock()
    )
    request = AsyncGenerationRequest(
        document_id=doc.id,
        mode="new_version",
        intent_id="replace-once",
        expected_fingerprint=terminal_fingerprint(job),
        confirm_replace=True,
        replacement_reason="The recorded requirement defect was fixed",
    )
    first = await enqueue_full_document(request, owner, db_session)
    second = await enqueue_full_document(request, owner, db_session)
    assert first.job_id == second.job_id and first.job_id != old_id
    old = await db_session.get(AIGenerationJob, old_id)
    assert (old.status, old.total_tokens, old.cost_cents) == ("failed", 1000, 4)
    events = list(
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "generation_replacement"
                )
            )
        ).scalars()
    )
    assert len(events) == 1 and events[0].payload["previous_job_id"] == old_id


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["profile", "legacy", "contract"])
async def test_incompatible_result_has_no_resume(db_session, mismatch):
    doc, job, owner = await stopped_work(db_session)
    if mismatch == "profile":
        doc.ai_model = "different"
    elif mismatch == "legacy":
        job.request_payload = {
            k: v for k, v in job.request_payload.items() if k != "profile_sha256"
        }
    else:
        doc.topic += " changed"
    await db_session.commit()
    state = await recovery_state(db_session, doc, job)
    assert state["allowed_actions"] == ["new_version"]
    assert state["reason_code"] == (
        "legacy_unknown" if mismatch == "legacy" else "contract_or_profile_mismatch"
    )
    with pytest.raises(HTTPException):
        await resume_generation(db_session, doc.id, owner, resume_request(job))
    assert job.status == "failed" and job.total_tokens == 1000


@pytest.mark.asyncio
async def test_pause_blocks_start_and_resume_and_fails_closed(db_session):
    doc, job, owner = await stopped_work(db_session)
    db_session.add(
        SystemSetting(
            key=PAUSE_KEY, value=True, category="generation", updated_by=owner.id
        )
    )
    await db_session.commit()
    for operation in [
        lambda: enqueue_full_document(
            AsyncGenerationRequest(document_id=doc.id), owner, db_session
        ),
        lambda: resume_generation(db_session, doc.id, owner, resume_request(job)),
    ]:
        with pytest.raises(HTTPException) as exc:
            await operation()
        assert exc.value.status_code == 503
    broken_db = AsyncMock()
    broken_db.get_bind = lambda: (_ for _ in ()).throw(
        ConnectionError("database offline")
    )
    with pytest.raises(HTTPException) as exc:
        await require_generation_open(broken_db)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_changed_profile_is_quarantined_at_claim(db_session):
    doc, job, _ = await stopped_work(db_session)
    job.status, job.attempt_count = "queued", 0
    doc.ai_model = "different"
    # Keep the original compatibility fingerprint even if someone updates only the contract.
    from app.services.generation_contract import generation_contract_sha256

    job.request_payload = {
        **job.request_payload,
        "generation_contract_sha256": generation_contract_sha256(
            doc, None, job.request_payload["additional_requirements"]
        ),
    }
    await db_session.commit()
    assert job.request_payload["profile_sha256"] != generation_profile_sha256(doc)
    assert (
        await claim_next_generation_job(db_session, worker_id="changed-profile") is None
    )
    await db_session.refresh(job)
    assert (
        job.status == "failed"
        and job.request_payload["last_outcome"]["reason_code"]
        == "contract_or_profile_mismatch"
    )
