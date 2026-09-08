"""Control 9 class: the reconciled plan must come back whole, or stop truthfully.

Live failure 2026-09-08 (document 9 / job 9): plan preparation asked for the
complete outline with the generic 4000-token cap, the answer stopped at
max_tokens, the SDK-level enlarge-and-reissue recovery was disabled by
max_retries=0, and the wrapped IncompleteModelResponse became
``unknown_failure`` with only "new_version" offered. No reviewer had rejected
anything. These tests drive the real AIService/RetryStrategy/ModelResponseRecovery
stack with SDK-shaped answers; only the transport is synthetic.
"""

import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AllProvidersFailedError
from app.models.document import DocumentProvenance
from app.services import plan_preparation
from app.services.academic_review import outline_problems
from app.services.cost_estimator import UsageTracker
from app.services.generation_operations import journal_usage
from app.services.generation_outcomes import (
    TEMPORARY_REASONS,
    GenerationStageError,
    failure_reason,
)
from app.services.model_response_recovery import (
    IncompleteModelResponse,
    ModelResponseRecovery,
    model_output_ceiling,
)
from app.services.plan_preparation import (
    PLAN_OUTPUT_FLOOR,
    plan_output_budget,
    preparation_wait_seconds,
    prepare_final_plan,
)
from tests.test_academic_quality import seed_review

MODEL = "claude-opus-4-8"
CEILING = model_output_ceiling(MODEL)


def _answer(text: str, *, stop_reason: str = "end_turn", out: int = 1200, rid="msg"):
    return SimpleNamespace(
        id=rid,
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)] if text else [],
        usage=SimpleNamespace(input_tokens=32846, output_tokens=out),
    )


async def _pruned_work(db):
    """Provisional plan with one pruned key: reconciliation must call the model."""
    doc, job, pack = await seed_review(db)
    valid = copy.deepcopy(doc.outline)
    doc.outline = copy.deepcopy(doc.outline)
    doc.outline["sections"][0]["evidence_keys"] = ["Pruned2020"]
    await db.commit()
    return doc, job, pack, valid


def _stack(monkeypatch, answers):
    """Real AIService on a synthetic Anthropic transport; records SDK kwargs."""
    sdk = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(side_effect=answers)),
        close=AsyncMock(),
    )
    monkeypatch.setattr("anthropic.AsyncAnthropic", MagicMock(return_value=sdk))
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "fixture-never-sent")
    monkeypatch.setattr(settings, "AI_FALLBACK_CHAIN", f"anthropic:{MODEL}")
    constructed = []
    real_service = plan_preparation.AIService

    def factory(db, **kwargs):
        service = real_service(db, **kwargs)
        service._anthropic_retry.delays = [0]
        constructed.append(kwargs)
        return service

    monkeypatch.setattr(plan_preparation, "AIService", factory)
    usage = UsageTracker()
    return sdk, constructed, usage


def _bind(usage, doc, job):
    usage.generation_context = {
        "document_id": doc.id,
        "job_id": job.id,
        "worker_attempt": 0,
    }


async def _events(db, event_type):
    return list(
        (
            await db.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.event_type == event_type)
                .order_by(DocumentProvenance.id)
            )
        ).scalars()
    )


@pytest.mark.asyncio
async def test_truncated_plan_is_reissued_once_with_room_and_completes(
    db_session, monkeypatch
):
    doc, job, pack, valid = await _pruned_work(db_session)
    complete = json.dumps(valid, ensure_ascii=False)
    sdk, constructed, usage = _stack(
        monkeypatch,
        [
            _answer(complete[:300], stop_reason="max_tokens", out=8000, rid="cut"),
            _answer(complete, out=5200, rid="whole"),
        ],
    )
    _bind(usage, doc, job)
    before = (pack.sha256(), [s["title"] for s in doc.outline["sections"]])

    result = await prepare_final_plan(db_session, doc, job, pack, usage_tracker=usage)

    assert result["status"] == "completed" and result["model_called"]
    assert constructed == [{"usage_tracker": usage, "max_retries": 1}]
    calls = [c.kwargs for c in sdk.messages.create.call_args_list]
    assert len(calls) == 2
    # Same task, same pinned model, no hidden fallback; only the room grows.
    assert {c["model"] for c in calls} == {MODEL}
    assert [c["max_tokens"] for c in calls] == [PLAN_OUTPUT_FLOOR, CEILING]
    assert calls[0]["messages"] == calls[1]["messages"]
    # The outer wait covers both bounded requests' own SDK timeouts.
    assert sum(c["timeout"] for c in calls) <= preparation_wait_seconds(
        PLAN_OUTPUT_FLOOR, CEILING
    )
    # Frozen pack and structure untouched; the plan itself is now reconciled.
    assert (pack.sha256(), [s["title"] for s in doc.outline["sections"]]) == before
    assert outline_problems(doc.outline, set(pack.keys())) == []
    # One content reconciliation: one started event, one completed event.
    started = await _events(db_session, "academic_plan_preparation_started")
    finished = await _events(db_session, "academic_plan_preparation")
    assert (
        len(started) == 1 and started[0].payload["output_budget"] == PLAN_OUTPUT_FLOOR
    )
    assert [e.payload["status"] for e in finished] == ["completed"]
    # Every SDK call has a receipt; confirmed usage equals the tracker and journal.
    receipts = await _events(db_session, "generation_provider_attempt")
    assert [r.payload["outcome"] for r in receipts] == [
        "started",
        "received",
        "started",
        "received",
    ]
    assert {r.payload["stage"] for r in receipts} == {"academic_plan_preparation"}
    confirmed, unknown = await journal_usage(db_session, doc.id, job.id)
    assert unknown == 0
    assert confirmed.total_tokens == usage.total_tokens == 2 * 32846 + 8000 + 5200


@pytest.mark.asyncio
async def test_plan_truncated_at_the_ceiling_is_technical_not_academic(
    db_session, monkeypatch
):
    doc, job, pack, valid = await _pruned_work(db_session)
    partial = json.dumps(valid, ensure_ascii=False)[:300]
    sdk, _, usage = _stack(
        monkeypatch,
        [
            _answer(partial, stop_reason="max_tokens", out=8000),
            _answer(partial, stop_reason="max_tokens", out=16000),
        ],
    )
    _bind(usage, doc, job)
    before = copy.deepcopy(doc.outline)

    with pytest.raises(GenerationStageError) as error:
        await prepare_final_plan(db_session, doc, job, pack, usage_tracker=usage)

    assert error.value.reason_code == "review_input_invalid"
    assert error.value.reason_code not in TEMPORARY_REASONS
    assert sdk.messages.create.await_count == 2
    assert doc.outline == before
    (event,) = await _events(db_session, "academic_plan_preparation")
    assert event.payload["status"] == "unchecked"
    assert event.payload["outcome"] == "unusable"
    assert event.payload["budget_exhausted"] is True
    assert event.payload["reason_code"] not in {
        "plan_requirements_unmet",
        "academic_content_rejected",
        "unknown_failure",
    }
    confirmed, unknown = await journal_usage(db_session, doc.id, job.id)
    assert (confirmed.total_tokens, unknown) == (2 * 32846 + 8000 + 16000, 0)


@pytest.mark.asyncio
async def test_ceiling_sized_plan_is_not_re_requested_with_the_same_cap(
    db_session, monkeypatch
):
    doc, job, pack, valid = await _pruned_work(db_session)
    doc.outline = {**doc.outline, "notes": "x" * CEILING}
    await db_session.commit()
    sdk, _, usage = _stack(
        monkeypatch, [_answer("{", stop_reason="max_tokens", out=CEILING)]
    )
    _bind(usage, doc, job)

    with pytest.raises(GenerationStageError) as error:
        await prepare_final_plan(db_session, doc, job, pack, usage_tracker=usage)

    assert error.value.reason_code == "review_input_invalid"
    assert sdk.messages.create.await_count == 1
    assert sdk.messages.create.call_args.kwargs["max_tokens"] == CEILING


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["empty", "malformed"])
async def test_empty_or_malformed_answer_is_a_bounded_technical_repeat(
    db_session, monkeypatch, fault
):
    doc, job, pack, _ = await _pruned_work(db_session)
    answers = (
        [_answer("", out=0), _answer("", out=0)]
        if fault == "empty"
        else [_answer(json.dumps({"answer": "Ho letto il piano."}), out=40)]
    )
    sdk, _, usage = _stack(monkeypatch, answers)
    _bind(usage, doc, job)
    before = copy.deepcopy(doc.outline)

    with pytest.raises(GenerationStageError) as error:
        await prepare_final_plan(db_session, doc, job, pack, usage_tracker=usage)

    assert error.value.reason_code == "review_temporarily_unavailable"
    assert sdk.messages.create.await_count == len(answers)
    assert doc.outline == before
    (event,) = await _events(db_session, "academic_plan_preparation")
    assert (event.payload["status"], event.payload["outcome"]) == (
        "unchecked",
        "unusable",
    )


@pytest.mark.asyncio
async def test_complete_plan_that_breaks_structure_is_a_quality_stop_without_repeat(
    db_session, monkeypatch
):
    doc, job, pack, valid = await _pruned_work(db_session)
    broken = copy.deepcopy(valid)
    broken["sections"].pop()
    sdk, _, usage = _stack(monkeypatch, [_answer(json.dumps(broken), out=3000)])
    _bind(usage, doc, job)

    with pytest.raises(GenerationStageError) as error:
        await prepare_final_plan(db_session, doc, job, pack, usage_tracker=usage)

    assert error.value.reason_code == "plan_requirements_unmet"
    # A valid but rejected answer is a verdict: no technical repeat is spent on it.
    assert sdk.messages.create.await_count == 1
    (event,) = await _events(db_session, "academic_plan_preparation")
    assert (event.payload["status"], event.payload["outcome"]) == ("failed", "rejected")


def test_control_9_shape_gets_room_above_the_generic_cap():
    outline = {
        "academic_plan": {
            "research_question": "Q " * 120,
            "objectives": ["Obiettivo " * 30 for _ in range(5)],
            "conflicts": ["Vincolo " * 60 for _ in range(3)],
        },
        "sections": [
            {
                "title": f"Capitolo {i}",
                "main_points": ["Punto " * 40 for _ in range(4)],
                "subsections": ["Sotto " * 20 for _ in range(3)],
                "estimated_words": 1050,
                "key_concepts": ["Concetto"] * 5,
                "academic_functions": ["critical_analysis"],
                "evidence_keys": ["Key2023"] * 5,
            }
            for i in range(6)
        ],
    }
    serialized = len(json.dumps(outline, ensure_ascii=False))
    assert 8500 <= serialized <= 14000  # same order as the live six-section plan
    budget = plan_output_budget(outline, MODEL)
    assert budget == serialized > PLAN_OUTPUT_FLOOR > 4000
    # Legacy ceiling models cannot exceed their own limit.
    assert plan_output_budget(outline, "claude-3-opus-20240229") == 4000
    wait = preparation_wait_seconds(budget, CEILING)
    first = ModelResponseRecovery(budget, CEILING).timeout_seconds
    assert wait >= first + ModelResponseRecovery(CEILING, CEILING).timeout_seconds
    assert first > 90  # the previous fixed outer wait would have cut a valid answer


def test_failure_reason_never_turns_an_incomplete_answer_into_a_verdict():
    exhausted = IncompleteModelResponse("cut", budget_exhausted=True)
    wrapped = AllProvidersFailedError("All AI providers failed")
    wrapped.__cause__ = exhausted
    assert failure_reason(wrapped, stage="review") == "review_input_invalid"
    assert failure_reason(exhausted, stage="generation") == "unknown_failure"
    assert (
        failure_reason(IncompleteModelResponse("empty"), stage="review")
        == "review_temporarily_unavailable"
    )
    recovery = ModelResponseRecovery(8000, 16000)
    with pytest.raises(IncompleteModelResponse) as first:
        recovery.validate("partial", "max_tokens")
    assert first.value.budget_exhausted is False and recovery.max_tokens == 16000
    with pytest.raises(IncompleteModelResponse) as second:
        recovery.validate("partial", "max_tokens")
    assert second.value.budget_exhausted is True
