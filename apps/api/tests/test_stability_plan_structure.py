"""Control 11 (job 11, 2026-09-09): sparse preparation answers and exact rejects.

The preparation reply stopped on "changed section structure" and nothing
retained said which section or field. Two bounded corrections: the reply
contract asks only for ``academic_plan`` and, per section, the exact title
plus editable fields (the server keeps every immutable value from the saved
outline), and any structural violation is rejected with a bounded record of
section index, field, before and after. None of this decides whether the
frozen evidence satisfies the brief: a genuine ``blocking_conflicts`` entry
still stops a structurally valid answer, and the semantic reviewer is not
replaced. The fixtures are synthetic; they do not verify the live model.
"""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.document import DocumentProvenance
from app.services.academic_context import digest
from app.services.generation_outcomes import GenerationStageError
from app.services.plan_preparation import (
    REJECTION_ITEM_CHARS,
    SECTION_FIELDS,
    PlanRejected,
    plan_output_budget,
    prepare_final_plan,
    reconcile_outline,
)
from tests.test_academic_quality import example, seed_review

IMMUTABLE = ("subsections", "estimated_words", "key_concepts")
UNMET = "L'indice richiede 2.2 termoregolazione: nessuna fonte frozen la supporta."


def _immutable_projection(outline):
    return [
        {"title": s["title"], **{k: s.get(k) for k in IMMUTABLE}}
        for s in outline["sections"]
    ]


def _with_structure(outline):
    """The control-11 shape: subsections, target words and key concepts."""
    outline = copy.deepcopy(outline)
    for index, section in enumerate(outline["sections"], 1):
        section["subsections"] = [
            f"{index}.1 Sotto {index}",
            f"{index}.2 Altro {index}",
        ]
        section["estimated_words"] = 900 + index
        section["key_concepts"] = [f"concetto {index}", "termoregolazione"]
    outline["academic_plan"]["scope_note"] = "kept when the reply omits it"
    outline["academic_plan"]["conflicts"] = ["Nota provvisoria del planner."]
    outline["sections"][0]["evidence_keys"] = ["Pruned2020"]  # forces the model
    return outline


def _sparse_reply(outline, *, blocking=None):
    """Only the allowed top fields and, per section, exact title + edits."""
    return {
        "academic_plan": {
            "research_question": outline["academic_plan"]["research_question"],
            "objectives": outline["academic_plan"]["objectives"],
            "limitations": ["Nota provvisoria del planner (limite dichiarato)."],
            "blocking_conflicts": list(blocking or []),
        },
        "sections": [
            {
                "title": s["title"],
                "main_points": [*s["main_points"], "confronto aggiornato"],
                "academic_functions": s["academic_functions"],
                "evidence_keys": ["Author2024"],
            }
            for s in outline["sections"]
        ],
    }


async def _work(db):
    doc, job, pack = await seed_review(db)
    doc.outline = _with_structure(doc.outline)
    await db.commit()
    return doc, job, pack


async def _preparation_events(db):
    return list(
        (
            await db.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.event_type == "academic_plan_preparation")
                .order_by(DocumentProvenance.id)
            )
        ).scalars()
    )


def test_sparse_reply_merges_and_immutable_values_come_from_the_original():
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    frozen = copy.deepcopy(original)
    reply = _sparse_reply(original)

    merged = reconcile_outline(original, reply)

    assert original == frozen  # never mutated
    assert _immutable_projection(merged) == _immutable_projection(original)
    assert [s["evidence_keys"] for s in merged["sections"]] == [["Author2024"]] * 4
    assert merged["sections"][0]["main_points"][-1] == "confronto aggiornato"
    plan = merged["academic_plan"]
    assert plan["scope_note"] == "kept when the reply omits it"
    assert plan["blocking_conflicts"] == [] and plan["limitations"]
    assert "conflicts" not in plan  # sorted into the authoritative lists
    assert set(merged) == set(original)


def test_full_exact_echo_remains_compatible():
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    echo = copy.deepcopy(original)
    echo["academic_plan"]["blocking_conflicts"] = []
    echo["sections"][1]["evidence_keys"] = ["Author2024"]
    echo["tokens_used"] = 123
    merged = reconcile_outline(original, echo)
    assert _immutable_projection(merged) == _immutable_projection(original)
    assert (
        merged["academic_plan"]["conflicts"] == original["academic_plan"]["conflicts"]
    )
    assert merged["sections"][1]["evidence_keys"] == ["Author2024"]
    assert "tokens_used" not in merged


def test_sparse_plan_without_blocking_list_keeps_the_legacy_input():
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    reply = _sparse_reply(original)
    del reply["academic_plan"]["blocking_conflicts"]
    merged = reconcile_outline(original, reply)
    # Conservative: the planner's provisional notes still block downstream.
    assert merged["academic_plan"]["conflicts"] == ["Nota provvisoria del planner."]


@pytest.mark.parametrize(
    "mutation,kind,index,field",
    [
        ("subsections", "section_field", 2, "subsections"),
        ("estimated_words", "section_field", 3, "estimated_words"),
        ("key_concepts", "section_field", 1, "key_concepts"),
        ("new_field", "section_field", 4, "notes"),
        ("order", "section_title", 1, "title"),
        ("count", "section_count", None, None),
        ("top_field", "top_field", None, "appendix"),
    ],
)
def test_changed_or_added_forbidden_structure_rejects_with_precise_evidence(
    mutation, kind, index, field
):
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    frozen = copy.deepcopy(original)
    reply = _sparse_reply(original)
    before_value = None
    if mutation == "subsections":
        before_value = original["sections"][1]["subsections"]
        reply["sections"][1]["subsections"] = ["2.1 Cambiata"]
    elif mutation == "estimated_words":
        before_value = original["sections"][2]["estimated_words"]
        reply["sections"][2]["estimated_words"] = 1500
    elif mutation == "key_concepts":
        before_value = original["sections"][0]["key_concepts"]
        reply["sections"][0]["key_concepts"] = ["ostetricia"]
    elif mutation == "new_field":
        reply["sections"][3]["notes"] = "campo aggiunto dal modello"
    elif mutation == "order":
        reply["sections"][0], reply["sections"][1] = (
            reply["sections"][1],
            reply["sections"][0],
        )
    elif mutation == "count":
        reply["sections"].pop()
    else:
        reply["appendix"] = ["non richiesto"]

    with pytest.raises(PlanRejected) as error:
        reconcile_outline(original, reply)

    assert original == frozen
    detail = error.value.detail
    assert (detail["kind"], detail["section_index"], detail["field"]) == (
        kind,
        index,
        field,
    )
    if mutation == "count":
        assert (detail["before"], detail["after"]) == ("4", "3")
    elif mutation == "order":
        assert detail["before"] == original["sections"][0]["title"]
        assert detail["after"] == original["sections"][1]["title"]
    elif mutation == "new_field":
        assert detail["before"] is None
        assert detail["after"] == "campo aggiunto dal modello"
    elif mutation == "top_field":
        assert detail["before"] is None and detail["after"] == ["non richiesto"]
    else:
        assert detail["before"] == (
            [str(v) for v in before_value]
            if isinstance(before_value, list)
            else str(before_value)
        )
    if index is not None:
        assert str(index) in str(error.value)
    if field is not None and field != "title":
        assert field in str(error.value)


def test_structure_evidence_is_bounded():
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    reply = _sparse_reply(original)
    reply["sections"][0]["subsections"] = ["x" * (REJECTION_ITEM_CHARS + 100)] * 30
    with pytest.raises(PlanRejected) as error:
        reconcile_outline(original, reply)
    after = error.value.detail["after"]
    assert len(after) == 20 and all(len(item) == REJECTION_ITEM_CHARS for item in after)
    reply["sections"][0]["subsections"] = "y" * (REJECTION_ITEM_CHARS + 100)
    with pytest.raises(PlanRejected) as error:
        reconcile_outline(original, reply)
    assert len(error.value.detail["after"]) == REJECTION_ITEM_CHARS


def test_editable_fields_are_exactly_the_contract():
    assert SECTION_FIELDS == {
        "main_points",
        "academic_functions",
        "evidence_keys",
        "limitations",
        "blocking_conflicts",
    }


@pytest.mark.asyncio
async def test_sparse_answer_completes_and_persists_original_structure(db_session):
    doc, job, pack = await _work(db_session)
    structure_before = _immutable_projection(doc.outline)
    reply = _sparse_reply(doc.outline)
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=reply))

    result = await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)

    assert result["status"] == "completed" and result["model_called"]
    assert ai.call_with_fallback.await_count == 1
    assert _immutable_projection(doc.outline) == structure_before
    assert doc.outline["academic_plan"]["blocking_conflicts"] == []
    assert result["output_sha256"] == digest(doc.outline)
    prompt = ai.call_with_fallback.call_args.args[0]
    assert "Do not return subsections, estimated_words, key_concepts" in prompt
    assert "complete outline JSON" not in prompt
    assert all(s["title"] in prompt for s in doc.outline["sections"])
    # Budget sizing is unchanged: still derived from the saved outline.
    started = list(
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "academic_plan_preparation_started"
                )
            )
        ).scalars()
    )
    model = settings.AI_FALLBACK_CHAIN_LIST[0][1]
    assert started[0].payload["output_budget"] == plan_output_budget(doc.outline, model)
    again = await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)
    assert again == result and ai.call_with_fallback.await_count == 1


@pytest.mark.asyncio
async def test_changed_immutable_field_is_persisted_as_precise_rejection(
    db_session,
):
    doc, job, pack = await _work(db_session)
    before = copy.deepcopy(doc.outline)
    reply = _sparse_reply(doc.outline)
    reply["sections"][1]["subsections"] = ["2.1 Riscritta dal modello"]
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=reply))

    for _ in range(2):
        with pytest.raises(GenerationStageError) as error:
            await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)
        assert error.value.reason_code == "plan_requirements_unmet"

    assert ai.call_with_fallback.await_count == 1
    assert doc.outline == before
    (event,) = await _preparation_events(db_session)
    payload = event.payload
    assert (payload["status"], payload["outcome"]) == ("failed", "rejected")
    assert "розділу 2" in payload["reason"] and "subsections" in payload["reason"]
    structure = payload["rejection"]["structure"]
    assert structure == {
        "kind": "section_field",
        "section_index": 2,
        "field": "subsections",
        "before": before["sections"][1]["subsections"],
        "after": ["2.1 Riscritta dal modello"],
    }
    assert payload["rejection"]["problems"] == [payload["reason"]]
    assert payload["rejection"]["response_sha256"] == digest(reply)
    # Nothing beyond the violated field is copied from the reply.
    assert "main_points" not in str(payload["rejection"]["structure"])


@pytest.mark.asyncio
async def test_genuine_blocking_conflict_rejects_a_structurally_valid_sparse_answer(
    db_session,
):
    doc, job, pack = await _work(db_session)
    before = copy.deepcopy(doc.outline)
    reply = _sparse_reply(doc.outline, blocking=[UNMET])
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=reply))

    with pytest.raises(GenerationStageError) as error:
        await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)

    assert error.value.reason_code == "plan_requirements_unmet"
    assert doc.outline == before
    (event,) = await _preparation_events(db_session)
    rejection = event.payload["rejection"]
    assert rejection["problems"] == [UNMET]
    assert rejection["plan_fields"]["blocking_conflicts"] == [UNMET]
    assert "structure" not in rejection  # the structure was valid


@pytest.mark.parametrize("level", ["section", "outline"])
def test_unknown_null_field_has_precise_diagnostic(level):
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    reply = _sparse_reply(original)
    target = reply["sections"][0] if level == "section" else reply
    target["unexpected"] = None
    with pytest.raises(PlanRejected) as error:
        reconcile_outline(original, reply)
    assert error.value.detail["field"] == "unexpected"
    assert error.value.detail["after"] is None


def test_long_unknown_field_is_bounded_in_diagnostic():
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    reply = _sparse_reply(original)
    reply["sections"][0]["x" * 5000] = "unexpected"
    with pytest.raises(PlanRejected) as error:
        reconcile_outline(original, reply)
    assert len(error.value.detail["field"]) == 200
    assert len(str(error.value)) < 300


def test_sparse_plan_can_replace_a_malformed_original_academic_plan():
    doc, _, _ = example()
    original = _with_structure(doc.outline)
    reply = _sparse_reply(original)
    original["academic_plan"] = None
    result = reconcile_outline(original, reply)
    assert result["academic_plan"] == reply["academic_plan"]
    assert original["academic_plan"] is None
