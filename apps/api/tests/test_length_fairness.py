"""
Validation-6 fixes: length-fair grammar gate, per-section length brief in the
writer prompt, length backstop in panel mode, and the honest writer trail.

Context (Фаза 5): Opus writes ~1400-word sections against a ~500-word outline
target. The absolute grammar cap failed it on volume (28 errors/1400 words =
20/1000 — denser gpt-4 sections passed at 31/1000), the prompt never told the
model how long the section should be, panel mode had dropped the word-count
check entirely, and a mid-document provider outage silently swapped the
writer with no trace.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_pipeline.prompt_builder import PromptBuilder
from app.services.background_jobs import CheckStatus, _check_grammar_quality


def _grammar_result(error_count: int) -> dict:
    return {"checked": True, "matches": [{"rule": f"r{i}"} for i in range(error_count)]}


# ----------------------------------------------------------------------
# Grammar gate: budget scales with length
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grammar_long_section_gets_scaled_budget():
    """28 errors in ~1400 words (20/1000) passes: budget = 1400/1000*20 = 28.
    This is exactly the t3-energia-opus section the absolute cap killed."""
    text = "parola " * 1400
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            return_value=_grammar_result(28)
        )
        score, errors, status, reason = await _check_grammar_quality(text, "it", 10)

    assert status == CheckStatus.PASSED
    assert errors == 28
    assert reason is None


@pytest.mark.asyncio
async def test_grammar_short_section_keeps_absolute_floor():
    """450 words: the scaled budget (9) must NOT tighten below the non-EN
    floor of 20 — short sections behave exactly as before."""
    text = "parola " * 450
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            return_value=_grammar_result(20)
        )
        score, errors, status, reason = await _check_grammar_quality(text, "it", 10)

    assert status == CheckStatus.PASSED


@pytest.mark.asyncio
async def test_grammar_dense_long_section_still_fails():
    """54 errors in ~1500 words (36/1000) exceeds the scaled budget (30) —
    genuinely sloppy text keeps failing regardless of length."""
    text = "parola " * 1500
    with patch("app.services.background_jobs.GrammarChecker") as checker_class:
        checker_class.return_value.check_text = AsyncMock(
            return_value=_grammar_result(54)
        )
        score, errors, status, reason = await _check_grammar_quality(text, "it", 10)

    assert status == CheckStatus.FAILED
    assert "54 errors" in reason


@pytest.mark.asyncio
async def test_grammar_per_1000_zero_disables_scaling():
    with patch("app.services.background_jobs.settings") as mock_settings:
        mock_settings.QUALITY_GRAMMAR_ERRORS_PER_1000 = 0
        mock_settings.QUALITY_MAX_GRAMMAR_ERRORS_NON_EN = 20
        with patch("app.services.background_jobs.GrammarChecker") as checker_class:
            checker_class.return_value.check_text = AsyncMock(
                return_value=_grammar_result(28)
            )
            text = "parola " * 1400
            score, errors, status, reason = await _check_grammar_quality(text, "it", 10)

    assert status == CheckStatus.FAILED  # legacy absolute behavior


# ----------------------------------------------------------------------
# Prompt: per-section length brief
# ----------------------------------------------------------------------


def test_section_prompt_carries_word_target(sample_document_factory=None):
    class Doc:
        topic = "Tema"
        language = "it"
        target_pages = 6

    prompt = PromptBuilder.build_section_prompt(
        document=Doc(),
        section_title="Introduzione",
        section_index=1,
        target_word_count=500,
    )
    assert "approximately 500 words" in prompt
    assert "do not exceed 600 words" in prompt


def test_section_prompt_without_target_has_no_length_brief():
    class Doc:
        topic = "Tema"
        language = "it"
        target_pages = 6

    prompt = PromptBuilder.build_section_prompt(
        document=Doc(),
        section_title="Introduzione",
        section_index=1,
    )
    assert "Section Length" not in prompt


# ----------------------------------------------------------------------
# Honest writer trail (Validation-6: credit outage silently swapped Opus
# for gpt-4 mid-document; nothing recorded it)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_records_actual_writer():
    """When the preferred writer dies, _last_writer names who really wrote."""
    from app.services.ai_pipeline.generator import SectionGenerator

    gen = SectionGenerator()
    with (
        patch.object(
            gen, "_call_anthropic", AsyncMock(side_effect=RuntimeError("credits"))
        ),
        patch.object(gen, "_call_openai", AsyncMock(return_value="text")),
        patch("app.services.ai_pipeline.generator.settings") as mock_settings,
    ):
        mock_settings.AI_ENABLE_FALLBACK = True
        mock_settings.AI_FALLBACK_CHAIN_LIST = [
            ("openai", "gpt-4"),
        ]
        result = await gen._call_ai_with_fallback(
            prompt="p",
            language="it",
            purpose="test",
            preferred=("anthropic", "claude-opus-4-8"),
        )

    assert result == "text"
    assert gen._last_writer == ("openai", "gpt-4")


@pytest.mark.asyncio
async def test_preferred_writer_success_records_no_fallback():
    from app.services.ai_pipeline.generator import SectionGenerator

    gen = SectionGenerator()
    with (
        patch.object(gen, "_call_anthropic", AsyncMock(return_value="text")),
        patch("app.services.ai_pipeline.generator.settings") as mock_settings,
    ):
        mock_settings.AI_ENABLE_FALLBACK = True
        mock_settings.AI_FALLBACK_CHAIN_LIST = [("openai", "gpt-4")]
        await gen._call_ai_with_fallback(
            prompt="p",
            language="it",
            purpose="test",
            preferred=("anthropic", "claude-opus-4-8"),
        )

    assert gen._last_writer == ("anthropic", "claude-opus-4-8")
