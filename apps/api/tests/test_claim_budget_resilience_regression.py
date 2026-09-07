"""ISSUE-008: exhausted reservations must not expire the worker's document.

Found in production order 5/job 5 on 2026-09-07 and reproduced in isolated QA.
Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from app.services.background_jobs import BackgroundJobService
from app.services.generation_worker import (
    claim_next_generation_job,
    reserve_generation_claim_checks,
)
from tests import test_claim_verifier as claim_fixtures
from tests.test_generation_worker import _seed_job

mock_redis = claim_fixtures.mock_redis


@pytest.mark.asyncio
async def test_unlimited_claim_accounting_survives_more_than_old_cap(db_session):
    document, job = await _seed_job(db_session, email="unlimited-claims@example.com")
    claimed = await claim_next_generation_job(
        db_session, worker_id="qa", lease_seconds=120
    )
    args = {
        "job_id": job.id,
        "document_id": document.id,
        "worker_id": claimed.lease_owner,
        "lease_token": claimed.lease_token,
        "max_checks": None,
    }
    assert await reserve_generation_claim_checks(db_session, requested=100, **args) == (
        100,
        100,
    )
    assert await reserve_generation_claim_checks(db_session, requested=32, **args) == (
        32,
        132,
    )
    await db_session.refresh(job)
    assert job.claim_checks_used == 132


@pytest.mark.asyncio
async def test_unlimited_internal_user_checks_claims_despite_small_default_quota(
    db_session, mock_redis, monkeypatch
):
    user, document = await claim_fixtures.seed_document(db_session)
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        claim_fixtures.make_settings(
            CLAIM_VERIFICATION_MAX_CHECKS=0,
            CLAIM_VERIFICATION_BLOCKING=True,
            UNLIMITED_GENERATION_USER_IDS=[user.id],
        ),
    )
    with ExitStack() as stack:
        mocks = claim_fixtures.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            claim_llm_response=claim_fixtures.llm_verdicts(("supported", "Supported.")),
        )
        await BackgroundJobService.generate_full_document(
            document_id=document.id, user_id=user.id
        )
        assert mocks["export_document"].await_count == 1
        assert mocks["ai_service"].call_with_fallback.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", [0, 1])
async def test_empty_claim_reservation_keeps_loaded_document_usable(
    db_session, requested
):
    document, job = await _seed_job(db_session, email="claim-budget-qa@example.com")
    claimed = await claim_next_generation_job(
        db_session, worker_id="qa", lease_seconds=120
    )
    args = {
        "job_id": job.id,
        "document_id": document.id,
        "worker_id": claimed.lease_owner,
        "lease_token": claimed.lease_token,
        "max_checks": 1,
    }
    provider = document.ai_provider
    assert await reserve_generation_claim_checks(db_session, requested=1, **args) == (
        1,
        1,
    )
    assert await reserve_generation_claim_checks(
        db_session, requested=requested, **args
    ) == (0, 1)
    # The next section attempt reads these already-loaded fields synchronously.
    assert document.ai_provider == provider
    assert document.id == args["document_id"]


@pytest.mark.asyncio
async def test_advisory_claim_budget_does_not_cancel_a_panel_repair(
    db_session, mock_redis, monkeypatch
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        claim_fixtures.make_settings(
            CLAIM_VERIFICATION_BLOCKING=False,
            CLAIM_VERIFICATION_MAX_CHECKS=0,
            QUALITY_PANEL_ENABLED=True,
            QUALITY_GATES_ENABLED=True,
            QUALITY_MAX_REGENERATE_ATTEMPTS=1,
        ),
    )
    user, document = await claim_fixtures.seed_document(db_session)
    with ExitStack() as stack:
        mocks = claim_fixtures.pipeline_harness(
            stack, db_session, mock_redis, claim_llm_response={}
        )
        panel = stack.enter_context(
            patch(
                "app.services.background_jobs._check_panel_quality",
                new=AsyncMock(
                    side_effect=[
                        {"passed": False, "overall_score": 40, "reviewers": []},
                        {"passed": True, "overall_score": 90, "reviewers": []},
                    ]
                ),
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=document.id, user_id=user.id
        )
        assert panel.await_count == 2
        assert mocks["generate_section"].await_count == 2
        assert mocks["export_document"].await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "budget,has_abstract,completes",
    [(0, True, False), (100, False, False), (100, True, True)],
)
async def test_qualitative_grounding_requires_actual_semantic_check(
    db_session, mock_redis, monkeypatch, budget, has_abstract, completes
):
    from app.core.exceptions import CitationIntegrityError
    from app.services.ai_pipeline.rag_retriever import SourceDoc
    from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
    from app.services.grounding_gate import evaluate_grounding

    user, document = await claim_fixtures.seed_document(db_session)
    source = {
        **claim_fixtures.SOURCE_A,
        "abstract": claim_fixtures.ABSTRACT if has_abstract else None,
    }
    pack = SourcePack(
        document_id=document.id,
        topic=document.topic,
        sources=[PackedSource(SourceDoc(**source), "Vaswani2017", 0.9)],
    )
    content = "L'attenzione sostituisce la ricorrenza [Vaswani2017]."
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        claim_fixtures.make_settings(
            SOURCE_GROUNDING_ENABLED=True,
            SOURCE_PACK_PREFLIGHT_ENABLED=False,
            GROUNDING_GATE_ENABLED=True,
            GROUNDING_REQUIRE_EVIDENCE=True,
            CLAIM_VERIFICATION_BLOCKING=True,
            CLAIM_VERIFICATION_MAX_CHECKS=budget,
            UNLIMITED_GENERATION_USER_IDS=[],
        ),
    )
    with ExitStack() as stack:
        mocks = claim_fixtures.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            claim_llm_response=claim_fixtures.llm_verdicts(("supported", "Supported.")),
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(return_value=pack),
            )
        )
        response = {
            **mocks["generate_section"].return_value,
            "content": content,
            "content_with_markers": content,
            "pack_keys_used": ["Vaswani2017"],
            "cited_sources": [source],
        }
        mocks["generate_section"].return_value = response
        assert not evaluate_grounding(response, pack).passed
        if completes:
            await BackgroundJobService.generate_full_document(
                document_id=document.id, user_id=user.id
            )
            assert mocks["export_document"].await_count == 1
            assert mocks["ai_service"].call_with_fallback.await_count == 1
        else:
            with pytest.raises(CitationIntegrityError):
                await BackgroundJobService.generate_full_document(
                    document_id=document.id, user_id=user.id
                )
            assert mocks["export_document"].await_count == 0
            assert mocks["ai_service"].call_with_fallback.await_count == 0
