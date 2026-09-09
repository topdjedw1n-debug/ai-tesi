"""Actual provider retry boundaries and durable, non-zero-by-assumption receipts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.models.document import DocumentProvenance
from app.services.ai_service import AIService
from app.services.cost_estimator import UsageTracker
from app.services.generation_operations import journal_usage, recorded_provider_call
from tests.test_generation_worker import _seed_job


@pytest.mark.asyncio
async def test_actual_ai_service_retry_records_each_sdk_call(db_session, monkeypatch):
    doc, job = await _seed_job(db_session, email="usage-retry@example.com")
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
        usage=SimpleNamespace(
            prompt_tokens=1800, completion_tokens=1200, total_tokens=3000
        ),
    )
    sdk = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=[TimeoutError(), TimeoutError(), response])
            )
        ),
        close=AsyncMock(),
    )
    factory = MagicMock(return_value=sdk)
    monkeypatch.setattr("openai.AsyncOpenAI", factory)
    monkeypatch.setattr(
        "app.services.ai_service.settings.OPENAI_API_KEY", "fixture-never-sent"
    )
    service = AIService(db_session, usage_tracker=usage)
    service._openai_retry.delays = [0]
    assert (await service._call_openai("gpt-4", "synthetic request"))["ok"]
    assert sdk.chat.completions.create.await_count == 3
    assert all(c.kwargs["max_retries"] == 0 for c in factory.call_args_list)
    confirmed, unknown = await journal_usage(db_session, doc.id, job.id)
    assert confirmed.total_tokens == usage.total_tokens == 3000
    assert confirmed.cost_usd_cents() == usage.cost_usd_cents()
    assert unknown == 2
    events = list(
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "generation_provider_attempt"
                )
            )
        ).scalars()
    )
    assert len(events) == 6
    assert [e.payload["outcome"] for e in events] == [
        "started",
        "failed",
        "started",
        "failed",
        "started",
        "received",
    ]
    assert all(e.payload.get("usage") is None for e in events[:-1])
    assert "synthetic request" in str([e.payload for e in events])
    assert len({e.payload["input_fingerprint"] for e in events}) == 1


@pytest.mark.asyncio
async def test_no_paid_call_when_started_receipt_cannot_commit(monkeypatch):
    usage = UsageTracker()
    usage.generation_context = {"document_id": 1, "job_id": 1, "worker_attempt": 1}
    monkeypatch.setattr(
        "app.services.generation_operations._append",
        AsyncMock(side_effect=RuntimeError("journal unavailable")),
    )
    call = AsyncMock()
    with pytest.raises(RuntimeError, match="journal unavailable"):
        await recorded_provider_call(
            call,
            provider="openai",
            model="gpt-4",
            request={},
            usage_tracker=usage,
            purpose="review",
        )
    call.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("application_retries,expected_sdk_calls", [(0, 1), (3, 4)])
async def test_provider_timeout_cap_counts_actual_application_layer(
    db_session, monkeypatch, application_retries, expected_sdk_calls
):
    doc, job = await _seed_job(
        db_session, email=f"cap-{application_retries}@example.com"
    )
    usage = UsageTracker()
    usage.generation_context = {
        "document_id": doc.id,
        "job_id": job.id,
        "worker_attempt": 1,
    }
    sdk = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(side_effect=TimeoutError()))
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr("openai.AsyncOpenAI", MagicMock(return_value=sdk))
    monkeypatch.setattr(
        "app.services.ai_service.settings.OPENAI_API_KEY", "fixture-never-sent"
    )
    service = AIService(
        db_session, usage_tracker=usage, max_retries=application_retries
    )
    service._openai_retry.delays = [0]
    with pytest.raises(TimeoutError):
        await service._call_openai("gpt-4", "fixture")
    confirmed, unknown = await journal_usage(db_session, doc.id, job.id)
    assert sdk.chat.completions.create.await_count == unknown == expected_sdk_calls
    assert confirmed.total_tokens == 0  # Confirmed subtotal, not total provider spend.


@pytest.mark.asyncio
async def test_worker_restores_received_usage_before_crashed_job_total_write(
    db_session, monkeypatch
):
    """A committed SDK receipt survives death before the job counters flush."""
    from contextlib import ExitStack

    import tests.test_provenance_ledger as pipeline
    from app.services.background_jobs import BackgroundJobService
    from tests.test_usage_accounting import (
        _capturing_generator_patch,
    )
    from tests.test_usage_accounting import (
        _seed_job as seed_usage_job,
    )

    monkeypatch.setattr(
        "app.services.background_jobs.settings", pipeline.make_settings()
    )
    user, doc = await pipeline.seed_document(
        db_session, section_titles=("Unfinished section",)
    )
    job = await seed_usage_job(db_session, user, doc)
    doc_id, job_id, owner_id = int(doc.id), int(job.id), int(user.id)
    tracker = UsageTracker()
    tracker.generation_context = {
        "document_id": doc_id,
        "job_id": job_id,
        "worker_attempt": 1,
    }
    sdk = AsyncMock(
        return_value=SimpleNamespace(
            id="paid-before-worker-death",
            usage=SimpleNamespace(prompt_tokens=1800, completion_tokens=1200),
        )
    )
    await recorded_provider_call(
        sdk,
        provider="openai",
        model="gpt-4",
        request={"fixture": True},
        usage_tracker=tracker,
        purpose="outline",
    )
    # The old process never called UsageTracker.add or flushed job totals.
    assert tracker.total_tokens == job.total_tokens == 0
    assert (await journal_usage(db_session, doc_id, job_id))[0].total_tokens == 3000
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    with ExitStack() as stack:
        pipeline.pipeline_harness(stack, db_session, redis, generate_side_effect=[None])
        _capturing_generator_patch(
            stack,
            [pipeline.section_result(1, [pipeline.SOURCE_A])],
            tokens_per_call=1200,
        )
        await BackgroundJobService.generate_full_document(
            document_id=doc_id,
            user_id=owner_id,
            job_id=job_id,
        )
    await db_session.refresh(job)
    assert job.total_tokens == 4200
    expected = UsageTracker()
    expected.add("openai", "gpt-4", 1800, 1200)
    added = UsageTracker()
    added.add("openai", "gpt-4", 1000, 200)
    assert job.cost_cents == added.cost_usd_cents(expected)
    sdk.assert_awaited_once()


@pytest.mark.parametrize("input_tokens,output_tokens", [(40, 80), (40, 40)])
def test_attempt_cost_rounds_once_across_the_journal(input_tokens, output_tokens):
    first, second, combined = UsageTracker(), UsageTracker(), UsageTracker()
    first.add("openai", "gpt-4", input_tokens, output_tokens)
    second.add("openai", "gpt-4", input_tokens, output_tokens)
    combined.add("openai", "gpt-4", input_tokens * 2, output_tokens * 2)
    assert second.cost_usd_cents(first) == combined.cost_usd_cents()
    assert first.cost_usd_cents() + second.cost_usd_cents() != combined.cost_usd_cents()
