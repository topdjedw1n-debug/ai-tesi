"""Truthful reason codes and current-state views (independent review fixes)."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import redis.exceptions
from fastapi import BackgroundTasks, HTTPException
from minio.error import S3Error
from openai import APIStatusError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from starlette.requests import Request

from app.core.config import settings
from app.models.document import AIGenerationJob, DocumentProvenance, DocumentSection
from app.services.academic_review import review_binding
from app.services.ai_service import AIService
from app.services.circuit_breaker import CircuitBreakerOpenError
from app.services.cost_estimator import UsageTracker
from app.services.generation_operations import journal_usage, operation_purpose
from app.services.generation_outcomes import GenerationStageError, failure_reason
from app.services.generation_pause import PAUSE_KEY, require_generation_open
from app.services.generation_recovery import (
    recovery_state,
    resume_generation,
    terminal_fingerprint,
)
from app.services.generation_worker import complete_generation_job, utc_now
from app.services.settings_service import SettingsService
from tests.test_generation_worker import _seed_job
from tests.test_stability_recovery import resume_request, stopped_work


class _PgConnectionLost(Exception):
    sqlstate = "08006"


class _PgUndefinedTable(Exception):
    sqlstate = "42P01"


def _storage_error(code: str) -> S3Error:
    return S3Error(
        code=code,
        message="fixture",
        resource="/bucket/object",
        request_id="req",
        host_id="host",
        response=None,
    )


def _status_error(status: int) -> APIStatusError:
    response = httpx.Response(
        status, request=httpx.Request("POST", "https://fixture.invalid")
    )
    return APIStatusError("provider failure", response=response, body={})


@pytest.mark.parametrize(
    "error,stage,expected",
    [
        # An open breaker only remembers recent failures; it is not a verdict.
        (CircuitBreakerOpenError("open"), "review", "review_temporarily_unavailable"),
        (
            CircuitBreakerOpenError("open"),
            "generation",
            "provider_temporarily_unavailable",
        ),
        (
            redis.exceptions.ConnectionError("down"),
            "generation",
            "provider_temporarily_unavailable",
        ),
        (
            redis.exceptions.TimeoutError("slow"),
            "review",
            "review_temporarily_unavailable",
        ),
        # Database: lost connections and rollbacks are temporary...
        (
            OperationalError("SELECT 1", {}, _PgConnectionLost()),
            "generation",
            "provider_temporarily_unavailable",
        ),
        (
            OperationalError("SELECT 1", {}, ConnectionRefusedError()),
            "generation",
            "provider_temporarily_unavailable",
        ),
        # ...schema and programming defects are not, whatever the wrapper class.
        (
            ProgrammingError("SELECT 1", {}, _PgUndefinedTable()),
            "generation",
            "unknown_failure",
        ),
        (
            OperationalError("SELECT 1", {}, _PgUndefinedTable()),
            "generation",
            "unknown_failure",
        ),
        # Object storage outside export: outage vs. a frozen object that is gone.
        (_storage_error("SlowDown"), "generation", "provider_temporarily_unavailable"),
        (_storage_error("NoSuchKey"), "generation", "checkpoint_integrity_error"),
        (_storage_error("NoSuchBucket"), "export", "artifact_temporarily_unavailable"),
        (_storage_error("AccessDenied"), "generation", "provider_access_required"),
        # A missing local file is not blindly an availability problem.
        (FileNotFoundError("template.docx"), "generation", "unknown_failure"),
        # Writer request defects are technical, never an academic plan failure.
        (_status_error(404), "generation", "unknown_failure"),
        (_status_error(400), "generation", "unknown_failure"),
        (_status_error(400), "review", "review_input_invalid"),
    ],
)
def test_typed_infrastructure_failures_are_classified_without_guessing(
    error, stage, expected
):
    wrapped = RuntimeError("wrapper")
    wrapped.__cause__ = error
    assert failure_reason(wrapped, stage=stage) == expected


def test_checkpoint_and_intake_reasons_survive_the_worker_mapping():
    checkpoint = GenerationStageError(
        "checkpoint_integrity_error", "invalid outline checkpoint", stage="checkpoint"
    )
    intake = GenerationStageError(
        "plan_requirements_unmet", "uploads not ready", stage="intake"
    )
    assert failure_reason(checkpoint) == "checkpoint_integrity_error"
    assert failure_reason(intake) == "plan_requirements_unmet"


@pytest.mark.asyncio
async def test_receipts_carry_the_business_purpose_of_the_call(db_session, monkeypatch):
    doc, job = await _seed_job(db_session, email="purpose@example.com")
    usage = UsageTracker()
    usage.generation_context = {
        "document_id": doc.id,
        "job_id": job.id,
        "worker_attempt": 1,
    }
    response = SimpleNamespace(
        id="fixture-response",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"ok": true}'), finish_reason="stop"
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    sdk = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=[TimeoutError(), response])
            )
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr("openai.AsyncOpenAI", MagicMock(return_value=sdk))
    monkeypatch.setattr(
        "app.services.ai_service.settings.OPENAI_API_KEY", "fixture-never-sent"
    )
    service = AIService(db_session, usage_tracker=usage)
    service._openai_retry.delays = [0]
    result = await service.call_with_fallback(
        "fixture",
        purpose="academic_outline_review",
        chain_override=[("openai", "gpt-4")],
    )
    assert result["ok"] and operation_purpose.get() is None
    events = list(
        (
            await db_session.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.event_type == "generation_provider_attempt")
                .order_by(DocumentProvenance.id)
            )
        ).scalars()
    )
    assert [e.payload["outcome"] for e in events] == [
        "started",
        "failed",
        "started",
        "received",
    ]
    assert {e.payload["stage"] for e in events} == {"academic_outline_review"}
    assert events[1].payload["reason_code"] == "review_temporarily_unavailable"
    confirmed, unknown = await journal_usage(db_session, doc.id, job.id)
    assert (confirmed.total_tokens, unknown) == (15, 1)


async def _running_job(db_session, email):
    doc, job = await _seed_job(
        db_session, email=email, status="running", attempt_count=2
    )
    job.lease_owner = "worker-1"
    job.lease_token = "token-1"
    job.lease_expires_at = utc_now() + timedelta(minutes=5)
    job.request_payload = {
        **job.request_payload,
        "last_outcome": {
            "stage": "review",
            "reason_code": "review_temporarily_unavailable",
            "retryability": "automatic",
        },
    }
    await db_session.commit()
    return doc, job


@pytest.mark.asyncio
async def test_completed_job_reports_no_stale_failure(db_session):
    doc, job = await _running_job(db_session, "completed-clean@example.com")
    assert await complete_generation_job(
        db_session, job_id=job.id, worker_id="worker-1", lease_token="token-1"
    )
    await db_session.refresh(job)
    outcome = job.request_payload["last_outcome"]
    assert (outcome["outcome"], outcome["reason_code"]) == ("completed", None)
    state = await recovery_state(db_session, doc, job)
    assert state["reason_code"] is None
    assert state["allowed_actions"] == ["new_version"]


@pytest.mark.asyncio
async def test_completed_artifact_keeps_actual_failed_whole_review(db_session):
    doc, job = await _running_job(db_session, "completed-rejected@example.com")
    db_session.add(
        DocumentProvenance(
            document_id=doc.id,
            stage="quality",
            event_type="academic_review",
            payload={
                "binding": review_binding(doc, job, "f" * 64, kind="whole"),
                "kind": "whole",
                "status": "failed",
                "reason": "Descriptive summary without critical comparison.",
            },
        )
    )
    await db_session.commit()
    assert await complete_generation_job(
        db_session, job_id=job.id, worker_id="worker-1", lease_token="token-1"
    )
    await db_session.refresh(job)
    outcome = job.request_payload["last_outcome"]
    assert (outcome["outcome"], outcome["reason_code"]) == (
        "completed",
        "academic_content_rejected",
    )
    state = await recovery_state(db_session, doc, job)
    assert state["reason_code"] == "academic_content_rejected"
    # The verdict is not a release approval and must not become one here.
    assert state["allowed_actions"] == ["new_version"]


@pytest.mark.asyncio
async def test_resume_keeps_the_answered_stop_in_history_not_in_current_view(
    db_session,
):
    doc, job, owner = await stopped_work(db_session)
    await resume_generation(db_session, doc.id, owner, resume_request(job))
    await db_session.refresh(job)
    current = job.request_payload["last_outcome"]
    assert job.status == "queued"
    assert current["outcome"] == "resumed" and current["reason_code"] is None
    assert current["previous_reason_code"] == "provider_temporarily_unavailable"
    state = await recovery_state(db_session, doc, job)
    assert state["reason_code"] is None and state["allowed_actions"] == []
    history = (
        await db_session.execute(
            select(DocumentProvenance).where(
                DocumentProvenance.event_type == "generation_resume"
            )
        )
    ).scalar_one()
    assert history.payload["previous"]["last_outcome"] == {
        "stage": "review",
        "reason_code": "provider_temporarily_unavailable",
    }


@pytest.mark.asyncio
async def test_export_only_resume_ignores_exhausted_claim_budget(
    db_session, monkeypatch
):
    doc, job, owner = await stopped_work(db_session, "artifact_temporarily_unavailable")
    doc.outline = {"sections": [{"title": "Introduzione"}, {"title": "Metodi"}]}
    job.claim_checks_used = settings.CLAIM_VERIFICATION_MAX_CHECKS
    db_session.add(
        DocumentSection(
            document_id=doc.id,
            title="Introduzione",
            section_index=1,
            content="Saved text",
            status="completed",
        )
    )
    await db_session.commit()
    fingerprint = terminal_fingerprint(job)
    monkeypatch.setattr(
        "app.services.generation_recovery.recovery_state",
        AsyncMock(
            return_value={
                "reason_code": "artifact_temporarily_unavailable",
                "allowed_actions": ["resume"],
                "expected_fingerprint": fingerprint,
            }
        ),
    )
    # One section still has to be written: the exhausted budget stays binding.
    with pytest.raises(HTTPException) as error:
        await resume_generation(
            db_session, doc.id, owner, resume_request(job, "needs-writing", fingerprint)
        )
    assert error.value.detail["reason_code"] == "claim_budget_exhausted"
    await db_session.rollback()
    await db_session.refresh(doc)
    await db_session.refresh(job)
    await db_session.refresh(owner)
    db_session.add(
        DocumentSection(
            document_id=doc.id,
            title="Metodi",
            section_index=2,
            content="Saved text",
            status="completed",
        )
    )
    await db_session.commit()
    resumed = await resume_generation(
        db_session, doc.id, owner, resume_request(job, "export-only", fingerprint)
    )
    assert resumed.status == "queued"
    assert resumed.claim_checks_used == settings.CLAIM_VERIFICATION_MAX_CHECKS


@pytest.mark.asyncio
async def test_payment_hook_never_erases_a_saved_result_without_a_job(
    db_session, monkeypatch
):
    from app.api.v1.endpoints import payment as payment_module
    from app.api.v1.endpoints.payment import stripe_webhook

    doc, job = await _seed_job(db_session, email="paid-orphan@example.com")
    owner_id = job.user_id
    doc.content = "Saved legacy result"
    doc.status = "completed"
    await db_session.delete(job)
    await db_session.commit()

    class FakePayments:
        def __init__(self, _db):
            pass

        async def handle_webhook(self, _payload, _signature):
            return SimpleNamespace(
                id=1, status="completed", document_id=doc.id, user_id=owner_id
            )

    invalidate = AsyncMock(return_value=[])
    monkeypatch.setattr(payment_module, "PaymentService", FakePayments)
    monkeypatch.setattr(payment_module.settings, "MVP_FREE_GENERATION_ENABLED", False)
    monkeypatch.setattr(
        "app.api.v1.endpoints.generate._invalidate_previous_generation_evidence",
        invalidate,
    )

    async def receive():
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "query_string": b"",
        },
        receive,
    )
    result = await stripe_webhook(
        request, BackgroundTasks(), stripe_signature="sig", db=db_session
    )
    assert result["generation"] == "manual_start_required"
    invalidate.assert_not_called()
    await db_session.refresh(doc)
    assert doc.content == "Saved legacy result"
    assert (await db_session.execute(select(AIGenerationJob))).scalars().all() == []


@pytest.mark.asyncio
async def test_batch_settings_update_takes_pause_barrier_before_any_write(
    db_session, monkeypatch
):
    doc, job = await _seed_job(db_session, email="pause-batch@example.com")
    events: list[tuple[str, object]] = []

    async def fake_lock(_db, *, shared=False):
        events.append(("lock", shared))

    original = SettingsService.update_setting

    async def spy(self, key, value, category, updated_by):
        events.append(("write", key))
        return await original(self, key, value, category, updated_by)

    monkeypatch.setattr(
        "app.services.generation_pause.lock_generation_pause", fake_lock
    )
    monkeypatch.setattr(SettingsService, "update_setting", spy)
    await SettingsService(db_session).update_settings(
        "generation", {"generation.note": "first", PAUSE_KEY: True}, job.user_id
    )
    assert events[0] == ("lock", False)
    assert events[1] == ("write", "generation.note")
    with pytest.raises(HTTPException) as error:
        await require_generation_open(db_session)
    assert error.value.status_code == 503
    with pytest.raises(ValueError):
        await SettingsService(db_session).update_settings(
            "generation", {PAUSE_KEY: "yes"}, job.user_id
        )
