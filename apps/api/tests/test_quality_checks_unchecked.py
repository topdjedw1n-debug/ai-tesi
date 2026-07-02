"""
Stage B (fail-open -> fail-visible): every quality check must return
status="unchecked" — never "passed" — when its provider is disabled,
unconfigured, or throws. Unchecked is non-blocking for generation but is
recorded honestly in the provenance ledger (covered by the pipeline test
in test_provenance_ledger.py).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.background_jobs import (
    CheckStatus,
    _check_ai_detection_quality,
    _check_grammar_quality,
    _check_plagiarism_quality,
)


@pytest.mark.asyncio
async def test_grammar_unchecked_when_provider_disabled():
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            return_value={"checked": False, "error": "LanguageTool is disabled"}
        )
        score, errors, status, reason = await _check_grammar_quality(
            "Some content", "en", 10
        )

    assert status == CheckStatus.UNCHECKED
    assert status != CheckStatus.PASSED
    assert score is None
    assert errors == 0
    assert "LanguageTool is disabled" in reason


@pytest.mark.asyncio
async def test_grammar_unchecked_when_provider_throws():
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )
        score, errors, status, reason = await _check_grammar_quality(
            "Some content", "en", 10
        )

    assert status == CheckStatus.UNCHECKED
    assert score is None
    assert "connection refused" in reason


@pytest.mark.asyncio
async def test_plagiarism_unchecked_when_not_configured():
    with patch("app.services.background_jobs.PlagiarismChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            return_value={"checked": False, "error": "Copyscape API not configured"}
        )
        score, uniqueness, status, reason = await _check_plagiarism_quality(
            "Some content", 85.0
        )

    assert status == CheckStatus.UNCHECKED
    assert status != CheckStatus.PASSED
    assert score is None
    assert "Copyscape API not configured" in reason


@pytest.mark.asyncio
async def test_plagiarism_unchecked_when_provider_throws():
    with patch("app.services.background_jobs.PlagiarismChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            side_effect=RuntimeError("timeout")
        )
        score, uniqueness, status, reason = await _check_plagiarism_quality(
            "Some content", 85.0
        )

    assert status == CheckStatus.UNCHECKED
    assert score is None
    assert "timeout" in reason


@pytest.mark.asyncio
async def test_ai_detection_unchecked_when_provider_disabled():
    """GPTZero deliberately off: content untouched, no multi-pass, unchecked."""
    humanizer = MagicMock()
    humanizer.humanize_multi_pass = AsyncMock()

    with patch("app.services.background_jobs.AIDetectionChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            return_value={"checked": False, "error": "AI detection is disabled"}
        )
        score, content, provider, status, reason = await _check_ai_detection_quality(
            "Original content", 55.0, humanizer, "openai", "gpt-4", "en"
        )

    assert status == CheckStatus.UNCHECKED
    assert status != CheckStatus.PASSED
    assert score is None
    assert content == "Original content"  # returned unchanged
    assert provider == "none"
    assert "AI detection is disabled" in reason
    humanizer.humanize_multi_pass.assert_not_called()


@pytest.mark.asyncio
async def test_ai_detection_unchecked_when_provider_throws():
    humanizer = MagicMock()
    humanizer.humanize_multi_pass = AsyncMock()

    with patch("app.services.background_jobs.AIDetectionChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            side_effect=RuntimeError("provider outage")
        )
        score, content, provider, status, reason = await _check_ai_detection_quality(
            "Original content", 55.0, humanizer, "openai", "gpt-4", "en"
        )

    assert status == CheckStatus.UNCHECKED
    assert score is None
    assert content == "Original content"
    assert "provider outage" in reason
    humanizer.humanize_multi_pass.assert_not_called()


@pytest.mark.asyncio
async def test_checks_still_fail_honestly_when_provider_works():
    """Sanity: a working provider that finds problems returns FAILED, not
    unchecked — the tri-state must not soften real failures."""
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            return_value={"checked": True, "matches": [{}] * 25}
        )
        score, errors, status, reason = await _check_grammar_quality(
            "Bad content", "en", 10
        )

    assert status == CheckStatus.FAILED
    assert errors == 25
    assert score == 0.0  # 100 - 25*5 clamps at 0
    assert "25 errors" in reason


def test_check_status_str_is_the_value():
    """str(CheckStatus.X) must serialize to the raw value for JSON payloads."""
    assert str(CheckStatus.PASSED) == "passed"
    assert str(CheckStatus.FAILED) == "failed"
    assert str(CheckStatus.UNCHECKED) == "unchecked"
    # Plain-string mocks compare equal (str-mixin contract)
    assert CheckStatus.FAILED == "failed"


@pytest.mark.asyncio
async def test_grammar_check_strips_citation_anchors_before_languagetool():
    """Stage B4.2: citation anchors like [Rossi2021, 2021] must not reach
    LanguageTool — they inflate the error count (-5 points per match) and
    caused the grammar-score regression (95 -> 60-70)."""
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        check_text = AsyncMock(return_value={"checked": True, "matches": []})
        checker_class.return_value.check_text = check_text
        await _check_grammar_quality(
            "Gli studenti migliorano [Rossi2021, 2021] con il tempo "
            "[Smith2020; Lee2019].",
            "it",
            10,
        )

    sent_text = check_text.call_args.kwargs["text"]
    assert "[Rossi2021" not in sent_text
    assert "[Smith2020" not in sent_text
    assert "Gli studenti migliorano" in sent_text


# ----------------------------------------------------------------------
# strip_citation_anchors: stripping must not CREATE LanguageTool errors
# (double spaces, space before punctuation) — B-fix wave, item 3.
# ----------------------------------------------------------------------


def test_strip_citation_anchors_no_whitespace_artifacts():
    from app.services.background_jobs import strip_citation_anchors

    text = (
        "Gli studenti migliorano [Rossi2021, 2021] con il tempo "
        "[Smith2020; Lee2019]. Fine [Nappo,2023]!"
    )
    cleaned = strip_citation_anchors(text)

    assert "[" not in cleaned and "]" not in cleaned
    assert "  " not in cleaned
    assert " ." not in cleaned and " !" not in cleaned and " ," not in cleaned
    assert cleaned == "Gli studenti migliorano con il tempo. Fine!"


def test_strip_citation_anchors_keeps_plain_text_unchanged():
    from app.services.background_jobs import strip_citation_anchors

    text = "Una frase normale, senza citazioni: resta intatta."
    assert strip_citation_anchors(text) == text


@pytest.mark.asyncio
async def test_grammar_check_sends_normalized_text():
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        check_text = AsyncMock(return_value={"checked": True, "matches": []})
        checker_class.return_value.check_text = check_text
        await _check_grammar_quality(
            "Testo con ancora [Rossi2021, 2021] dentro.", "it", 10
        )

    sent_text = check_text.await_args.kwargs.get("text") or check_text.await_args[0][0]
    assert "  " not in sent_text
    assert " ." not in sent_text
    assert "Rossi2021" not in sent_text
