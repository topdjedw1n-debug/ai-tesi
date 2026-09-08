"""S1: final-evidence reconciliation, truthful failures and bounded reuse."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIStatusError
from sqlalchemy import delete, select

from app.models.document import DocumentProvenance
from app.services.academic_context import digest
from app.services.academic_review import run_academic_review
from app.services.generation_outcomes import GenerationStageError, failure_reason
from app.services.generation_profile import generation_profile_sha256
from app.services.plan_preparation import prepare_final_plan
from tests.test_academic_quality import seed_review, verdict


@pytest.mark.asyncio
async def test_pruned_keys_and_permissible_limit_are_reconciled_once(db_session):
    doc, job, pack = await seed_review(db_session)
    valid = copy.deepcopy(doc.outline)
    original_titles = [s["title"] for s in doc.outline["sections"]]
    doc.outline = copy.deepcopy(doc.outline)
    doc.outline["sections"][0]["evidence_keys"] = ["Pruned2020"]
    doc.outline["academic_plan"]["conflicts"] = ["Narrative review, no PRISMA search"]
    valid["academic_plan"]["limitations"] = ["Narrative review, no PRISMA search"]
    valid["academic_plan"]["blocking_conflicts"] = []
    await db_session.commit()
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=valid))
    before_pack = pack.sha256()
    result = await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)
    assert result["status"] == "completed" and result["model_called"]
    assert [s["title"] for s in doc.outline["sections"]] == original_titles
    assert pack.sha256() == before_pack
    again = await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)
    assert again == result and ai.call_with_fallback.await_count == 1
    assert doc.outline["academic_plan"]["limitations"]
    reviewer = SimpleNamespace(call_with_fallback=AsyncMock(return_value=verdict(True)))
    reviewed = await run_academic_review(
        db_session, doc, job, pack, kind="outline", ai_service=reviewer
    )
    # The preparation event never grants the semantic PASS by itself.
    assert reviewer.call_with_fallback.await_count == 1
    assert reviewed["binding"]["outline_sha256"] == digest(doc.outline)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["chapter", "count", "gap", "foreign_key"])
async def test_reconciliation_cannot_erase_real_requirements_or_change_structure(
    db_session, mutation
):
    doc, job, pack = await seed_review(db_session)
    original = copy.deepcopy(doc.outline)
    doc.outline = copy.deepcopy(original)
    doc.outline["sections"][0]["evidence_keys"] = ["Pruned2020"]
    result = copy.deepcopy(original)
    if mutation == "chapter":
        result["sections"][0]["title"] = "Different chapter"
    elif mutation == "count":
        result["sections"].pop()
    elif mutation == "gap":
        result["academic_plan"]["blocking_conflicts"] = [
            "The required clinical population has no readable evidence"
        ]
    else:
        result["sections"][0]["evidence_keys"] = ["ForeignDOI2025"]
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=result))
    before = digest(doc.outline)
    for _ in range(2):
        with pytest.raises(GenerationStageError) as exc:
            await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)
        assert exc.value.reason_code == "plan_requirements_unmet"
    assert digest(doc.outline) == before
    assert ai.call_with_fallback.await_count == 1


@pytest.mark.asyncio
async def test_missing_trace_is_integrity_failure_with_no_model(db_session):
    doc, job, pack = await seed_review(db_session)
    await db_session.execute(delete(DocumentProvenance))
    await db_session.commit()
    ai = SimpleNamespace(call_with_fallback=AsyncMock())
    with pytest.raises(GenerationStageError) as exc:
        await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)
    assert exc.value.reason_code == "checkpoint_integrity_error"
    result = await run_academic_review(
        db_session, doc, job, pack, kind="outline", ai_service=ai
    )
    assert (
        result["status"] == "unchecked"
        and result["reason_code"] == "checkpoint_integrity_error"
    )
    ai.call_with_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_reviewer_timeout_then_new_worker_attempt_reuses_identical_inputs(
    db_session,
):
    doc, job, pack = await seed_review(db_session)
    job.attempt_count = 1
    ai = SimpleNamespace(
        call_with_fallback=AsyncMock(side_effect=[TimeoutError(), verdict(True)])
    )
    original = (digest(doc.outline), pack.sha256(), doc.content)
    first = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    assert first["status"] == "unchecked"
    assert first["reason_code"] == "review_temporarily_unavailable"
    assert (
        await run_academic_review(
            db_session, doc, job, pack, kind="whole", ai_service=ai
        )
        == first
    )
    job.attempt_count = 2
    second = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    assert second["status"] == "passed" and ai.call_with_fallback.await_count == 2
    assert original == (digest(doc.outline), pack.sha256(), doc.content)
    events = list(
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "academic_review_started"
                )
            )
        ).scalars()
    )
    assert len(events) == 2 and events[0].payload["outcome"] == "outcome_unknown"


@pytest.mark.asyncio
async def test_oversized_review_is_non_retryable(db_session, monkeypatch):
    doc, job, pack = await seed_review(db_session)
    monkeypatch.setattr("app.services.academic_review.REVIEW_MAX_CHARS", 10)
    ai = SimpleNamespace(call_with_fallback=AsyncMock())
    first = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    job.attempt_count = 3
    assert (
        await run_academic_review(
            db_session, doc, job, pack, kind="whole", ai_service=ai
        )
        == first
    )
    assert first["reason_code"] == "review_input_invalid"
    ai.call_with_fallback.assert_not_called()


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (429, {}, "review_temporarily_unavailable"),
        (503, {}, "review_temporarily_unavailable"),
        (401, {}, "provider_access_required"),
        (429, {"error": {"code": "insufficient_quota"}}, "provider_access_required"),
        (
            400,
            {"error": {"message": "Your credit balance is too low"}},
            "provider_access_required",
        ),
        (400, {}, "review_input_invalid"),
    ],
)
def test_typed_provider_reasons_survive_wrapping(status, body, expected):
    response = httpx.Response(
        status, request=httpx.Request("POST", "https://fixture.invalid")
    )
    error = APIStatusError("provider failure", response=response, body=body)
    wrapped = RuntimeError("wrapper without message matching")
    wrapped.__cause__ = error
    assert failure_reason(wrapped, stage="review") == expected


def test_transport_timeout_is_temporary_and_unknown_is_not_guessed():
    assert (
        failure_reason(TimeoutError(), stage="review")
        == "review_temporarily_unavailable"
    )
    assert failure_reason(RuntimeError("timeout 429 balance")) == "unknown_failure"


def test_profile_changes_with_writer_policy_and_internal_claim_rights(monkeypatch):
    from app.services.generation_profile import settings
    from tests.test_academic_quality import example

    doc, _, _ = example()
    first = generation_profile_sha256(doc)
    doc.ai_model = "different"
    assert generation_profile_sha256(doc) != first
    doc.ai_model = "unchanged-writer"
    monkeypatch.setattr(settings, "UNLIMITED_GENERATION_USER_IDS", [1])
    assert generation_profile_sha256(doc) != first


@pytest.mark.parametrize(
    "setting,value",
    [
        ("SOURCE_PACK_MIN_VERIFIED", 19),
        ("CLAIM_VERIFICATION_MAX_CHECKS", 101),
        ("QUALITY_JUDGE_MODEL", "different-reviewer"),
        ("HUMANIZER_MODEL", "different-humanizer"),
        ("AI_MAX_RETRIES", 4),
        ("AI_FALLBACK_CHAIN", "openai:other"),
    ],
)
def test_profile_changes_for_each_execution_policy_group(monkeypatch, setting, value):
    from app.services.generation_profile import settings
    from tests.test_academic_quality import example

    doc, _, _ = example()
    before = generation_profile_sha256(doc)
    monkeypatch.setattr(settings, setting, value)
    assert generation_profile_sha256(doc) != before


def test_profile_excludes_provider_secrets(monkeypatch):
    from app.services.generation_profile import settings
    from tests.test_academic_quality import example

    doc, _, _ = example()
    before = generation_profile_sha256(doc)
    monkeypatch.setattr(
        settings, "OPENAI_API_KEY", "changed-secret-must-not-affect-resume"
    )
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "another-key")
    assert generation_profile_sha256(doc) == before
