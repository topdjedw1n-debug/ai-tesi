"""
Unit tests for best-of-N detector-in-the-loop in humanize_multi_pass.

Both the humanizer's provider call and the AI detector are mocked, so these
tests exercise the selection logic only (no network, no real scoring).
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.ai_pipeline.humanizer import Humanizer


class _FakeChecker:
    """Stand-in for AIDetectionChecker: scores text from a lookup/callable."""

    def __init__(self, scores):
        self._scores = scores

    async def check_text(self, text):
        score = self._scores(text) if callable(self._scores) else self._scores.get(text)
        if score is None:
            return {"checked": False, "error": "unavailable"}
        return {"checked": True, "ai_probability": score, "provider": "fake"}


def _patch_checker(monkeypatch, scores):
    monkeypatch.setattr(
        "app.services.ai_detection_checker.AIDetectionChecker",
        lambda: _FakeChecker(scores),
    )


@pytest.mark.asyncio
async def test_best_of_n_picks_lowest_scoring_variant(monkeypatch):
    monkeypatch.setattr(settings, "HUMANIZER_BEST_OF_N", 3)

    # humanize() returns a distinct text per style variant.
    async def fake_humanize(*, style_variant, **_):
        return f"s{style_variant}"

    scores = {"orig": 90.0, "s0": 80.0, "s2": 40.0, "s3": 60.0}
    _patch_checker(monkeypatch, scores)

    h = Humanizer()
    h.humanize = AsyncMock(side_effect=fake_humanize)

    trace: dict = {}
    text, score = await h.humanize_multi_pass(
        text="orig",
        provider="openai",
        model="gpt-4",
        target_ai_score=50.0,
        max_attempts=3,
        score_trace=trace,
    )

    # Lowest of {80, 40, 60} is s2 at 40, which also clears the 50 target.
    assert (text, score) == ("s2", 40.0)
    assert trace["best_of_n"] == 3
    # 1 baseline + 3 variants = 4 detector calls.
    assert trace["detector_calls"] == 4
    assert trace["variant_scores"] == [[80.0, 40.0, 60.0]]


@pytest.mark.asyncio
async def test_n1_matches_legacy_single_variant(monkeypatch):
    monkeypatch.setattr(settings, "HUMANIZER_BEST_OF_N", 1)

    captured = {}

    async def fake_humanize(*, style_variant, **_):
        captured["style_variant"] = style_variant
        return "rescued"

    _patch_checker(monkeypatch, {"orig": 90.0, "rescued": 40.0})

    h = Humanizer()
    h.humanize = AsyncMock(side_effect=fake_humanize)

    text, score = await h.humanize_multi_pass(
        text="orig",
        provider="openai",
        model="gpt-4",
        target_ai_score=50.0,
        max_attempts=3,
    )

    assert (text, score) == ("rescued", 40.0)
    # Legacy path uses the attempt+1 style directive (attempt 0 -> variant 1).
    assert captured["style_variant"] == 1
    assert h.humanize.await_count == 1


@pytest.mark.asyncio
async def test_detector_unavailable_on_initial_check(monkeypatch):
    monkeypatch.setattr(settings, "HUMANIZER_BEST_OF_N", 3)
    _patch_checker(monkeypatch, lambda _text: None)  # always unchecked

    h = Humanizer()
    h.humanize = AsyncMock(side_effect=AssertionError("should not humanize"))

    trace: dict = {}
    text, score = await h.humanize_multi_pass(
        text="orig",
        provider="openai",
        model="gpt-4",
        score_trace=trace,
    )

    assert (text, score) == ("orig", 100.0)
    assert trace["detector_calls"] == 1
    h.humanize.assert_not_awaited()


@pytest.mark.asyncio
async def test_returns_best_when_target_never_reached(monkeypatch):
    monkeypatch.setattr(settings, "HUMANIZER_BEST_OF_N", 1)

    outputs = iter(["h1", "h2", "h3"])

    async def fake_humanize(**_):
        return next(outputs)

    # Improves each pass but never reaches the 25 target; best is 50.
    scores = {"orig": 90.0, "h1": 70.0, "h2": 60.0, "h3": 50.0}
    _patch_checker(monkeypatch, scores)

    h = Humanizer()
    h.humanize = AsyncMock(side_effect=fake_humanize)

    text, score = await h.humanize_multi_pass(
        text="orig",
        provider="openai",
        model="gpt-4",
        target_ai_score=25.0,
        max_attempts=3,
    )

    assert (text, score) == ("h3", 50.0)
    assert h.humanize.await_count == 3


# ----------------------------------------------------------------------
# Corruption guard (Masters-2: garbled gpt-4 output at temp>=1.1 scored
# 0.3-3.4% "human" and won best-of-N, then died at the panel)
# ----------------------------------------------------------------------


def test_looks_garbled_rejects_symbol_soup():
    from app.services.ai_pipeline.humanizer import _looks_garbled

    garbage = (
        "Il riscaldamento globale ⊄⊕ ha ∆∆ effetti ¤¤ significativi "
        "≈≈ sull'agricoltura ⊗⊗ e ∞∞ sulle ††† risorse ▓▓ idriche ��"
    )
    assert _looks_garbled(garbage) is True


def test_looks_garbled_rejects_vowelless_nonwords():
    from app.services.ai_pipeline.humanizer import _looks_garbled

    nonwords = " ".join(["asdkj fjqw pzkr mnbv qwrtz xcvbn"] * 10)
    assert _looks_garbled(nonwords) is True


def test_looks_garbled_accepts_real_italian_prose():
    from app.services.ai_pipeline.humanizer import _looks_garbled

    prose = (
        "Il riscaldamento globale rappresenta una delle sfide più gravi "
        "per i paesi del Medio Oriente [Rossi, 2024]. Lo stress idrico, "
        "già critico, peggiora — e la sicurezza alimentare ne risente "
        "(circa il 60% del fabbisogno è importato). «La regione», scrive "
        "l'autore, “resta la più esposta”. "
    ) * 10
    assert _looks_garbled(prose) is False


def test_looks_garbled_accepts_frozen_placeholders():
    from app.services.ai_pipeline.humanizer import _looks_garbled

    text = (
        "La letteratura recente ⟦C1⟧ conferma questa tendenza, e i dati "
        "⟦C2⟧ mostrano un peggioramento costante delle riserve idriche "
        "regionali nel corso dell'ultimo decennio. "
    ) * 10
    assert _looks_garbled(text) is False


@pytest.mark.asyncio
async def test_best_of_n_skips_garbled_variant(monkeypatch):
    """The garbled variant scores lowest but must NOT be selected."""
    from app.core.config import settings as real_settings
    from app.services.ai_pipeline.humanizer import Humanizer

    monkeypatch.setattr(real_settings, "HUMANIZER_BEST_OF_N", 3)

    clean = (
        "Un testo accademico perfettamente leggibile sulla transizione "
        "energetica europea e le sue conseguenze economiche regionali. "
    ) * 10
    garbled = "zxcqw ⊗⊗ pfkrt ∆∆ mnvbz ¤¤ " * 40

    humanizer = Humanizer()
    variants = iter([garbled, clean, clean])
    humanizer.humanize = AsyncMock(side_effect=lambda **kw: next(variants))

    scores = {garbled: 0.3, clean: 28.0}

    async def fake_check(text):
        return {"checked": True, "ai_probability": scores.get(text, 85.0)}

    with patch("app.services.ai_detection_checker.AIDetectionChecker") as checker_cls:
        checker_cls.return_value.check_text = AsyncMock(side_effect=fake_check)
        best_text, best_score = await humanizer.humanize_multi_pass(
            text="testo originale con punteggio alto " * 20,
            provider="anthropic",
            model="claude-opus-4-8",
            target_ai_score=35.0,
            max_attempts=1,
        )

    assert best_text == clean
    assert best_score == 28.0
