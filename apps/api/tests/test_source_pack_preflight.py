from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.ai_pipeline.source_pack_preflight import (
    invalid_preverified_source_keys,
    preverify_source_pack,
)
from app.services.citation_verifier import VerificationResult, VerificationStatus
from app.services.uploaded_sources import SourcePassage


def _packed(index: int, *, source_type: str | None = "journal-article"):
    source = SourceDoc(
        title=f"Academic source {index}",
        authors=[f"Author {index}"],
        year=2020 + index % 5,
        abstract=f"Evidence {index}",
        doi=f"10.1234/{index}",
        provider="crossref",
        source_type=source_type,
    )
    return PackedSource(source, f"Author{index}2020", 1.0 - index / 1000)


def _verified(packed: PackedSource) -> VerificationResult:
    source = packed.source
    return VerificationResult(
        status=VerificationStatus.VERIFIED,
        doi=source.doi,
        title=source.title,
        authors=source.authors,
        year=source.year,
        abstract=source.abstract,
        provider="crossref",
        match_score=1.0,
    )


@pytest.mark.asyncio
async def test_preflight_keeps_only_verified_target_size():
    candidates = [_packed(index) for index in range(30)]
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        return_value=[_verified(item) for item in candidates]
    )

    outcome = await preverify_source_pack(
        SourcePack(1, "topic", candidates),
        verifier,
        target_size=24,
        minimum_verified=18,
    )

    assert outcome.meets_minimum is True
    assert outcome.verified_count == 24
    assert len(outcome.pack.sources) == 24
    assert all(
        item.source.verification_status == "verified" for item in outcome.pack.sources
    )


@pytest.mark.asyncio
async def test_preflight_distinguishes_transient_underfill():
    candidates = [_packed(index) for index in range(18)]
    results = [_verified(item) for item in candidates[:17]] + [
        VerificationResult(
            status=VerificationStatus.UNRESOLVABLE,
            reason="provider_errors",
        )
    ]
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(return_value=results)

    outcome = await preverify_source_pack(
        SourcePack(1, "topic", candidates),
        verifier,
        target_size=24,
        minimum_verified=18,
    )

    assert outcome.meets_minimum is False
    assert outcome.verified_count == 17
    assert outcome.transient_count == 1


@pytest.mark.asyncio
async def test_automatic_dissertation_is_rejected_but_uploaded_pdf_is_allowed():
    thesis = _packed(1, source_type="dissertation")
    uploaded = PackedSource(
        SourceDoc(
            title="Professor's required thesis",
            authors=["Mario Rossi"],
            year=2021,
            paper_id="uploaded:9",
        ),
        "Rossi2021",
        1.0,
    )
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(return_value=[])

    outcome = await preverify_source_pack(
        SourcePack(1, "topic", [thesis, uploaded]),
        verifier,
        target_size=24,
        minimum_verified=1,
    )

    assert outcome.verified_count == 1
    assert outcome.pack.sources[0].source.provider == "uploaded"
    assert [item.reason for item in outcome.rejected] == ["student_work"]


@pytest.mark.asyncio
async def test_missing_type_with_explicit_thesis_signal_is_rejected():
    thesis = _packed(1, source_type=None)
    thesis.source.title = "A Master's Thesis on Artificial Intelligence"
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(return_value=[])

    outcome = await preverify_source_pack(
        SourcePack(1, "topic", [thesis]),
        verifier,
        target_size=24,
        minimum_verified=1,
    )

    assert outcome.verified_count == 0
    assert [item.reason for item in outcome.rejected] == ["student_work"]
    verifier.verify_sources.assert_awaited_once_with([])


@pytest.mark.asyncio
async def test_unknown_nonempty_type_does_not_hide_explicit_thesis_signal():
    thesis = _packed(1, source_type="posted-content")
    thesis.source.title = "A Master's Thesis on Artificial Intelligence"
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(return_value=[])

    outcome = await preverify_source_pack(
        SourcePack(1, "topic", [thesis]),
        verifier,
        target_size=24,
        minimum_verified=1,
    )

    assert outcome.verified_count == 0
    assert [item.reason for item in outcome.rejected] == ["student_work"]
    verifier.verify_sources.assert_awaited_once_with([])


@pytest.mark.asyncio
async def test_etd_repository_signal_blocks_generic_posted_content_record():
    thesis = _packed(1, source_type="posted-content")
    thesis.source.title = "Artificial Intelligence in Higher Education"
    thesis.source.venue = "Electronic Theses and Dissertations Repository"
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(return_value=[])

    outcome = await preverify_source_pack(
        SourcePack(1, "topic", [thesis]),
        verifier,
        target_size=24,
        minimum_verified=1,
    )

    assert outcome.verified_count == 0
    assert [item.reason for item in outcome.rejected] == ["student_work"]
    verifier.verify_sources.assert_awaited_once_with([])


def test_frozen_pack_proof_requires_verified_status_and_uploaded_file_evidence():
    automatic = _packed(1)
    automatic.source.verification_status = "failed"
    automatic.source.canonical_metadata = {"status": "verified"}
    uploaded = PackedSource(
        SourceDoc(
            title="Required PDF",
            authors=["Mario Rossi"],
            year=2021,
            paper_id="uploaded:9",
            verification_status="verified",
            canonical_metadata={"status": "verified", "provider": "crossref"},
        ),
        "Rossi2021",
        1.0,
    )

    assert invalid_preverified_source_keys(
        SourcePack(1, "topic", [automatic, uploaded])
    ) == [automatic.citation_key, uploaded.citation_key]


@pytest.mark.asyncio
async def test_preflight_deduplicates_provider_aliases_after_verification():
    first = _packed(1)
    alias = PackedSource(
        SourceDoc(
            title=first.source.title,
            authors=["Different Given Author 1"],
            year=first.source.year + 1,
            provider="openalex",
            source_type="article",
        ),
        "Author2022",
        0.8,
    )
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        return_value=[_verified(first), _verified(first)]
    )

    outcome = await preverify_source_pack(
        SourcePack(1, "topic", [first, alias]),
        verifier,
        target_size=24,
        minimum_verified=1,
    )

    assert outcome.verified_count == 1


def test_source_pack_digest_is_order_independent_and_content_sensitive():
    first, second = _packed(1), _packed(2)
    a = SourcePack(1, "topic", [first, second])
    b = SourcePack(1, "topic", [second, first])
    assert a.sha256() == b.sha256()

    second.source.abstract = "changed evidence"
    assert a.sha256() != SourcePack(1, "topic", [first, _packed(2)]).sha256()


def test_source_pack_prompt_and_digest_share_canonical_source_order():
    first, second = _packed(1), _packed(2)
    first.on_topic_score = second.on_topic_score = 0.9
    first.citation_key = "Zulu2021"
    second.citation_key = "Alpha2022"
    forward = SourcePack(1, "topic", [first, second])
    reverse = SourcePack(1, "topic", [second, first])

    assert forward.prompt_block() == reverse.prompt_block()
    assert forward.prompt_block().splitlines()[0].startswith("[Alpha2022]")
    assert forward.sha256() == reverse.sha256()


def test_source_pack_digest_covers_pdf_passage_identity_and_content():
    packed = _packed(1)
    passage = SourcePassage(
        source_file_id=7,
        citation_key=packed.citation_key,
        filename="reading.pdf",
        page_number=3,
        text="Grounded evidence about adaptive learning.",
    )
    baseline = SourcePack(1, "topic", [packed], passages=[passage])

    mutations = [
        SourcePassage(8, passage.citation_key, passage.filename, 3, passage.text),
        SourcePassage(7, "Other2020", passage.filename, 3, passage.text),
        SourcePassage(7, passage.citation_key, "renamed.pdf", 3, passage.text),
        SourcePassage(7, passage.citation_key, passage.filename, 4, passage.text),
        SourcePassage(
            7,
            passage.citation_key,
            passage.filename,
            3,
            "Changed evidence about adaptive learning.",
        ),
    ]
    for changed in mutations:
        assert (
            baseline.sha256()
            != SourcePack(1, "topic", [packed], passages=[changed]).sha256()
        )


def test_pdf_passage_input_order_cannot_change_prompt_or_digest():
    packed = _packed(1)
    passages = [
        SourcePassage(
            7,
            packed.citation_key,
            "reading.pdf",
            2,
            "Adaptive learning evidence from the second page.",
        ),
        SourcePassage(
            7,
            packed.citation_key,
            "reading.pdf",
            1,
            "Adaptive learning evidence from the first page.",
        ),
    ]
    forward = SourcePack(1, "topic", [packed], passages=passages)
    reverse = SourcePack(1, "topic", [packed], passages=list(reversed(passages)))

    assert forward.sha256() == reverse.sha256()
    assert forward.prompt_block(query="adaptive learning") == reverse.prompt_block(
        query="adaptive learning"
    )
