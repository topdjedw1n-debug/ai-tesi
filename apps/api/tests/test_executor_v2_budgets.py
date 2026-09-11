"""Specification amendment 3: language-aware S4 budgets and truncated sections kept.

Fixtures are extracted from the real job14 recording (document 12, 2026-09-09):
30 recorded S4 calls with their actual output tokens, and the two truncated
responses of section 15. Neither the recording nor the model is contacted here.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.executor_v2.budgets import POLICY, output_budget
from app.services.executor_v2.run import Context
from app.services.executor_v2.sections import complete_prefix, write_sections
from app.services.executor_v2.warnings import ExecutionStop
from app.services.replay_dependencies import recording_context
from tests.test_executor_v2 import response, seed

FIXTURES = Path(__file__).parent / "fixtures/executor_v2"
CALLS = json.loads((FIXTURES / "job14_s4_calls.json").read_text())
SECTION_15 = json.loads((FIXTURES / "job14_section15_truncated.json").read_text())


def test_s4_budget_covers_every_recorded_job14_section():
    per_section = {}
    for call in CALLS["calls"]:
        per_section.setdefault(call["section_index"], []).append(call)
    assert len(CALLS["calls"]) == 30 and len(per_section) == 15
    for index, rows in per_section.items():
        # Both recorded replies together are a lower bound of the real need.
        needed = sum(row["output_tokens"] for row in rows)
        budget = output_budget("S4", rows[0]["target_words"], CALLS["language"])
        assert budget >= needed * 1.3, (index, budget, needed)
        # The old first attempt was cut at exactly the old budget for every section.
        assert rows[0]["stop_reason"] == "max_tokens"
        assert budget > rows[0]["output_tokens"] * 2
    assert output_budget("S4", 600, "it") == 3840 > output_budget("S4", 600, "en")
    assert output_budget("S4", 600, None) == output_budget("S4", 600, "xx") == 3600
    assert output_budget("S4", 10, "it") == POLICY["section_min_tokens"]
    assert POLICY["words_per_page"] == 340


def test_complete_prefix_cuts_at_the_last_finished_sentence():
    assert (
        complete_prefix("Prima frase. Seconda frase incompleta senza") == "Prima frase."
    )
    assert (
        complete_prefix("Domanda? Poi «citazione.» E poi ancora")
        == "Domanda? Poi «citazione.»"
    )
    assert complete_prefix("mai finita") == ""
    kept = complete_prefix(SECTION_15["first"] + "\n" + SECTION_15["continuation"])
    assert kept and kept.endswith(".") and "contributo di rifless" not in kept


def outline(*targets):
    return [
        {
            "section_index": i,
            "title": f"Sezione {i}",
            "purpose": "test",
            "main_points": [],
            "scope_ids": [],
            "evidence_keys": [],
            "target_words": words,
        }
        for i, words in enumerate(targets, 1)
    ]


async def run_sections(db_session, ctx, plan):
    await ctx.initialize()
    await ctx.save_outline(plan)
    pack = SimpleNamespace(sources=[], by_key=lambda key: None)
    token = recording_context.set(ctx.recording)
    try:
        return await write_sections(ctx, plan, pack)
    finally:
        recording_context.reset(token)


@pytest.mark.asyncio
async def test_second_truncation_keeps_finished_sentences_and_continues(
    db_session, monkeypatch
):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.provider = AsyncMock(
        side_effect=[
            response(SECTION_15["first"], True),
            response(SECTION_15["continuation"], True),
            response("La sezione successiva è completa. Termina qui."),
        ]
    )
    result = await run_sections(db_session, ctx, outline(201, 150))
    assert [row["section_index"] for row in result] == [1, 2]
    kept = result[0]["content"]
    assert kept.endswith(".") and "contributo di rifless" not in kept
    assert result[0]["word_count"] >= POLICY["min_kept_words"]
    codes = {(w["code"], w["section_index"]) for w in ctx.warnings}
    assert ("output_truncated_kept", 1) in codes
    assert ("output_truncated_retried", 1) not in codes
    requests = [call.kwargs for call in ctx.provider.await_args_list]
    assert requests[0]["max_tokens"] == output_budget("S4", 201, "it") == 2000
    assert requests[1]["max_tokens"] == 2000 * POLICY["truncation_multiplier"]
    prompt = requests[0]["messages"][0]["content"]
    assert '"target_words_range": [201, 280]' in prompt
    assert "stop at a complete sentence" in prompt


@pytest.mark.asyncio
async def test_second_truncation_without_enough_text_stops(db_session, monkeypatch):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.provider = AsyncMock(
        side_effect=[
            response("Una frase completa. E poi un frammento che non", True),
            response(" arriva mai alla fine del", True),
        ]
    )
    with pytest.raises(ExecutionStop) as stop:
        await run_sections(db_session, ctx, outline(201))
    assert stop.value.stop["code"] == "provider_unusable_response"
    assert not any(w["code"] == "output_truncated_kept" for w in ctx.warnings)
