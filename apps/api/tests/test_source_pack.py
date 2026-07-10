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
    assert keys == ["Rossi2021a", "Rossi2021b"]
    # Deterministic: same input -> same keys.
    packed2 = builder._assign_keys([(0.9, a), (0.8, b)])
    assert sorted(p.citation_key for p in packed2) == keys


def test_citation_key_uses_surname_for_comma_form_author():
    source = _edu_source(
        "Italian higher education study",
        authors=["Rossi, Mario"],
        year=2021,
    )
    packed = SourcePackBuilder._assign_keys([(0.9, source)])
    assert packed[0].citation_key == "Rossi2021"


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


# ---------------------------------------------------------------------------
# Fix-wave 2: anchor GATE regression fixtures — the REAL doc-3 offenders.
# ---------------------------------------------------------------------------

_EDU_TOPIC = "L'impatto dell'intelligenza artificiale sull'istruzione"


def _score_for_edu_topic(src):
    from app.services.ai_pipeline.text_utils import content_tokens

    topic_terms = content_tokens(_EDU_TOPIC)
    domain = SourcePackBuilder._detect_domain(topic_terms)
    assert domain == "education"
    return SourcePackBuilder._on_topic_score(src, topic_terms, domain)


def test_gate_rejects_evoting_source():
    src = SourceDoc(
        title="impatto dell'intelligenza artificiale sui sistemi di voto "
        "elettronico nell'epoca delle crisi globali",
        authors=["Bertoni"],
        year=2026,
        abstract="La monografia analizza l'impatto dell'intelligenza artificiale "
        "sui sistemi di voto elettronico, ricadute normative",
    )
    assert _score_for_edu_topic(src) == 0.0


def test_gate_rejects_healthcare_source():
    src = SourceDoc(
        title="Analisi dei fattori determinanti l'adozione dell'Intelligenza "
        "Artificiale in sanità",
        authors=["Domenico"],
        year=2024,
        abstract="adozione di strumenti di intelligenza artificiale nelle "
        "aziende sanitarie",
    )
    assert _score_for_edu_topic(src) == 0.0


def test_gate_rejects_neuro_diagnosis_source():
    src = SourceDoc(
        title="Il contributo dell'intelligenza artificiale nella diagnosi dei "
        "disturbi neurodegenerativi",
        authors=["Nappo"],
        year=2024,
        abstract="patologie neurodegenerative, emergenza assistenziale",
    )
    assert _score_for_edu_topic(src) == 0.0


def test_gate_passes_formazione_source():
    src = SourceDoc(
        title="Il potere di imparare: navigare la formazione nell'era "
        "dell'intelligenza artificiale",
        authors=["Vitolo"],
        year=2026,
        abstract="",
    )
    assert _score_for_edu_topic(src) >= 0.35


def test_gate_counts_venue_as_anchor_signal():
    # Moscatelli-class: no anchor in title/abstract, but a formazione journal.
    src = SourceDoc(
        title="#openAIF: Coltivare un Nuovo Umanesimo nell'Era "
        "dell'Intelligenza Artificiale",
        authors=["Moscatelli"],
        year=2024,
        abstract="",
        venue="FOR - Rivista per la formazione",
    )
    assert _score_for_edu_topic(src) > 0.0


def test_anchored_but_tainted_stays_below_threshold():
    # Yesterday's corporate-training case: anchored (formazione) but off-topic.
    src = SourceDoc(
        title="L'impatto dell'IA nella formazione aziendale: tra etica e "
        "adattamento",
        authors=["Vittori"],
        year=2026,
        abstract="formazione aziendale con IA per dipendenti",
    )
    score = _score_for_edu_topic(src)
    assert 0.0 <= score < 0.35


def test_build_queries_includes_language_anchors_and_is_bounded():
    qs = SourcePackBuilder._build_queries(
        _EDU_TOPIC, ["Introduzione", "Futuro"], "it", "education"
    )
    assert any("istruzione scuola" in q for q in qs)
    assert any("apprendimento studenti" in q for q in qs)
    assert len(qs) <= 11
    # No domain -> no anchored queries; legacy 2-arg-style call still works.
    qs_plain = SourcePackBuilder._build_queries(_EDU_TOPIC, None)
    assert qs_plain == [_EDU_TOPIC]


# ---------------------------------------------------------------------------
# Bilingual pack (doc-8 fix): EN translation queries + max() scoring.
# ---------------------------------------------------------------------------

_COVID_TOPIC_IT = "L'impatto della pandemia COVID-19 sull'economia degli Stati Uniti"
_COVID_TOPIC_EN = "The impact of the COVID-19 pandemic on the United States economy"


@pytest.mark.asyncio
async def test_build_merges_alt_queries_and_caps_alt_titles():
    builder = SourcePackBuilder()
    seen_queries: list[str] = []

    async def capture(query, limit=10):
        seen_queries.append(query)
        return []

    builder.rag.search_crossref = AsyncMock(side_effect=capture)
    builder.rag.search_openalex = AsyncMock(side_effect=capture)

    await builder.build(
        topic=_COVID_TOPIC_IT,
        language="it",
        document_id=1,
        section_titles=[f"Sezione {i}" for i in range(1, 9)],
        alt_topic=_COVID_TOPIC_EN,
        alt_section_titles=[f"Chapter number {i}" for i in range(1, 9)],
    )

    unique = list(dict.fromkeys(seen_queries))
    assert _COVID_TOPIC_EN in unique  # bare alt topic queried
    # Only 4 of the 8 alt titles become queries (the cap), all 8 IT ones do.
    alt_title_queries = [q for q in unique if "Chapter number" in q]
    it_title_queries = [q for q in unique if "Sezione" in q]
    assert len(alt_title_queries) == 4
    assert len(it_title_queries) == 8
    assert len(unique) <= 18


@pytest.mark.asyncio
async def test_en_source_passes_threshold_via_alt_terms():
    """The doc-8 failure: a perfectly on-topic English source scored ~0 against
    the Italian topic tokens. With alt terms it must clear the threshold."""
    builder = SourcePackBuilder()
    en_src = SourceDoc(
        title="The economic impact of the COVID-19 pandemic on the United States",
        authors=["Smith"],
        year=2021,
        abstract="pandemic recession unemployment economy united states impact",
    )
    builder.rag.search_crossref = AsyncMock(return_value=[en_src])
    builder.rag.search_openalex = AsyncMock(return_value=[])

    mono = await builder.build(topic=_COVID_TOPIC_IT, language="it", document_id=1)
    bi = await builder.build(
        topic=_COVID_TOPIC_IT,
        language="it",
        document_id=1,
        alt_topic=_COVID_TOPIC_EN,
    )

    mono_score = next(
        (ps.on_topic_score for ps in mono.sources if ps.source.title == en_src.title),
        0.0,
    )
    bi_score = next(
        ps.on_topic_score for ps in bi.sources if ps.source.title == en_src.title
    )
    assert mono_score < 0.35  # today's behavior: killed by Italian tokens
    assert bi_score >= 0.35  # bilingual: kept on merit
    assert bi.bilingual is True
    assert mono.bilingual is False


@pytest.mark.asyncio
async def test_alt_topic_none_is_byte_identical_to_legacy_build():
    builder = SourcePackBuilder()
    edu = _edu_source(
        "AI in classroom learning for students",
        abstract="students learning in school classroom",
    )
    builder.rag.search_crossref = AsyncMock(return_value=[edu])
    builder.rag.search_openalex = AsyncMock(return_value=[])

    kwargs = {
        "topic": "AI in education for students in schools",
        "language": "en",
        "document_id": 1,
        "target_size": 10,
        "min_on_topic_score": 0.35,
    }
    legacy = await builder.build(**kwargs)
    explicit_none = await builder.build(
        **kwargs, alt_topic=None, alt_section_titles=None
    )

    assert [
        (ps.citation_key, ps.on_topic_score, ps.source.title) for ps in legacy.sources
    ] == [
        (ps.citation_key, ps.on_topic_score, ps.source.title)
        for ps in explicit_none.sources
    ]
    assert legacy.underfilled == explicit_none.underfilled
    assert explicit_none.bilingual is False


@pytest.mark.asyncio
async def test_build_drops_uncitable_sources():
    """doc-9 crash: the citation formatter hard-requires author(s) + year, so
    an authorless or yearless source must never enter the pack."""
    builder = SourcePackBuilder()
    good = _edu_source(
        "AI in classroom learning for students",
        abstract="students learning in school classroom",
    )
    no_author = SourceDoc(
        title="AI in education and classroom learning for students",
        authors=[],
        year=2022,
        abstract="students learning education school",
    )
    no_year = SourceDoc(
        title="Education students classroom learning with AI",
        authors=["Verdi"],
        year=0,
        abstract="students learning education school",
    )
    builder.rag.search_crossref = AsyncMock(return_value=[good, no_author, no_year])
    builder.rag.search_openalex = AsyncMock(return_value=[])

    pack = await builder.build(
        topic="AI in education for students in schools",
        language="en",
        document_id=1,
    )
    titles = [ps.source.title for ps in pack.sources]
    assert good.title in titles
    assert no_author.title not in titles
    assert no_year.title not in titles


def test_learning_in_alt_terms_does_not_flip_education_domain():
    """Regression: an EN translation containing 'learning' (machine learning,
    deep learning) on a NON-education topic must not detect the education
    domain — its anchor hard-gate would zero every source in the pack."""
    from app.services.ai_pipeline.text_utils import content_tokens

    topic_terms = content_tokens(
        "Previsioni di disoccupazione durante le recessioni economiche"
    )
    alt_terms = content_tokens(
        "Machine learning forecasts of unemployment during economic recessions"
    )
    assert SourcePackBuilder._detect_domain(topic_terms | alt_terms) is None

    # Real education vocabulary still detects (both languages).
    assert (
        SourcePackBuilder._detect_domain(
            content_tokens("AI in education for students in schools")
        )
        == "education"
    )
    assert SourcePackBuilder._detect_domain(content_tokens(_EDU_TOPIC)) == "education"
