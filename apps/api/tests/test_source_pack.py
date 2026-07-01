"""Unit tests for the upfront topic-locked source pack (source_pack.py)."""

from unittest.mock import AsyncMock

import pytest

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import (
    PackedSource,
    SourcePack,
    SourcePackBuilder,
)


def _edu_source(title, authors=("Rossi",), year=2021, abstract=""):
    return SourceDoc(title=title, authors=list(authors), year=year, abstract=abstract)


def test_off_topic_corporate_source_rejected_for_education_topic():
    """The concrete failure case: corporate-training source scores below an
    on-topic school-education source."""
    builder = SourcePackBuilder()
    from app.services.ai_pipeline.text_utils import content_tokens

    topic_terms = content_tokens(
        "the impact of artificial intelligence on education in schools"
    )
    domain = builder._detect_domain(topic_terms)
    assert domain == "education"

    edu = _edu_source(
        "Artificial intelligence in classroom teaching and student learning",
        abstract="AI personalizes learning for students in schools.",
    )
    corp = _edu_source(
        "AI in corporate training for employee onboarding in the workplace",
        authors=["Vittori"],
        year=2026,
        abstract="AI for corporate aziendale employee training in enterprises.",
    )

    s_edu = builder._on_topic_score(edu, topic_terms, domain)
    s_corp = builder._on_topic_score(corp, topic_terms, domain)

    assert s_edu > s_corp
    assert s_corp < 0.35  # rejected by the default threshold
    assert s_edu >= 0.35


def test_citation_key_stability_and_collision_suffix():
    builder = SourcePackBuilder()
    # Two different sources, same author+year -> collision -> suffix.
    a = _edu_source("First study on AI tutoring", authors=["Rossi"], year=2021)
    b = _edu_source("Second study on AI tutoring", authors=["Rossi"], year=2021)
    packed = builder._assign_keys([(0.9, a), (0.8, b)])
    keys = sorted(p.citation_key for p in packed)
    assert keys == ["Rossi2021", "Rossi2021b"]
    # Deterministic: same input -> same keys.
    packed2 = builder._assign_keys([(0.9, a), (0.8, b)])
    assert sorted(p.citation_key for p in packed2) == keys


def test_base_key_fallbacks():
    builder = SourcePackBuilder()
    no_author = SourceDoc(title="Deep learning for schools", authors=[], year=2020)
    assert builder._base_key(no_author) == "Deep2020"
    no_year = SourceDoc(title="Something", authors=["Éàç Pérez"], year=0)
    key = builder._base_key(no_year)
    assert key.startswith("Perez")  # accent-folded
    assert key.endswith("nd")


@pytest.mark.asyncio
async def test_build_filters_and_keys_pack(monkeypatch):
    builder = SourcePackBuilder()
    edu = _edu_source(
        "AI in classroom learning for students",
        abstract="students learning in school classroom",
    )
    corp = _edu_source(
        "AI corporate workplace employee onboarding",
        authors=["Vittori"],
        year=2026,
        abstract="corporate aziendale enterprise employee training",
    )
    # Crossref returns both; OpenAlex returns nothing.
    builder.rag.search_crossref = AsyncMock(return_value=[edu, corp])
    builder.rag.search_openalex = AsyncMock(return_value=[])

    pack = await builder.build(
        topic="AI in education for students in schools",
        language="en",
        document_id=1,
        target_size=10,
        min_on_topic_score=0.35,
    )

    titles = [ps.source.title for ps in pack.sources]
    assert edu.title in titles
    assert corp.title not in titles  # off-topic filtered out
    assert all(ps.citation_key for ps in pack.sources)  # every kept source keyed


@pytest.mark.asyncio
async def test_build_underfill_relaxes_threshold(monkeypatch):
    builder = SourcePackBuilder()
    # A single weak-but-nonzero source; below the strict floor of 6.
    weak = _edu_source(
        "A tangential note on education policy",
        abstract="policy education",
    )
    builder.rag.search_crossref = AsyncMock(return_value=[weak])
    builder.rag.search_openalex = AsyncMock(return_value=[])

    pack = await builder.build(
        topic="AI in education",
        language="en",
        document_id=1,
        target_size=10,
        min_on_topic_score=0.9,  # nothing clears this
    )
    assert pack.underfilled is True


def test_prompt_block_uses_keys():
    src = _edu_source("AI tutoring systems", authors=["Rossi", "Bianchi"], year=2021)
    pack = SourcePack(
        document_id=1,
        topic="t",
        sources=[PackedSource(src, "Rossi2021", 0.9)],
    )
    block = pack.prompt_block()
    assert "[Rossi2021]" in block
    assert "AI tutoring systems" in block
    assert pack.by_key("rossi2021") is not None  # case-insensitive lookup
