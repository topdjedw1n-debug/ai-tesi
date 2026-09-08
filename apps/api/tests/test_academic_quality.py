"""Academic brief, immutable evidence and durable whole-work release regression."""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.document import Document, DocumentProvenance
from app.services.academic_context import (
    ACADEMIC_FUNCTIONS,
    academic_context,
    previous_analysis,
)
from app.services.academic_review import (
    academic_release_verdict,
    outline_problems,
    review_binding,
    run_academic_review,
    validate_review,
)
from app.services.ai_pipeline.prompt_builder import PromptBuilder
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.ai_pipeline.source_pack_preflight import preverify_source_pack
from app.services.ai_service import AIService
from app.services.claim_verifier import ClaimVerifier, _source_abstract
from app.services.generation_contract import generation_contract_payload
from app.services.production_case_service import RELEASE_GATE_CONFIG
from app.services.source_evidence import (
    evidence_text,
    freeze_evidence,
    preserve_evidence,
)
from app.services.task_contract import task_contract_sha256
from tests.test_source_pack_preflight import _packed, _verified


def example():
    doc = Document(
        id=71,
        user_id=1,
        title="Nursing review",
        topic="Nursing care evidence",
        language="it",
        work_type="tesi_magistrale",
        target_pages=18,
        citation_style="apa",
        ai_provider="anthropic",
        ai_model="unchanged-writer",
        requirements_file_processed=True,
        additional_requirements="Preserve exactly these four chapters, with no additional chapters.",
        content="Comparison of study designs and populations. Results differ by setting.",
        status="completed",
        docx_sha256="a" * 64,
        docx_path="documents/71/final.docx",
    )
    doc.outline = {
        "academic_plan": {
            "research_question": "Which care findings transfer between settings?",
            "objectives": ["Compare designs and evidence limitations"],
        },
        "sections": [
            {
                "title": f"Fixed chapter {i}",
                "estimated_words": 1000,
                "academic_functions": (
                    list(ACADEMIC_FUNCTIONS) if i == 1 else ["critical_analysis"]
                ),
                "main_points": ["Comparison of study designs and populations"],
                "evidence_keys": ["Author2024"],
            }
            for i in range(1, 5)
        ],
    }
    source = SourceDoc(
        "Care study",
        ["Author"],
        2024,
        abstract="Comparison of study designs and populations. Results differ by setting.",
        doi="10.1000/care",
        provider="crossref",
    )
    freeze_evidence(source, [], "Author2024")
    pack = SourcePack(71, doc.topic, [PackedSource(source, "Author2024", 1)])
    job = SimpleNamespace(
        id=17,
        request_payload={"generation_contract_sha256": "b" * 64},
        source_pack_sha256=pack.sha256(),
    )
    return doc, job, pack


def verdict(passed=True):
    return {
        "functions": {
            key: {
                "satisfied": passed,
                "evidence_quote": "Comparison of study designs and populations",
                "reason": "Specific substantive review",
            }
            for key in ACADEMIC_FUNCTIONS
        },
        "requirements_satisfied": passed,
        "source_coverage": [
            {
                "section_index": i,
                "supported": passed,
                "source_keys": ["Author2024"],
                "reason": "Evidence supports comparison",
            }
            for i in range(1, 5)
        ],
        "issues": (
            []
            if passed
            else [{"severity": "major", "reason": "No genuine comparison in chapter 2"}]
        ),
    }


def test_brief_reaches_outline_writer_and_preserves_contract_inputs():
    doc, _, pack = example()
    original = generation_contract_payload(doc, None, doc.additional_requirements)
    sha = task_contract_sha256(doc)
    master = academic_context(doc)
    service = AIService(None)
    master_prompts = [
        service._build_outline_prompt(doc),
        service._build_outline_prompt(doc, source_pack=pack),
        PromptBuilder.build_section_prompt(doc, "Chapter", 1),
    ]
    assert all("tesi_magistrale" in p for p in master_prompts)
    assert all(doc.additional_requirements in p for p in master_prompts)
    doc.work_type = "tesi_triennale"
    bachelor = academic_context(doc)
    assert master["level"] != bachelor["level"]
    assert all(
        "tesi_triennale" in p
        for p in [
            service._build_outline_prompt(doc),
            service._build_outline_prompt(doc, source_pack=pack),
            PromptBuilder.build_section_prompt(doc, "Chapter", 1),
        ]
    )
    doc.work_type = "tesi_magistrale"
    assert task_contract_sha256(doc) == sha
    assert (
        generation_contract_payload(doc, None, doc.additional_requirements) == original
    )


def test_previous_analysis_keeps_findings_beyond_200_chars():
    finding = "Study B contradicts Study A on the measured outcome [Author2024]."
    result = previous_analysis([{"title": "Analysis", "content": "a" * 900 + finding}])
    assert finding in result
    assert "truncated" in previous_analysis([{"content": "a" * 130000}])


def test_outline_must_cover_functions_and_each_chapter_evidence():
    doc, _, pack = example()
    assert outline_problems(doc.outline, set(pack.keys())) == []
    doc.outline["sections"][0]["academic_functions"] = ["critical_analysis"]
    assert outline_problems(doc.outline, set(pack.keys()))
    doc.outline["sections"][0]["evidence_keys"] = ["Invented2024"]
    assert any("1:" in p for p in outline_problems(doc.outline, set(pack.keys())))


def test_shared_evidence_is_exact_and_survives_identity_reverification():
    doc, _, pack = example()
    source = pack.sources[0].source
    source.abstract = (
        "a" * 1600
        + " Distinct finding only after the legacy checker limit. "
        + "b" * 1600
    )
    freeze_evidence(source, [], "Author2024")
    sha = pack.sha256()
    writer = pack.prompt_block(query="care")
    source.canonical_metadata = preserve_evidence(
        source, {"abstract": "A different verifier abstract"}
    )
    assert evidence_text(source) in writer
    assert _source_abstract(source) == evidence_text(source)
    checker = ClaimVerifier(MagicMock(), abstract_max_chars=10)
    source.id = 1
    source.citation_key = "Author2024"
    claims = checker.extract_claims(
        "This is the supported care finding [Author2024].", [source]
    )
    assert claims[0].frozen_evidence
    assert "Distinct finding" in checker._build_batch_prompt(claims)
    assert pack.sha256() == sha
    source.canonical_metadata["academic_evidence"]["text"] += "tampered"
    assert _source_abstract(source) is None
    assert pack.sha256() != sha


@pytest.mark.asyncio
async def test_preflight_enriches_same_identity_and_excludes_no_evidence():
    good, unavailable, mismatch = (_packed(i) for i in range(3))
    for p in [good, unavailable, mismatch]:
        p.source.abstract = None
    richer = copy.deepcopy(good.source)
    richer.abstract = "Actual abstract evidence"
    richer.provider = "openalex"
    unrelated = copy.deepcopy(mismatch.source)
    unrelated.doi = "10.1000/other"
    unrelated.title = "Unrelated work"
    unrelated.abstract = "Wrong source"
    retriever = MagicMock()
    retriever.search_openalex = AsyncMock(side_effect=[[richer], [], [unrelated]])
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        return_value=[_verified(p) for p in [good, unavailable, mismatch]]
    )
    outcome = await preverify_source_pack(
        SourcePack(1, "topic", [good, unavailable, mismatch]),
        verifier,
        target_size=3,
        minimum_verified=1,
        require_evidence=True,
        evidence_retriever=retriever,
    )
    assert len(outcome.pack.sources) == 1
    assert evidence_text(outcome.pack.sources[0].source) == "Actual abstract evidence"
    assert len(outcome.rejected) == 2
    assert (
        outcome.provenance_payload(top_up_attempted=False)["retrieval_trace"][0][
            "purpose"
        ]
        == "missing_evidence"
    )


@pytest.mark.parametrize(
    "mutation",
    ["missing", "quote", "unknown_source", "duplicate_section", "string_bool"],
)
def test_incomplete_or_invented_review_cannot_pass(mutation):
    result = verdict()
    if mutation == "missing":
        result["functions"].pop("review_method")
    if mutation == "quote":
        result["functions"]["review_method"][
            "evidence_quote"
        ] = "Invented verbatim excerpt"
    if mutation == "unknown_source":
        result["source_coverage"][0]["source_keys"] = ["Fake2024"]
    if mutation == "duplicate_section":
        result["source_coverage"][0]["section_index"] = 2
    if mutation == "string_bool":
        result["requirements_satisfied"] = "true"
    with pytest.raises(ValueError):
        validate_review(result, example()[0].content, 4, {"Author2024"})


async def seed_review(db):
    doc, job, pack = example()
    db.add(doc)
    db.add(
        DocumentProvenance(
            document_id=doc.id,
            stage="retrieval",
            event_type="source_pack_preflight",
            payload={
                "sha256": pack.sha256(),
                "retrieval_trace": [
                    {
                        "provider": "search_openalex",
                        "query": "care",
                        "retrieved_at": "2026-09-08T00:00:00+00:00",
                        "status": "returned",
                        "count": 1,
                    }
                ],
                "candidates": 1,
                "verified": 1,
                "rejected_by_reason": {},
            },
        )
    )
    await db.commit()
    return doc, job, pack


@pytest.mark.asyncio
@pytest.mark.parametrize("passed", [True, False])
async def test_review_is_durable_reused_and_does_not_rewrite(db_session, passed):
    doc, job, pack = await seed_review(db_session)
    original = doc.content

    async def call(*args, **kwargs):
        async with AsyncSessionLocal() as observer:
            started = (
                await observer.execute(
                    select(DocumentProvenance).where(
                        DocumentProvenance.event_type == "academic_review_started"
                    )
                )
            ).scalar_one()
            assert started.payload["binding"]["text_sha256"]
        assert len(kwargs["chain_override"]) == 1
        return verdict(passed)

    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(side_effect=call)
    result = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    assert result["status"] == ("passed" if passed else "failed")
    assert doc.content == original
    again = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    assert again == result and ai.call_with_fallback.await_count == 1
    doc.content += " Changed after review."
    stale = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    assert stale["status"] == "unchecked" and ai.call_with_fallback.await_count == 1


@pytest.mark.asyncio
async def test_crash_checkpoint_prevents_second_paid_attempt(db_session):
    doc, job, pack = await seed_review(db_session)
    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await run_academic_review(
            db_session, doc, job, pack, kind="whole", ai_service=ai
        )
    outcome = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    assert outcome["status"] == "unchecked" and ai.call_with_fallback.await_count == 1


@pytest.mark.asyncio
async def test_provider_failure_is_unchecked_not_pass(db_session):
    doc, job, pack = await seed_review(db_session)
    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(side_effect=TimeoutError())
    outcome = await run_academic_review(
        db_session, doc, job, pack, kind="whole", ai_service=ai
    )
    assert outcome["status"] == "unchecked"
    assert (
        await run_academic_review(
            db_session, doc, job, pack, kind="whole", ai_service=ai
        )
    ) == outcome
    assert ai.call_with_fallback.await_count == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "text",
        "outline",
        "requirements",
        "source",
        "file",
        "path",
        "job",
        "policy",
        "failed",
        "unchecked",
        "missing",
    ],
)
def test_academic_gate_requires_current_review_and_exact_file(mutation):
    doc, job, pack = example()
    source_sha = pack.sha256()
    binding = review_binding(doc, job, source_sha, kind="whole")
    review = {"binding": binding, "status": "passed"}
    artifact = {
        "binding": copy.deepcopy(binding),
        "docx_sha256": doc.docx_sha256,
        "docx_path": doc.docx_path,
    }
    events = [
        SimpleNamespace(event_type="academic_review", payload=review),
        SimpleNamespace(event_type="academic_review_artifact", payload=artifact),
    ]
    if mutation == "text":
        doc.content += " New text"
    if mutation == "outline":
        doc.outline["sections"][0]["main_points"] = ["different"]
    if mutation == "requirements":
        doc.additional_requirements += " extra"
    if mutation == "source":
        source_sha = "c" * 64
    if mutation == "file":
        doc.docx_sha256 = "d" * 64
    if mutation == "path":
        doc.docx_path = "other.docx"
    if mutation == "job":
        job.id += 1
    if mutation == "policy":
        review["binding"]["policy_version"] = "old"
    if mutation in {"failed", "unchecked"}:
        review["status"] = mutation
    if mutation == "missing":
        events = []
    status, _, _ = academic_release_verdict(doc, job, events, source_sha)
    assert (status == "passed") == (mutation == "none")
    assert RELEASE_GATE_CONFIG["academic_quality"]["override_allowed"] is False


def test_review_quote_matches_visible_markdown_and_normalized_whitespace():
    result = verdict()
    source = (
        "Comparison of **study designs**\nand   populations. Results differ by setting."
    )
    assert validate_review(result, source, 4, {"Author2024"})["status"] == "passed"


@pytest.mark.parametrize(
    "query",
    ["neonatal nursing thermoregulation", "assistenza infermieristica neonatale"],
)
def test_uploaded_evidence_uses_relevance_or_explicit_cross_language_fallback(query):
    from app.services.uploaded_sources import SourcePassage, score_passage

    source = SourceDoc(
        "Uploaded textbook",
        ["Author"],
        2024,
        abstract="Title page and contents",
        paper_id="uploaded:1",
    )
    passages = [
        SourcePassage(1, "Author2024", "book.pdf", 1, "Title page and contents"),
        SourcePassage(
            1,
            "Author2024",
            "book.pdf",
            42,
            "Neonatal nursing thermoregulation evidence compares skin temperature outcomes.",
        ),
    ]
    assert freeze_evidence(source, passages, "Author2024", query=query)
    assert "thermoregulation" in evidence_text(source)
    origins = source.canonical_metadata["academic_evidence"]["origins"]
    if query.startswith("neonatal"):
        assert "Title page" not in evidence_text(source)
        assert origins[0]["page_number"] == 42
        assert origins[0]["selection"] == "lexical_relevance"
    else:
        assert all(score_passage(query, p.text) == 0 for p in passages)
        assert [p["page_number"] for p in origins] == [1, 42]
        assert all(p["selection"] == "page_order_fallback" for p in origins)
    assert _source_abstract(source) == evidence_text(source)
