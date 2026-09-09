"""Control 10 (job 10, 2026-09-09): the S1 requirement/limitation contract.

The planner records every brief tension in the legacy ``academic_plan.conflicts``
list. Reconciliation must sort them into ``limitations`` (permissible) and
``blocking_conflicts`` (explicit requirements that remain unmet). The structural
check reads ONLY ``blocking_conflicts`` once that list exists; before the fix
``[] or conflicts`` fell back to the legacy list, so a complete plan that kept
the provisional list beside an empty authoritative one was rejected as
``plan_requirements_unmet``, and only a 500-character prefix of the joined
problems survived as evidence. Admissibility of the limitations remains the
semantic reviewer's judgement; nothing here grants that PASS.
"""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.document import DocumentProvenance
from app.services.academic_context import digest
from app.services.academic_review import (
    outline_problems,
    plan_conflicts,
    run_academic_review,
)
from app.services.generation_outcomes import GenerationStageError
from app.services.plan_preparation import (
    REJECTION_ITEM_CHARS,
    prepare_final_plan,
    rejection_evidence,
)
from tests.test_academic_quality import example, seed_review, verdict

# Synthetic permissible limitations. Whether the real control's missing
# clinical evidence satisfies its specific brief requires semantic review;
# these fixtures do not adjudicate that unretained model reply.
PROVISIONAL = [
    "Revisione narrativa ammessa dal brief; nessun protocollo PRISMA dichiarato.",
    "Popolazioni internazionali: limiti di trasferibilita dichiarati.",
    "Nessuna raccolta di dati primari richiesta; analisi della letteratura.",
]
UNMET = (
    "L'indice richiede la valutazione della conformazione pelvica, esclusa dal "
    "vincolo del relatore: requisito esplicito non soddisfatto. " * 6
).strip()


@pytest.mark.parametrize(
    "plan,expected",
    [
        # Legacy-only input stays conservative: every entry blocks.
        ({"conflicts": ["a", "b"]}, ["a", "b"]),
        ({"conflicts": "single"}, ["single"]),
        # An explicit list is authoritative, including an empty one.
        ({"conflicts": ["a"], "blocking_conflicts": []}, []),
        ({"conflicts": ["a"], "limitations": ["a"], "blocking_conflicts": []}, []),
        ({"conflicts": ["a"], "blocking_conflicts": ["real"]}, ["real"]),
        # Nothing is erased by type coercion.
        ({"blocking_conflicts": [{"requirement": "R"}]}, ["{'requirement': 'R'}"]),
        ({"blocking_conflicts": [""]}, [""]),
    ],
)
def test_blocking_list_is_authoritative_and_legacy_input_is_conservative(
    plan, expected
):
    assert plan_conflicts(plan) == expected


@pytest.mark.parametrize("value", [None, "nessuno", {}, {"x": 1}, 0, False, ""])
def test_non_list_blocking_field_is_a_problem_not_an_empty_list(value):
    problems = plan_conflicts({"blocking_conflicts": value, "conflicts": ["a"]})
    assert len(problems) == 1 and problems[0].startswith("blocking_conflicts")


@pytest.mark.parametrize("legacy", [{}, {"conflicts": []}])
def test_explicit_null_is_not_an_empty_authoritative_list(legacy):
    problems = plan_conflicts({**legacy, "blocking_conflicts": None})
    assert len(problems) == 1 and problems[0].startswith("blocking_conflicts")


def test_outline_check_reads_only_the_authoritative_list():
    doc, _, pack = example()
    keys = set(pack.keys())
    doc.outline["academic_plan"]["conflicts"] = list(PROVISIONAL)
    assert outline_problems(doc.outline, keys) == list(PROVISIONAL)
    doc.outline["academic_plan"]["limitations"] = list(PROVISIONAL)
    doc.outline["academic_plan"]["blocking_conflicts"] = []
    assert outline_problems(doc.outline, keys) == []
    doc.outline["academic_plan"]["blocking_conflicts"] = [UNMET]
    assert outline_problems(doc.outline, keys) == [UNMET]
    # Structural checks after the conflict lists are unchanged.
    doc.outline["academic_plan"]["blocking_conflicts"] = []
    doc.outline["sections"][0]["evidence_keys"] = ["Foreign2025"]
    assert outline_problems(doc.outline, keys) == [
        "Розділ 1: немає прив'язки до доступних доказів."
    ]


async def _provisional_work(db):
    doc, job, pack = await seed_review(db)
    doc.outline = copy.deepcopy(doc.outline)
    doc.outline["academic_plan"]["conflicts"] = list(PROVISIONAL)
    await db.commit()
    return doc, job, pack


def _sorted_reply(doc, *, blocking, keep_legacy):
    reply = copy.deepcopy(doc.outline)
    reply["academic_plan"]["limitations"] = [
        p + " (limite dichiarato)" for p in PROVISIONAL
    ]
    reply["academic_plan"]["blocking_conflicts"] = blocking
    if not keep_legacy:
        del reply["academic_plan"]["conflicts"]
    return reply


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


@pytest.mark.asyncio
@pytest.mark.parametrize("keep_legacy", [True, False])
async def test_control_10_shape_sorted_limitations_are_accepted(
    db_session, keep_legacy
):
    """The model sorts every provisional entry as a limitation and reports no
    unmet requirement. Whether it also echoes the legacy list back (the
    'complete outline JSON' reading that control 10 most plausibly took) must
    not change the structural verdict."""
    doc, job, pack = await _provisional_work(db_session)
    titles = [s["title"] for s in doc.outline["sections"]]
    reply = _sorted_reply(doc, blocking=[], keep_legacy=keep_legacy)
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=reply))

    result = await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)

    assert result["status"] == "completed" and result["model_called"]
    assert ai.call_with_fallback.await_count == 1
    assert [s["title"] for s in doc.outline["sections"]] == titles
    assert doc.outline["academic_plan"]["blocking_conflicts"] == []
    assert len(doc.outline["academic_plan"]["limitations"]) == 3
    assert ("conflicts" in doc.outline["academic_plan"]) is keep_legacy
    # The prompt states the contract the reply is judged by.
    prompt = ai.call_with_fallback.call_args.args[0]
    assert "blocking_conflicts is authoritative" in prompt
    assert "academic_plan.conflicts list is planner input" in prompt
    assert PROVISIONAL[0] in prompt
    # Admissibility is still decided by the semantic reviewer, which now runs.
    reviewer = SimpleNamespace(call_with_fallback=AsyncMock(return_value=verdict(True)))
    reviewed = await run_academic_review(
        db_session, doc, job, pack, kind="outline", ai_service=reviewer
    )
    assert reviewer.call_with_fallback.await_count == 1
    assert reviewed["status"] == "passed"
    assert reviewed["binding"]["outline_sha256"] == digest(doc.outline)


@pytest.mark.asyncio
async def test_unmet_explicit_requirement_stays_blocked_with_full_evidence(
    db_session,
):
    doc, job, pack = await _provisional_work(db_session)
    before = copy.deepcopy(doc.outline)
    reply = _sorted_reply(doc, blocking=[UNMET], keep_legacy=False)
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=reply))
    assert len(UNMET) > 500  # longer than the joined reason column keeps

    for _ in range(2):
        with pytest.raises(GenerationStageError) as error:
            await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)
        assert error.value.reason_code == "plan_requirements_unmet"

    assert ai.call_with_fallback.await_count == 1
    assert doc.outline == before
    (event,) = await _preparation_events(db_session)
    payload = event.payload
    assert (payload["status"], payload["outcome"]) == ("failed", "rejected")
    assert payload["reason"] == UNMET[:500]
    # The verdict is auditable after the fact: which list blocked, verbatim.
    rejection = payload["rejection"]
    assert rejection["problems"] == [UNMET] and rejection["problem_count"] == 1
    assert rejection["plan_fields"]["blocking_conflicts"] == [UNMET]
    assert len(rejection["plan_fields"]["limitations"]) == 3
    assert "conflicts" not in rejection["plan_fields"]
    assert rejection["response_sha256"] == digest(reply)


@pytest.mark.asyncio
async def test_wrong_typed_blocking_field_is_rejected_not_erased(db_session):
    doc, job, pack = await _provisional_work(db_session)
    reply = _sorted_reply(doc, blocking="nessuno", keep_legacy=True)
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=reply))

    with pytest.raises(GenerationStageError) as error:
        await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)

    assert error.value.reason_code == "plan_requirements_unmet"
    (event,) = await _preparation_events(db_session)
    rejection = event.payload["rejection"]
    assert rejection["problems"][0].startswith("blocking_conflicts має бути списком")
    assert rejection["plan_fields"]["blocking_conflicts"] == "nessuno"
    assert rejection["plan_fields"]["conflicts"] == list(PROVISIONAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["chapter", "foreign_key", "function"])
async def test_empty_blocking_list_does_not_relax_structure_or_evidence(
    db_session, mutation
):
    doc, job, pack = await _provisional_work(db_session)
    reply = _sorted_reply(doc, blocking=[], keep_legacy=False)
    if mutation == "chapter":
        reply["sections"][0]["title"] = "Different chapter"
    elif mutation == "foreign_key":
        reply["sections"][0]["evidence_keys"] = ["ForeignDOI2025"]
    else:
        reply["sections"][0]["academic_functions"] = ["critical_analysis"]
    ai = SimpleNamespace(call_with_fallback=AsyncMock(return_value=reply))
    before = copy.deepcopy(doc.outline)

    with pytest.raises(GenerationStageError) as error:
        await prepare_final_plan(db_session, doc, job, pack, ai_service=ai)

    assert error.value.reason_code == "plan_requirements_unmet"
    assert doc.outline == before
    (event,) = await _preparation_events(db_session)
    rejection = event.payload["rejection"]
    assert rejection["problems"] and rejection["problem_count"] >= 1
    if mutation == "chapter":
        assert "назви або порядок" in rejection["problems"][0]
    elif mutation == "foreign_key":
        assert rejection["problems"] == [
            "Розділ 1: немає прив'язки до доступних доказів."
        ]
    else:
        assert rejection["problems"][0].startswith("План не покриває")


def test_rejection_evidence_is_bounded_and_never_the_prompt():
    problems = ["x" * (REJECTION_ITEM_CHARS + 50)] * 25
    reply = {
        "academic_plan": {
            "blocking_conflicts": problems,
            "limitations": "not a list",
            "conflicts": [{"nested": 1}],
            "research_question": "must not be copied",
        },
        "sections": [{"title": "kept out"}],
    }
    evidence = rejection_evidence(problems, reply)
    assert len(evidence["problems"]) == 20 and evidence["problem_count"] == 25
    assert all(len(p) == REJECTION_ITEM_CHARS for p in evidence["problems"])
    assert set(evidence["plan_fields"]) == {
        "blocking_conflicts",
        "limitations",
        "conflicts",
    }
    assert evidence["plan_fields"]["limitations"] == "not a list"
    assert evidence["plan_fields"]["conflicts"] == ["{'nested': 1}"]
    assert evidence["response_sha256"] == digest(reply)
    assert "research_question" not in str(evidence) and "kept out" not in str(evidence)
    # A non-object reply (prose) still yields a bounded, truthful record.
    assert rejection_evidence(["p"], "prose") == {
        "problems": ["p"],
        "problem_count": 1,
        "response_sha256": None,
        "plan_fields": {},
    }
