"""
Tests for the claim-faithfulness verifier (advisory pass).

Unit layer: ClaimVerifier with a mocked LLM (AIService.call_with_fallback) -
supported / unsupported verdicts, missing abstract (no LLM call), budget cap,
batching, fail-open on LLM errors.

Pipeline layer: generate_full_document with CLAIM_VERIFICATION_ENABLED -
verdicts land in DocumentSection.claim_verification + provenance ledger, and
unsupported claims do NOT block the document.
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.auth import User
from app.models.document import (
    Document,
    DocumentProvenance,
    DocumentSection,
    DocumentSource,
)
from app.services.background_jobs import BackgroundJobService
from app.services.citation_verifier import VerificationResult, VerificationStatus
from app.services.claim_verifier import (
    REASON_BUDGET,
    REASON_LLM_FAILED,
    REASON_NO_ABSTRACT,
    REASON_NO_SOURCE,
    ClaimVerifier,
    summarize_verdicts,
)

# ----------------------------------------------------------------------
# Unit-test helpers
# ----------------------------------------------------------------------

ABSTRACT = (
    "We propose the Transformer, a network architecture based solely on "
    "attention mechanisms, dispensing with recurrence and convolutions."
)


def make_source(
    source_id=1,
    title="Attention Is All You Need",
    authors=None,
    year=2017,
    abstract=None,
    canonical_metadata=None,
):
    source = DocumentSource(
        document_id=1,
        title=title,
        authors=authors if authors is not None else ["Ashish Vaswani"],
        year=year,
        abstract=abstract,
        canonical_metadata=canonical_metadata,
    )
    source.id = source_id
    return source


def make_ai(response=None, side_effect=None):
    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(return_value=response, side_effect=side_effect)
    return ai


def llm_verdicts(*entries):
    """Response shape when the model returned valid JSON (parsed by AIService)"""
    return {
        "verdicts": [
            {"id": i, "verdict": verdict, "explanation": explanation}
            for i, (verdict, explanation) in enumerate(entries, start=1)
        ],
        "tokens_used": 42,
    }


CONTENT_ONE_CLAIM = "Transformers dominate NLP [Vaswani, 2017]. Plain sentence."


# ----------------------------------------------------------------------
# Unit: verdicts
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supported_claim():
    source = make_source(canonical_metadata={"abstract": ABSTRACT})
    ai = make_ai(llm_verdicts(("supported", "The abstract directly states this.")))
    verifier = ClaimVerifier(ai)

    claims = verifier.extract_claims(CONTENT_ONE_CLAIM, [source])
    assert len(claims) == 1
    assert claims[0].citation_text == "[Vaswani, 2017]"
    assert claims[0].source_id == 1
    assert claims[0].abstract == ABSTRACT

    verdicts, llm_used = await verifier.verify_claims(claims, budget=10)

    assert llm_used == 1
    assert verdicts[0].verdict == "supported"
    assert verdicts[0].explanation == "The abstract directly states this."
    assert verdicts[0].checked_by_llm is True

    # Prompt contains both the abstract and the cited sentence
    prompt = ai.call_with_fallback.call_args[0][0]
    assert ABSTRACT in prompt
    assert "Transformers dominate NLP" in prompt


@pytest.mark.asyncio
async def test_unsupported_claim():
    source = make_source(canonical_metadata={"abstract": ABSTRACT})
    ai = make_ai(
        llm_verdicts(("unsupported", "The abstract says nothing about NLP dominance."))
    )
    verifier = ClaimVerifier(ai)

    verdicts, llm_used = await verifier.verify_claims(
        verifier.extract_claims(CONTENT_ONE_CLAIM, [source]), budget=10
    )

    assert llm_used == 1
    assert verdicts[0].verdict == "unsupported"
    assert "nothing about" in verdicts[0].explanation
    assert verdicts[0].checked_by_llm is True

    summary = summarize_verdicts(verdicts)
    assert summary["counts"] == {"unsupported": 1}
    assert summary["checked"] == 1
    assert summary["claims"][0]["verdict"] == "unsupported"


@pytest.mark.asyncio
async def test_missing_abstract_marks_uncertain_without_llm_call():
    # No canonical_metadata abstract AND no RAG abstract
    source = make_source(abstract=None, canonical_metadata={"title": "x"})
    ai = make_ai()
    verifier = ClaimVerifier(ai)

    verdicts, llm_used = await verifier.verify_claims(
        verifier.extract_claims(CONTENT_ONE_CLAIM, [source]), budget=10
    )

    assert llm_used == 0
    assert verdicts[0].verdict == "uncertain"
    assert verdicts[0].explanation == REASON_NO_ABSTRACT
    assert verdicts[0].checked_by_llm is False
    ai.call_with_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_unmatched_citation_marks_uncertain_without_llm_call():
    source = make_source()  # Vaswani 2017
    ai = make_ai()
    verifier = ClaimVerifier(ai)

    content = "Quantum supremacy is near [Nobody, 1999]."
    verdicts, llm_used = await verifier.verify_claims(
        verifier.extract_claims(content, [source]), budget=10
    )

    assert llm_used == 0
    assert verdicts[0].verdict == "uncertain"
    assert verdicts[0].explanation == REASON_NO_SOURCE
    ai.call_with_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_abstract_prefers_canonical_metadata_over_rag():
    source = make_source(
        abstract="RAG abstract", canonical_metadata={"abstract": "Canonical abstract"}
    )
    verifier = ClaimVerifier(make_ai(llm_verdicts(("supported", "ok"))))

    claims = verifier.extract_claims(CONTENT_ONE_CLAIM, [source])
    assert claims[0].abstract == "Canonical abstract"


# ----------------------------------------------------------------------
# Unit: budget and batching
# ----------------------------------------------------------------------

CONTENT_THREE_CLAIMS = (
    "Attention replaced recurrence [Vaswani, 2017]. "
    "Self-attention scales well [Vaswani, 2017]! "
    "Transformers train faster [Vaswani, 2017]."
)


@pytest.mark.asyncio
async def test_budget_exceeded_marks_remaining_uncertain():
    source = make_source(canonical_metadata={"abstract": ABSTRACT})
    ai = make_ai(llm_verdicts(("supported", "ok")))
    verifier = ClaimVerifier(ai)

    claims = verifier.extract_claims(CONTENT_THREE_CLAIMS, [source])
    assert len(claims) == 3

    verdicts, llm_used = await verifier.verify_claims(claims, budget=1)

    assert llm_used == 1
    assert ai.call_with_fallback.call_count == 1
    # Only the first claim went to the LLM
    prompt = ai.call_with_fallback.call_args[0][0]
    assert "Attention replaced recurrence" in prompt
    assert "Self-attention scales well" not in prompt

    assert verdicts[0].verdict == "supported"
    assert verdicts[0].checked_by_llm is True
    for verdict in verdicts[1:]:
        assert verdict.verdict == "uncertain"
        assert verdict.explanation == REASON_BUDGET
        assert verdict.checked_by_llm is False


@pytest.mark.asyncio
async def test_zero_budget_skips_llm_entirely():
    source = make_source(canonical_metadata={"abstract": ABSTRACT})
    ai = make_ai()
    verifier = ClaimVerifier(ai)

    verdicts, llm_used = await verifier.verify_claims(
        verifier.extract_claims(CONTENT_ONE_CLAIM, [source]), budget=0
    )

    assert llm_used == 0
    assert verdicts[0].explanation == REASON_BUDGET
    ai.call_with_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_batching_multiple_claims_in_one_prompt():
    """Three claims citing the same source -> ONE LLM call, ONE abstract block"""
    source = make_source(canonical_metadata={"abstract": ABSTRACT})
    # Model answered as plain text containing JSON (the "content" parse path)
    ai = make_ai(
        {
            "content": (
                'Here is my analysis:\n{"verdicts": ['
                '{"id": 1, "verdict": "supported", "explanation": "a"},'
                '{"id": 2, "verdict": "uncertain", "explanation": "b"},'
                '{"id": 3, "verdict": "unsupported", "explanation": "c"}]}'
            ),
            "tokens_used": 100,
        }
    )
    verifier = ClaimVerifier(ai)

    claims = verifier.extract_claims(CONTENT_THREE_CLAIMS, [source])
    verdicts, llm_used = await verifier.verify_claims(claims, budget=50)

    assert llm_used == 3
    assert ai.call_with_fallback.call_count == 1  # batched into one prompt

    prompt = ai.call_with_fallback.call_args[0][0]
    assert prompt.count(ABSTRACT) == 1  # abstract deduplicated
    # Claim lines bind each claim to its source label AND title
    assert '1. (source S1: "Attention Is All You Need")' in prompt
    assert '3. (source S1: "Attention Is All You Need")' in prompt

    assert [v.verdict for v in verdicts] == ["supported", "uncertain", "unsupported"]
    assert all(v.checked_by_llm for v in verdicts)


@pytest.mark.asyncio
async def test_constructor_overrides_batch_size_and_abstract_limit():
    source = make_source(canonical_metadata={"abstract": "ABCDEFGHIJ"})
    ai = make_ai(llm_verdicts(("supported", "ok"), ("supported", "ok")))
    verifier = ClaimVerifier(ai, batch_size=2, abstract_max_chars=5)

    claims = verifier.extract_claims(CONTENT_THREE_CLAIMS, [source])
    verdicts, llm_used = await verifier.verify_claims(claims, budget=50)

    assert llm_used == 3
    assert ai.call_with_fallback.call_count == 2
    first_prompt = ai.call_with_fallback.call_args_list[0].args[0]
    assert "Abstract: ABCDE" in first_prompt
    assert "ABCDEF" not in first_prompt
    assert [v.verdict for v in verdicts] == ["supported", "supported", "supported"]


@pytest.mark.asyncio
async def test_llm_failure_fails_open_to_uncertain():
    source = make_source(canonical_metadata={"abstract": ABSTRACT})
    ai = make_ai(side_effect=RuntimeError("all providers down"))
    verifier = ClaimVerifier(ai)

    verdicts, llm_used = await verifier.verify_claims(
        verifier.extract_claims(CONTENT_ONE_CLAIM, [source]), budget=10
    )

    # Budget is still consumed (no retry storms), verdicts degrade gracefully
    assert llm_used == 1
    assert verdicts[0].verdict == "uncertain"
    assert verdicts[0].explanation == REASON_LLM_FAILED
    assert verdicts[0].checked_by_llm is False


# ----------------------------------------------------------------------
# Pipeline integration: advisory pass never blocks
# ----------------------------------------------------------------------

SOURCE_A = {
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani"],
    "year": 2017,
    "abstract": ABSTRACT,
    "paper_id": None,
    "venue": "NeurIPS",
    "citation_count": 100,
    "url": None,
    "doi": "10.5555/attention",
}


def make_settings(**overrides) -> Settings:
    defaults = {
        "QUALITY_GATES_ENABLED": False,
        "QUALITY_MAX_REGENERATE_ATTEMPTS": 0,
        "CITATION_VERIFICATION_ENABLED": True,
        "CITATION_VERIFICATION_POLICY": "mark_only",
        "PROVENANCE_LEDGER_ENABLED": True,
        "CLAIM_VERIFICATION_ENABLED": True,
        "CLAIM_VERIFICATION_MAX_CHECKS": 50,
    }
    defaults.update(overrides)
    return Settings(**defaults)


async def seed_document(db_session):
    user = User(email="claims-test@example.com", full_name="Claims Tester")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    document = Document(
        user_id=user.id,
        title="Claims Test Thesis",
        topic="AI in Education",
        status="draft",
        language="en",
        ai_provider="openai",
        ai_model="gpt-4",
        outline={"sections": [{"title": "Introduction"}]},
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return user, document


def pipeline_harness(stack: ExitStack, db_session, mock_redis, *, claim_llm_response):
    """Trimmed harness (mirrors test_provenance_ledger) + mocked AIService"""
    gen_class = stack.enter_context(
        patch("app.services.background_jobs.SectionGenerator")
    )
    generator = MagicMock()
    generator.generate_section = AsyncMock(
        return_value={
            "section_title": "Introduction",
            "section_index": 1,
            "content": "Transformers dominate NLP [Vaswani, 2017].",
            "citations": [],
            "bibliography": ["ref"],
            "sources_used": 1,
            "humanized": False,
            "cited_sources": [SOURCE_A],
        }
    )
    gen_class.return_value = generator

    humanizer_class = stack.enter_context(
        patch("app.services.background_jobs.Humanizer")
    )
    humanizer = MagicMock()
    humanizer.humanize = AsyncMock(side_effect=lambda *a, **k: k.get("text", "x"))
    humanizer_class.return_value = humanizer

    quality_class = stack.enter_context(
        patch("app.services.background_jobs.QualityValidator")
    )
    quality_validator = MagicMock()
    quality_validator.validate_section = AsyncMock(
        return_value={"overall_score": 85.0, "issues": []}
    )
    quality_class.return_value = quality_validator

    stack.enter_context(
        patch(
            "app.services.background_jobs._check_grammar_quality",
            AsyncMock(return_value=(95.0, 0, "passed", None)),
        )
    )
    stack.enter_context(
        patch(
            "app.services.background_jobs._check_plagiarism_quality",
            AsyncMock(return_value=(5.0, 95.0, "passed", None)),
        )
    )
    stack.enter_context(
        patch(
            "app.services.background_jobs._check_ai_detection_quality",
            AsyncMock(
                side_effect=lambda content, *a, **k: (
                    20.0,
                    content,
                    "mock",
                    "passed",
                    None,
                )
            ),
        )
    )

    manager = stack.enter_context(patch("app.services.background_jobs.manager"))
    manager.send_progress = AsyncMock()

    doc_service_class = stack.enter_context(
        patch("app.services.background_jobs.DocumentService")
    )
    doc_service = MagicMock()
    doc_service.export_document = AsyncMock(
        return_value={"download_url": "https://example.com/doc.docx", "format": "docx"}
    )
    doc_service_class.return_value = doc_service

    stack.enter_context(
        patch(
            "app.services.background_jobs.get_redis",
            AsyncMock(return_value=mock_redis),
        )
    )

    session_class = stack.enter_context(
        patch("app.services.background_jobs.database.AsyncSessionLocal")
    )
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=db_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    session_class.return_value = mock_session

    verifier_class = stack.enter_context(
        patch("app.services.background_jobs.CitationVerifier")
    )
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        side_effect=lambda inputs: [
            VerificationResult(
                status=VerificationStatus.VERIFIED,
                title=s.title,
                match_score=1.0,
                provider="crossref",
            )
            for s in inputs
        ]
    )
    verifier_class.return_value = verifier

    # Mocked LLM for the claim verifier (AIService.call_with_fallback)
    ai_service_class = stack.enter_context(
        patch("app.services.background_jobs.AIService")
    )
    ai_service = MagicMock()
    ai_service.call_with_fallback = AsyncMock(return_value=claim_llm_response)
    ai_service_class.return_value = ai_service

    stack.enter_context(patch("app.services.notification_service.notification_service"))

    return {"ai_service": ai_service, "export_document": doc_service.export_document}


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.mark.asyncio
async def test_pipeline_unsupported_claims_do_not_block(
    db_session, mock_redis, monkeypatch
):
    """Advisory pass: unsupported verdicts are recorded, document completes"""
    monkeypatch.setattr("app.services.background_jobs.settings", make_settings())
    user, document = await seed_document(db_session)
    document_id = document.id

    with ExitStack() as stack:
        mocks = pipeline_harness(
            stack,
            db_session,
            mock_redis,
            claim_llm_response=llm_verdicts(
                ("unsupported", "The abstract does not mention NLP dominance.")
            ),
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )
        assert mocks["export_document"].call_count == 1  # export not blocked
        assert mocks["ai_service"].call_with_fallback.call_count == 1

    refreshed = (
        await db_session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one()
    assert refreshed.status == "completed"  # unsupported claims never block

    section = (
        await db_session.execute(
            select(DocumentSection).where(
                DocumentSection.document_id == document_id,
                DocumentSection.section_index == 1,
            )
        )
    ).scalar_one()
    assert section.claim_verification is not None
    assert section.claim_verification["total"] == 1
    assert section.claim_verification["checked"] == 1
    assert section.claim_verification["counts"] == {"unsupported": 1}
    assert section.claim_verification["claims"][0]["citation"] == "[Vaswani, 2017]"

    events = (
        (
            await db_session.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.document_id == document_id)
                .order_by(DocumentProvenance.id.asc())
            )
        )
        .scalars()
        .all()
    )
    by_type = {e.event_type: e.payload for e in events}
    assert by_type["claims_verified"]["counts"] == {"unsupported": 1}
    assert by_type["claims_verified"]["unsupported"][0]["citation"] == "[Vaswani, 2017]"
    assert by_type["claim_check_summary"]["total_claims"] == 1
    assert by_type["claim_check_summary"]["budget_exhausted"] is False

    types = [e.event_type for e in events]
    assert types.index("verification_summary") < types.index("claims_verified")
    assert types.index("claims_verified") < types.index("exported")


@pytest.mark.asyncio
async def test_pipeline_claim_flag_off_writes_nothing(
    db_session, mock_redis, monkeypatch
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(CLAIM_VERIFICATION_ENABLED=False),
    )
    user, document = await seed_document(db_session)
    document_id = document.id

    with ExitStack() as stack:
        mocks = pipeline_harness(
            stack, db_session, mock_redis, claim_llm_response=llm_verdicts()
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )
        mocks["ai_service"].call_with_fallback.assert_not_called()

    section = (
        await db_session.execute(
            select(DocumentSection).where(DocumentSection.document_id == document_id)
        )
    ).scalar_one()
    assert section.claim_verification is None

    event_types = {
        e.event_type
        for e in (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.document_id == document_id
                )
            )
        )
        .scalars()
        .all()
    }
    assert "claims_verified" not in event_types
    assert "claim_check_summary" not in event_types


@pytest.mark.asyncio
async def test_pipeline_blocking_unsupported_claims_block_export(
    db_session, mock_redis, monkeypatch
):
    """Blocking mode: an unsupported cited claim blocks export (failed_quality)."""
    from app.core.exceptions import CitationIntegrityError

    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(CLAIM_VERIFICATION_BLOCKING=True),
    )
    user, document = await seed_document(db_session)
    document_id = document.id

    with ExitStack() as stack:
        mocks = pipeline_harness(
            stack,
            db_session,
            mock_redis,
            claim_llm_response=llm_verdicts(
                ("unsupported", "The abstract does not mention NLP dominance.")
            ),
        )
        with pytest.raises(CitationIntegrityError):
            await BackgroundJobService.generate_full_document(
                document_id=document_id, user_id=user.id
            )
        # Export must NOT run when the claim gate blocks.
        assert mocks["export_document"].call_count == 0

    refreshed = (
        await db_session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one()
    assert refreshed.status == "failed_quality"

    event_types = {
        e.event_type
        for e in (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.document_id == document_id
                )
            )
        )
        .scalars()
        .all()
    }
    assert "claim_integrity_gate_failed" in event_types


# ----------------------------------------------------------------------
# Unit: source-pack citation keys (grounded path), e.g. "[Ciofalo2024]"
# ----------------------------------------------------------------------


def make_pack_source(source_id=1, citation_key="Ciofalo2024", **kwargs):
    source = make_source(source_id=source_id, **kwargs)
    source.citation_key = citation_key
    return source


def test_extract_claims_matches_pack_keys_by_citation_key():
    source = make_pack_source(
        source_id=7, citation_key="Ciofalo2024", abstract=ABSTRACT
    )
    verifier = ClaimVerifier(make_ai())
    claims = verifier.extract_claims(
        "L'IA trasforma la didattica [Ciofalo2024]. Frase neutra.", [source]
    )

    assert len(claims) == 1
    assert claims[0].citation_text == "[Ciofalo2024]"
    assert claims[0].source_id == 7
    assert claims[0].abstract == ABSTRACT


def test_extract_claims_pack_key_match_is_case_insensitive():
    source = make_pack_source(source_id=3, citation_key="DeSimone2024")
    verifier = ClaimVerifier(make_ai())
    claims = verifier.extract_claims("Un caso noto [desimone2024].", [source])

    assert len(claims) == 1
    assert claims[0].source_id == 3


def test_extract_claims_multiple_pack_keys_in_one_bracket():
    sources = [
        make_pack_source(source_id=1, citation_key="Ciofalo2024"),
        make_pack_source(source_id=2, citation_key="Corsi2025"),
    ]
    verifier = ClaimVerifier(make_ai())
    claims = verifier.extract_claims(
        "Due studi concordano [Ciofalo2024; Corsi2025].", sources
    )

    assert [c.source_id for c in claims] == [1, 2]


def test_extract_claims_unknown_pack_key_yields_unmatched_claim():
    verifier = ClaimVerifier(make_ai())
    claims = verifier.extract_claims("Fonte fantasma [Inventato2099].", [])

    assert len(claims) == 1
    assert claims[0].source_id is None
    assert claims[0].abstract is None


def test_extract_claims_legacy_and_pack_formats_do_not_double_count():
    pack_source = make_pack_source(
        source_id=1,
        citation_key="Ciofalo2024",
        authors=["Giovanni Ciofalo"],
        year=2024,
    )
    legacy_source = make_source(source_id=2, authors=["Ashish Vaswani"], year=2017)
    verifier = ClaimVerifier(make_ai())
    claims = verifier.extract_claims(
        "Prima frase [Ciofalo2024]. Seconda frase [Vaswani, 2017].",
        [pack_source, legacy_source],
    )

    assert len(claims) == 2
    assert {c.source_id for c in claims} == {1, 2}
