"""
Stage B3: real token accounting.

AIGenerationJob.total_tokens / cost_cents were never written; the admin
costs endpoint and the production-case economics returned zeros. These
tests pin the fix: provider calls record real response.usage into a
UsageTracker, the background job writes absolute totals incrementally,
and the case serializer exposes tokens + EUR cost.
"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import tests.test_provenance_ledger as harness_mod
from app.models.document import AIGenerationJob, DocumentSection, ProductionCase
from app.services.admin_service import AdminService
from app.services.ai_service import AIService
from app.services.background_jobs import BackgroundJobService
from app.services.cost_estimator import UsageTracker
from app.services.production_case_service import ProductionCaseService


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


# ---------------------------------------------------------------------------
# Unit: UsageTracker
# ---------------------------------------------------------------------------


def test_usage_tracker_cost_cents_split_pricing():
    tracker = UsageTracker()
    tracker.add("openai", "gpt-4", 1_000_000, 1_000_000)
    # $30/1M input + $60/1M output = $90 = 9000 cents
    assert tracker.cost_usd_cents() == 9000
    assert tracker.total_tokens == 2_000_000


def test_usage_tracker_unknown_model_falls_back_to_gpt4_pricing():
    tracker = UsageTracker()
    tracker.add("openai", "gpt-99-experimental", 1_000_000, 0)
    assert tracker.cost_usd_cents() == 3000  # $30/1M input fallback


def test_usage_tracker_accumulates_across_models():
    tracker = UsageTracker()
    tracker.add("openai", "gpt-4", 500, 300)
    tracker.add("anthropic", "claude-3-5-sonnet-20241022", 200, 100)
    tracker.add("openai", "gpt-4", 100, 50)
    assert tracker.total_tokens == 1250
    assert tracker.snapshot() == 1250


def test_usage_tracker_ignores_negative_and_none():
    tracker = UsageTracker()
    tracker.add("openai", "gpt-4", -5, None)  # type: ignore[arg-type]
    assert tracker.total_tokens == 0


# ---------------------------------------------------------------------------
# Provider calls record real usage
# ---------------------------------------------------------------------------


def _openai_response(prompt_tokens=1000, completion_tokens=500, content="text"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


@pytest.mark.asyncio
async def test_section_generator_records_real_usage(monkeypatch):
    from app.services.ai_pipeline.generator import SectionGenerator

    monkeypatch.setattr(
        "app.services.ai_pipeline.generator.settings.OPENAI_API_KEY", "test-key"
    )
    tracker = UsageTracker()
    generator = SectionGenerator(usage_tracker=tracker)

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_openai_response(1000, 500)
    )
    with patch("openai.AsyncOpenAI", return_value=fake_client):
        text = await generator._call_openai("gpt-4", "Write a section", "en")

    assert text == "text"
    assert tracker.total_tokens == 1500
    assert tracker.cost_usd_cents() == 6  # 1000*$30/1M + 500*$60/1M = $0.06


@pytest.mark.asyncio
async def test_ai_service_call_with_fallback_records_usage(monkeypatch):
    """Panel/claim-verifier coverage proof: they call AIService.call_with_fallback."""
    monkeypatch.setattr("app.services.ai_service.settings.OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.ai_service.settings.AI_ENABLE_FALLBACK", False)
    tracker = UsageTracker()
    service = AIService(MagicMock(), usage_tracker=tracker)

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_openai_response(800, 200, content='{"score": 80}')
    )
    with patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await service.call_with_fallback("Review this section")

    assert result["tokens_used"] == 1000
    assert tracker.total_tokens == 1000


@pytest.mark.asyncio
async def test_humanizer_records_real_usage(monkeypatch):
    from app.services.ai_pipeline.humanizer import Humanizer

    monkeypatch.setattr(
        "app.services.ai_pipeline.humanizer.settings.OPENAI_API_KEY", "test-key"
    )
    tracker = UsageTracker()
    humanizer = Humanizer(usage_tracker=tracker)

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_openai_response(700, 300, content="humanized")
    )
    with patch("openai.AsyncOpenAI", return_value=fake_client):
        text = await humanizer._call_openai("gpt-4", "Paraphrase", 0.9)

    assert text == "humanized"
    assert tracker.total_tokens == 1000


# ---------------------------------------------------------------------------
# Background job writes totals
# ---------------------------------------------------------------------------


def _capturing_generator_patch(stack, results, tokens_per_call=1200):
    """Re-patch SectionGenerator so the constructor's usage_tracker kwarg is
    captured and every generate_section call records real-looking usage."""
    captured = {}

    def factory(*args, **kwargs):
        captured["tracker"] = kwargs.get("usage_tracker")
        generator = MagicMock()

        call_state = {"i": 0}

        async def generate_section(**_kwargs):
            tracker = captured.get("tracker")
            if tracker is not None:
                tracker.add("openai", "gpt-4", tokens_per_call - 200, 200)
            index = min(call_state["i"], len(results) - 1)
            call_state["i"] += 1
            result = results[index]
            if isinstance(result, Exception):
                raise result
            return result

        generator.generate_section = AsyncMock(side_effect=generate_section)
        return generator

    stack.enter_context(
        patch("app.services.background_jobs.SectionGenerator", side_effect=factory)
    )
    return captured


async def _seed_job(db_session, user, document):
    job = AIGenerationJob(
        document_id=document.id,
        user_id=user.id,
        job_type="document_generation",
        status="running",
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.mark.asyncio
async def test_job_totals_written_on_completion(db_session, mock_redis, monkeypatch):
    monkeypatch.setattr(
        "app.services.background_jobs.settings", harness_mod.make_settings()
    )
    user, document = await harness_mod.seed_document(
        db_session, section_titles=("Intro", "Methods")
    )
    job = await _seed_job(db_session, user, document)
    document_id, job_id = document.id, job.id

    with ExitStack() as stack:
        harness_mod.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[None, None],  # replaced below
        )
        _capturing_generator_patch(
            stack,
            [
                harness_mod.section_result(1, [harness_mod.SOURCE_A]),
                harness_mod.section_result(2, [harness_mod.SOURCE_B]),
            ],
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id, job_id=job_id
        )

    refreshed_job = (
        await db_session.execute(
            select(AIGenerationJob).where(AIGenerationJob.id == job_id)
        )
    ).scalar_one()
    assert refreshed_job.total_tokens == 2400  # 2 sections x 1200
    assert refreshed_job.cost_cents > 0

    sections = (
        (
            await db_session.execute(
                select(DocumentSection)
                .where(DocumentSection.document_id == document_id)
                .order_by(DocumentSection.section_index)
            )
        )
        .scalars()
        .all()
    )
    assert all(s.tokens_used == 1200 for s in sections)


@pytest.mark.asyncio
async def test_job_partial_totals_survive_midrun_failure(
    db_session, mock_redis, monkeypatch
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings", harness_mod.make_settings()
    )
    user, document = await harness_mod.seed_document(
        db_session, section_titles=("Intro", "Methods")
    )
    job = await _seed_job(db_session, user, document)
    document_id, job_id = document.id, job.id

    with ExitStack() as stack:
        harness_mod.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[None, None],
        )
        _capturing_generator_patch(
            stack,
            [
                harness_mod.section_result(1, [harness_mod.SOURCE_A]),
                RuntimeError("provider outage on section 2"),
            ],
        )
        try:
            await BackgroundJobService.generate_full_document(
                document_id=document_id, user_id=user.id, job_id=job_id
            )
        except Exception:
            pass  # the job dying is the scenario under test

    refreshed_job = (
        await db_session.execute(
            select(AIGenerationJob).where(AIGenerationJob.id == job_id)
        )
    ).scalar_one()
    # Section 1's spend was written before the crash (honest partials).
    # The failed call itself recorded usage too — at least section 1's total.
    assert refreshed_job.total_tokens >= 1200


# ---------------------------------------------------------------------------
# Aggregation surfaces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_cost_analysis_aggregates(db_session):
    user, document = await harness_mod.seed_document(db_session)
    for tokens, cents in ((10_000, 120), (5_000, 60)):
        db_session.add(
            AIGenerationJob(
                document_id=document.id,
                user_id=user.id,
                job_type="document_generation",
                status="completed",
                total_tokens=tokens,
                cost_cents=cents,
            )
        )
    await db_session.commit()

    result = await AdminService(db_session).get_cost_analysis()

    assert result["totals"]["total_tokens"] == 15_000
    assert result["totals"]["total_cost_cents"] == 180
    assert result["totals"]["total_cost_eur_cents"] > 0


@pytest.mark.asyncio
async def test_serialize_case_includes_ai_cost(db_session, monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "USD_TO_EUR_RATE", 0.5)
    user, document = await harness_mod.seed_document(db_session)
    db_session.add(
        AIGenerationJob(
            document_id=document.id,
            user_id=user.id,
            job_type="document_generation",
            status="completed",
            total_tokens=42_000,
            cost_cents=200,
        )
    )
    case = ProductionCase(document_id=document.id, client_user_id=user.id)
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)

    serialized = await ProductionCaseService(db_session).serialize_case(case)

    assert serialized["ai_total_tokens"] == 42_000
    assert serialized["ai_cost_usd_cents"] == 200
    assert serialized["ai_cost_eur_cents"] == 100  # 200 * 0.5
