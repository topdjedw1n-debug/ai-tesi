"""
Unit and pipeline tests for the reviewer panel in quality_validator.py.

Panel: 3 LLM reviewers (methodology 0.4, citations 0.3, coherence 0.3)
+ devil's advocate whose CRITICAL finding fails the gate regardless of the
weighted average. Panel of >= QUALITY_PANEL_MIN_REVIEWERS is valid; below
that the heuristic fallback is used.
"""

import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

# Imported at module level so Base.metadata knows every model before the
# db_session fixture runs create_all (late imports would leave it empty)
import tests.test_citation_pipeline_integration as harness_mod
from app.core.config import Settings
from app.models.document import Document, DocumentSection
from app.services.background_jobs import BackgroundJobService
from app.services.quality_validator import (
    PANEL_REVIEWERS,
    QualityValidator,
    _extract_json_object,
    _normalize_remarks,
)

CONTENT = (
    "However, transformer architectures changed the field [Vaswani, 2017]. "
    "Therefore, this section reviews their impact in detail. " * 20
)
OUTLINE = {"title": "Background", "target_word_count": 200}


def reviewer_json(score, remarks=None):
    return {
        "score": score,
        "remarks": (
            remarks
            if remarks is not None
            else [
                {"severity": "minor", "text": "Could cite more recent work."},
                {"severity": "major", "text": "Methodology subsection is thin."},
            ]
        ),
    }


def advocate_json(severity="minor", weakness="Slightly repetitive opening."):
    return {"severity": severity, "weakness": weakness}


def make_ai_service(responses_by_purpose):
    """Mock AIService dispatching call_with_fallback by purpose"""
    service = MagicMock()

    async def dispatch(prompt, purpose="ai_call"):
        value = responses_by_purpose[purpose]
        if isinstance(value, Exception):
            raise value
        return value

    service.call_with_fallback = AsyncMock(side_effect=dispatch)
    return service


def panel_settings(monkeypatch, **overrides):
    defaults = {"QUALITY_PANEL_ENABLED": True}
    defaults.update(overrides)
    test_settings = Settings(**defaults)
    monkeypatch.setattr("app.services.quality_validator.settings", test_settings)
    return test_settings


def standard_responses(methodology=80, citations=60, coherence=90, advocate=None):
    return {
        "quality_panel_methodology": reviewer_json(methodology),
        "quality_panel_citations": reviewer_json(citations),
        "quality_panel_coherence": reviewer_json(coherence),
        "quality_panel_devils_advocate": advocate or advocate_json(),
    }


# ----------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregation_weighted_average(monkeypatch):
    panel_settings(monkeypatch)
    validator = QualityValidator(
        ai_service=make_ai_service(standard_responses(80, 60, 90))
    )

    result = await validator.validate_section(CONTENT, OUTLINE)

    # 80*0.4 + 60*0.3 + 90*0.3 = 77.0
    assert result["overall_score"] == 77.0
    assert result["passed"] is True
    assert result["critical_override"] is False
    assert set(result["checks"].keys()) == {
        "methodology",
        "citations",
        "coherence",
    }
    assert result["panel"]["valid"] is True
    assert len(result["panel"]["reviewers"]) == len(PANEL_REVIEWERS)


@pytest.mark.asyncio
async def test_aggregation_below_threshold_fails_gate(monkeypatch):
    panel_settings(monkeypatch)
    validator = QualityValidator(
        ai_service=make_ai_service(standard_responses(50, 40, 60))
    )

    result = await validator.validate_section(CONTENT, OUTLINE)

    # 50*0.4 + 40*0.3 + 60*0.3 = 50.0 < 70
    assert result["overall_score"] == 50.0
    assert result["passed"] is False
    assert result["critical_override"] is False


# ----------------------------------------------------------------------
# CRITICAL override (devil's advocate)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_critical_override_fails_gate_despite_high_average(monkeypatch):
    panel_settings(monkeypatch)
    validator = QualityValidator(
        ai_service=make_ai_service(
            standard_responses(
                95,
                90,
                92,
                advocate=advocate_json(
                    "critical", "Core claim contradicts the cited source."
                ),
            )
        )
    )

    result = await validator.validate_section(CONTENT, OUTLINE)

    assert result["overall_score"] > 90  # average is excellent...
    assert result["critical_override"] is True
    assert result["passed"] is False  # ...but CRITICAL fails the gate anyway
    assert result["panel"]["advocate"]["severity"] == "critical"
    assert any("devils_advocate" in issue for issue in result["issues"])
    assert any("Weakest spot" in item for item in result["feedback_for_regeneration"])


@pytest.mark.asyncio
async def test_non_critical_advocate_does_not_override(monkeypatch):
    panel_settings(monkeypatch)
    validator = QualityValidator(
        ai_service=make_ai_service(
            standard_responses(
                95, 90, 92, advocate=advocate_json("major", "Weak conclusion.")
            )
        )
    )

    result = await validator.validate_section(CONTENT, OUTLINE)

    assert result["critical_override"] is False
    assert result["passed"] is True


# ----------------------------------------------------------------------
# Remark format
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remark_format_normalized(monkeypatch):
    panel_settings(monkeypatch)
    messy_remarks = [
        {"severity": "CATASTROPHIC", "text": "Unknown severity normalizes."},
        "Bare string remark becomes minor.",
        {"severity": "major", "text": "X" * 1000},  # truncated to 300
        {"severity": "minor", "text": ""},  # dropped (empty)
        {"severity": "minor", "text": "Fourth remark beyond the cap."},
    ]
    responses = standard_responses()
    responses["quality_panel_methodology"] = reviewer_json(80, messy_remarks)
    validator = QualityValidator(ai_service=make_ai_service(responses))

    result = await validator.validate_section(CONTENT, OUTLINE)

    methodology = next(
        r for r in result["panel"]["reviewers"] if r["key"] == "methodology"
    )
    remarks = methodology["remarks"]
    assert len(remarks) == 3  # max 3, empty dropped
    assert all(r["severity"] in {"minor", "major", "critical"} for r in remarks)
    assert all(0 < len(r["text"]) <= 300 for r in remarks)
    assert remarks[0]["severity"] == "minor"  # unknown severity -> minor
    assert remarks[1]["text"] == "Bare string remark becomes minor."


def test_normalize_remarks_unit():
    assert _normalize_remarks(None) == []
    assert _normalize_remarks("garbage") == []
    normalized = _normalize_remarks([{"severity": "critical", "text": " trim me "}])
    assert normalized == [{"severity": "critical", "text": "trim me"}]


# ----------------------------------------------------------------------
# Fallbacks
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_reviewer_down_panel_of_two_valid(monkeypatch):
    """Reviewer failure renormalizes weights over the remaining two"""
    panel_settings(monkeypatch)
    responses = standard_responses(80, 60, 90)
    responses["quality_panel_citations"] = RuntimeError("provider down")
    validator = QualityValidator(ai_service=make_ai_service(responses))

    result = await validator.validate_section(CONTENT, OUTLINE)

    # (80*0.4 + 90*0.3) / 0.7 = 84.3
    assert result["overall_score"] == 84.3
    assert result["passed"] is True
    assert result["panel"]["valid"] is True
    citations_entry = next(
        r for r in result["panel"]["reviewers"] if r["key"] == "citations"
    )
    assert citations_entry["ok"] is False
    assert "citations" not in result["checks"]


@pytest.mark.asyncio
async def test_two_reviewers_down_falls_back_to_heuristic(monkeypatch):
    panel_settings(monkeypatch)
    responses = standard_responses()
    responses["quality_panel_methodology"] = RuntimeError("down")
    responses["quality_panel_citations"] = {"content": "no json here"}
    validator = QualityValidator(ai_service=make_ai_service(responses))

    heuristic_expected = await QualityValidator()._validate_heuristic(CONTENT, OUTLINE)
    result = await validator.validate_section(CONTENT, OUTLINE)

    assert result["panel"]["valid"] is False
    assert result["panel"]["reason"] == "insufficient_reviewers"
    assert result["overall_score"] == heuristic_expected["overall_score"]
    assert result["critical_override"] is False
    assert "citation_density" in result["checks"]  # heuristic shape


@pytest.mark.asyncio
async def test_advocate_down_no_override_panel_still_valid(monkeypatch):
    panel_settings(monkeypatch)
    responses = standard_responses(80, 60, 90)
    responses["quality_panel_devils_advocate"] = RuntimeError("down")
    validator = QualityValidator(ai_service=make_ai_service(responses))

    result = await validator.validate_section(CONTENT, OUTLINE)

    assert result["overall_score"] == 77.0
    assert result["passed"] is True
    assert result["critical_override"] is False
    assert result["panel"]["advocate"] == {"ok": False}


@pytest.mark.asyncio
async def test_flag_off_uses_heuristic_no_llm_calls(monkeypatch):
    panel_settings(monkeypatch, QUALITY_PANEL_ENABLED=False)
    ai_service = make_ai_service({})
    validator = QualityValidator(ai_service=ai_service)

    result = await validator.validate_section(CONTENT, OUTLINE)

    ai_service.call_with_fallback.assert_not_called()
    assert "panel" not in result  # legacy shape untouched
    assert "citation_density" in result["checks"]


@pytest.mark.asyncio
async def test_no_ai_service_uses_heuristic_even_with_flag(monkeypatch):
    panel_settings(monkeypatch, QUALITY_PANEL_ENABLED=True)
    validator = QualityValidator()  # legacy construction

    result = await validator.validate_section(CONTENT, OUTLINE)

    assert "panel" not in result
    assert "citation_density" in result["checks"]


# ----------------------------------------------------------------------
# JSON extraction from raw LLM text
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reviewer_json_inside_raw_content(monkeypatch):
    """{"content": "<text with JSON>"} responses are parsed too"""
    panel_settings(monkeypatch)
    responses = standard_responses(80, 60, 90)
    responses["quality_panel_methodology"] = {
        "content": "Here is my review:\n"
        + json.dumps(reviewer_json(80))
        + "\nHope this helps!",
        "tokens_used": 100,
    }
    validator = QualityValidator(ai_service=make_ai_service(responses))

    result = await validator.validate_section(CONTENT, OUTLINE)

    assert result["overall_score"] == 77.0
    assert result["panel"]["valid"] is True


def test_extract_json_object_unit():
    assert _extract_json_object({"score": 80}) == {"score": 80}
    assert _extract_json_object({"content": 'x {"a": 1} y'}) == {"a": 1}
    assert _extract_json_object({"content": "no json"}) is None
    assert _extract_json_object("not a dict") is None


def test_extract_json_object_chatty_responses():
    """Braces in surrounding prose must not break extraction (greedy-regex bug)"""
    # Trailing prose containing another brace pair
    chatty = '{"score": 80, "remarks": []}\n\nNote: I treated {placeholders} as fine.'
    assert _extract_json_object({"content": chatty}) == {"score": 80, "remarks": []}
    # Prose with a stray opening brace BEFORE the real object
    prefixed = 'I rate this {well, mostly} as follows: {"score": 65, "remarks": []}'
    assert _extract_json_object({"content": prefixed}) == {
        "score": 65,
        "remarks": [],
    }
    # Two JSON objects: the first valid one wins
    double = '{"score": 70, "remarks": []} and also {"score": 10, "remarks": []}'
    assert _extract_json_object({"content": double}) == {"score": 70, "remarks": []}


# Heuristically terrible content: no citations, no transitions, 2 words vs
# target 500 -> legacy heuristic scores far below 70
BAD_CONTENT = "Bad text."


@pytest.mark.asyncio
async def test_quorum_fallback_is_advisory_never_blocks(monkeypatch):
    """Panel outage + low heuristic score must NOT block generation"""
    panel_settings(monkeypatch)
    responses = standard_responses()
    responses["quality_panel_methodology"] = RuntimeError("down")
    responses["quality_panel_citations"] = RuntimeError("down")
    validator = QualityValidator(ai_service=make_ai_service(responses))

    result = await validator.validate_section(BAD_CONTENT, OUTLINE)

    assert result["panel"]["valid"] is False
    assert result["overall_score"] < 70  # heuristic genuinely failed it...
    assert result["passed"] is True  # ...but outage fallback is advisory


@pytest.mark.asyncio
async def test_quorum_fallback_still_honors_successful_critical_advocate(
    monkeypatch,
):
    """Advocate had no outage - its CRITICAL finding survives the fallback"""
    panel_settings(monkeypatch)
    responses = standard_responses(
        advocate=advocate_json("critical", "Fabricated citation in paragraph 2.")
    )
    responses["quality_panel_methodology"] = RuntimeError("down")
    responses["quality_panel_citations"] = RuntimeError("down")
    validator = QualityValidator(ai_service=make_ai_service(responses))

    result = await validator.validate_section(CONTENT, OUTLINE)

    assert result["panel"]["valid"] is False
    assert result["critical_override"] is True
    assert result["passed"] is False
    assert any("Fabricated citation" in i for i in result["issues"])
    assert any("Fabricated citation" in f for f in result["feedback_for_regeneration"])


# ----------------------------------------------------------------------
# Pipeline wiring (gate 4 + regeneration feedback)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_panel_feedback_reaches_regeneration_prompt(
    db_session, monkeypatch
):
    """Panel gate fails attempt 1 -> attempt 2 prompt carries the remarks"""
    pipeline_settings = Settings(
        QUALITY_GATES_ENABLED=True,
        QUALITY_MAX_REGENERATE_ATTEMPTS=1,
        QUALITY_PANEL_ENABLED=True,
        CITATION_VERIFICATION_ENABLED=False,
        CLAIM_VERIFICATION_ENABLED=False,
    )
    monkeypatch.setattr("app.services.background_jobs.settings", pipeline_settings)

    user, document = await harness_mod.seed_document(
        db_session, section_titles=("Only",)
    )
    document_id = document.id

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    failed_panel = {
        "passed": False,
        "overall_score": 40.0,
        "checks": {},
        "issues": ["[methodology/major] Too shallow."],
        "panel": {"valid": True, "critical_override": False},
        "critical_override": False,
        "feedback_for_regeneration": [
            "Methodology & Structure: Too shallow, expand the argument."
        ],
    }
    passed_panel = {
        "passed": True,
        "overall_score": 88.0,
        "checks": {},
        "issues": [],
        "panel": {"valid": True, "critical_override": False},
        "critical_override": False,
        "feedback_for_regeneration": [],
    }

    legacy_result = {
        "section_title": "Only",
        "section_index": 1,
        "content": "Generated content",
        "citations": [],
        "bibliography": [],
        "sources_used": 0,
        "humanized": False,
    }

    with ExitStack() as stack:
        mocks = harness_mod.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[dict(legacy_result), dict(legacy_result)],
        )
        panel_mock = stack.enter_context(
            patch(
                "app.services.background_jobs._check_panel_quality",
                AsyncMock(side_effect=[failed_panel, passed_panel]),
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

        # Attempt 2's generate_section received the reviewer feedback
        assert mocks["generate_section"].call_count == 2
        second_call_requirements = (
            mocks["generate_section"]
            .call_args_list[1]
            .kwargs["additional_requirements"]
        )
        assert "reviewer feedback" in second_call_requirements
        assert "Too shallow" in second_call_requirements
        # Attempt 1 had no feedback yet
        first_call_requirements = (
            mocks["generate_section"]
            .call_args_list[0]
            .kwargs["additional_requirements"]
        )
        assert first_call_requirements is None
        assert panel_mock.call_count == 2

    refreshed = (
        await db_session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one()
    assert refreshed.status == "completed"

    section = (
        await db_session.execute(
            select(DocumentSection).where(DocumentSection.document_id == document_id)
        )
    ).scalar_one()
    # Aggregate keeps feeding the legacy field; panel details in JSONB
    assert section.quality_score == 88.0
    assert section.quality_panel == {"valid": True, "critical_override": False}


@pytest.mark.asyncio
async def test_pipeline_panel_skipped_on_doomed_attempts_and_stale_feedback_dropped(
    db_session, monkeypatch
):
    """Gates 1-3 failure skips the panel; older panel feedback is dropped"""
    pipeline_settings = Settings(
        QUALITY_GATES_ENABLED=True,
        QUALITY_MAX_REGENERATE_ATTEMPTS=2,
        QUALITY_PANEL_ENABLED=True,
        CITATION_VERIFICATION_ENABLED=False,
        CLAIM_VERIFICATION_ENABLED=False,
    )
    monkeypatch.setattr("app.services.background_jobs.settings", pipeline_settings)

    user, document = await harness_mod.seed_document(
        db_session, section_titles=("Only",)
    )
    document_id = document.id

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    failed_panel = {
        "passed": False,
        "overall_score": 40.0,
        "checks": {},
        "issues": [],
        "panel": {"valid": True, "critical_override": False},
        "critical_override": False,
        "feedback_for_regeneration": ["Methodology & Structure: Too shallow."],
    }
    passed_panel = {
        "passed": True,
        "overall_score": 88.0,
        "checks": {},
        "issues": [],
        "panel": {"valid": True, "critical_override": False},
        "critical_override": False,
        "feedback_for_regeneration": [],
    }

    legacy_result = {
        "section_title": "Only",
        "section_index": 1,
        "content": "Generated content",
        "citations": [],
        "bibliography": [],
        "sources_used": 0,
        "humanized": False,
    }

    with ExitStack() as stack:
        mocks = harness_mod.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[dict(legacy_result) for _ in range(3)],
            # Attempt 1: grammar OK; attempt 2: grammar FAILS (panel must be
            # skipped); attempt 3: grammar OK again
            grammar_side_effect=[
                (95.0, 0, "passed", None),
                (40.0, 25, "failed", "Too many grammar errors"),
                (95.0, 0, "passed", None),
            ],
        )
        panel_mock = stack.enter_context(
            patch(
                "app.services.background_jobs._check_panel_quality",
                AsyncMock(side_effect=[failed_panel, passed_panel]),
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

        # Panel ran only on attempts 1 and 3 (attempt 2 was doomed by grammar)
        assert panel_mock.call_count == 2
        assert mocks["generate_section"].call_count == 3

        calls = mocks["generate_section"].call_args_list
        # Attempt 2 got attempt 1's panel feedback
        assert "Too shallow" in calls[1].kwargs["additional_requirements"]
        # Attempt 3: panel didn't flag attempt 2 (it was skipped) -> stale
        # attempt-1 feedback must be DROPPED, prompt back to the original
        assert calls[2].kwargs["additional_requirements"] is None


@pytest.mark.asyncio
async def test_pipeline_panel_crash_falls_back_to_real_heuristic(
    db_session, monkeypatch
):
    """Panel crash (None) -> post-loop heuristic scores; no fabricated 75.0"""
    pipeline_settings = Settings(
        QUALITY_GATES_ENABLED=True,
        QUALITY_MAX_REGENERATE_ATTEMPTS=0,
        QUALITY_PANEL_ENABLED=True,
        CITATION_VERIFICATION_ENABLED=False,
        CLAIM_VERIFICATION_ENABLED=False,
    )
    monkeypatch.setattr("app.services.background_jobs.settings", pipeline_settings)

    user, document = await harness_mod.seed_document(
        db_session, section_titles=("Only",)
    )
    document_id = document.id

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    legacy_result = {
        "section_title": "Only",
        "section_index": 1,
        "content": "Generated content",
        "citations": [],
        "bibliography": [],
        "sources_used": 0,
        "humanized": False,
    }

    with ExitStack() as stack:
        harness_mod.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[dict(legacy_result)],
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._check_panel_quality",
                AsyncMock(return_value=None),  # panel crashed
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

    section = (
        await db_session.execute(
            select(DocumentSection).where(DocumentSection.document_id == document_id)
        )
    ).scalar_one()
    assert section.status == "completed"  # crash never blocks
    assert section.quality_panel is None  # no panel report persisted
    assert section.quality_score is not None  # real heuristic score
    assert section.quality_score != 75.0  # not the old fabricated neutral


@pytest.mark.asyncio
async def test_pipeline_flag_off_no_panel_calls(db_session, monkeypatch):
    """Panel disabled: heuristic path, zero panel invocations"""
    pipeline_settings = Settings(
        QUALITY_GATES_ENABLED=False,
        QUALITY_MAX_REGENERATE_ATTEMPTS=0,
        QUALITY_PANEL_ENABLED=False,
        CITATION_VERIFICATION_ENABLED=False,
        CLAIM_VERIFICATION_ENABLED=False,
    )
    monkeypatch.setattr("app.services.background_jobs.settings", pipeline_settings)

    user, document = await harness_mod.seed_document(
        db_session, section_titles=("Only",)
    )
    document_id = document.id

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    legacy_result = {
        "section_title": "Only",
        "section_index": 1,
        "content": "Generated content",
        "citations": [],
        "bibliography": [],
        "sources_used": 0,
        "humanized": False,
    }

    with ExitStack() as stack:
        harness_mod.pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[dict(legacy_result)],
        )
        panel_mock = stack.enter_context(
            patch(
                "app.services.background_jobs._check_panel_quality",
                AsyncMock(),
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

        panel_mock.assert_not_called()

    section = (
        await db_session.execute(
            select(DocumentSection).where(DocumentSection.document_id == document_id)
        )
    ).scalar_one()
    assert section.quality_panel is None
    assert section.quality_score is not None  # heuristic still scored
