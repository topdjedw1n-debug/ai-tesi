"""
Unit tests for best-of-N detector-in-the-loop in humanize_multi_pass.

Both the humanizer's provider call and the AI detector are mocked, so these
tests exercise the selection logic only (no network, no real scoring).
"""

from unittest.mock import AsyncMock

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
