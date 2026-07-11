import pytest

from app.services.ai_pipeline.citation_formatter import (
    CitationFormatter,
    CitationStyle,
    SourceDocument,
)
from app.services.ai_pipeline.citation_keys import (
    convert_pack_markers,
    internal_marker_keys,
    year_suffix_from_citation_key,
)
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack


def _pack(*sources: tuple[str, list[str], int]) -> SourcePack:
    return SourcePack(
        document_id=1,
        topic="circular economy",
        sources=[
            PackedSource(
                source=SourceDoc(
                    title=f"Paper {key}",
                    authors=authors,
                    year=year,
                ),
                citation_key=key,
                on_topic_score=1.0,
            )
            for key, authors, year in sources
        ],
    )


def test_diacritic_variants_resolve_to_canonical_keys():
    pack = _pack(
        ("Kayıkcı2022", ["Yaşanur Kayıkçı"], 2022),
        ("EnriPeiro2025", ["Sandra Enri-Peiró"], 2025),
    )

    result = convert_pack_markers(
        "Uno studio [Kayıkçı2022] e un altro [EnriPeiró2025].",
        pack,
        citation_style=CitationStyle.APA,
    )

    assert result.content_with_markers == (
        "Uno studio [Kayıkcı2022] e un altro [EnriPeiro2025]."
    )
    assert "(Kayıkçı, 2022)" in result.content
    assert "(Enri-Peiró, 2025)" in result.content
    assert result.used_keys == ["Kayıkcı2022", "EnriPeiro2025"]
    assert result.unresolved_keys == []
    assert internal_marker_keys(result.content) == []


def test_unique_surname_component_alias_resolves():
    pack = _pack(("EnriPeiro2025", ["Sandra Enri-Peiró"], 2025))

    result = convert_pack_markers(
        "La trasformazione è documentata [Peiró2025].",
        pack,
        citation_style=CitationStyle.APA,
    )

    assert result.content == "La trasformazione è documentata (Enri-Peiró, 2025)."
    assert result.used_keys == ["EnriPeiro2025"]
    assert result.unresolved_keys == []


def test_ambiguous_alias_is_preserved_and_reported():
    pack = _pack(
        ("Smith2020a", ["Alice Smith"], 2020),
        ("Smith2020b", ["Bob Smith"], 2020),
    )

    result = convert_pack_markers(
        "Claim [Smith2020].",
        pack,
        citation_style=CitationStyle.APA,
    )

    assert result.content == "Claim [Smith2020]."
    assert result.used_keys == []
    assert result.unresolved_keys == ["Smith2020"]
    assert internal_marker_keys(result.content) == ["Smith2020"]


def test_multi_source_group_is_rendered_without_losing_a_source():
    pack = _pack(
        ("Rossi2021", ["Mario Rossi"], 2021),
        ("Bianchi2022", ["Anna Bianchi"], 2022),
    )

    result = convert_pack_markers(
        "Conferme multiple [Rossi2021; Bianchi2022].",
        pack,
        citation_style=CitationStyle.APA,
    )

    assert result.content == "Conferme multiple (Rossi, 2021; Bianchi, 2022)."
    assert result.used_keys == ["Rossi2021", "Bianchi2022"]
    assert result.unresolved_keys == []


def test_non_citation_bracket_with_four_digits_is_not_flagged():
    text = "La certificazione [ISO9001] e la figura [Figure1234] restano testo."
    assert internal_marker_keys(text) == []


def test_page_locators_and_historical_year_are_resolved_without_losing_pages():
    pack = _pack(("Rossi1895", ["Mario Rossi"], 1895))

    comma = convert_pack_markers(
        "Una fonte storica [Rossi1895, p. 12].",
        pack,
        citation_style=CitationStyle.APA,
    )
    pipe = convert_pack_markers(
        "Una fonte storica [Rossi1895 | pp. 12–14].",
        pack,
        citation_style=CitationStyle.APA,
    )

    assert comma.content == "Una fonte storica (Rossi, 1895, p. 12)."
    assert pipe.content == "Una fonte storica (Rossi, 1895, pp. 12–14)."
    assert comma.unresolved_keys == []
    assert pipe.unresolved_keys == []
    assert internal_marker_keys("[Rossi1895, p. 12]") == ["Rossi1895"]
    assert internal_marker_keys("[Rossi1895 | pp. 12–14]") == ["Rossi1895"]


def test_real_pre_four_digit_year_key_is_resolved_and_cannot_leak():
    pack = _pack(("Rossi950", ["Mario Rossi"], 950))

    result = convert_pack_markers(
        "Una fonte medievale [Rossi950, ch. 3].",
        pack,
        citation_style=CitationStyle.APA,
    )

    assert result.content == "Una fonte medievale (Rossi, 950, ch. 3)."
    assert result.unresolved_keys == []
    assert internal_marker_keys("[Rossi950]") == ["Rossi950"]


@pytest.mark.parametrize(
    ("marker", "expected_key"),
    [
        ("[Smithnd]", "Smithnd"),
        ("[Smithndaa]", "Smithndaa"),
        ("[Smith2020aa]", "Smith2020aa"),
        ("[Rossi950]", "Rossi950"),
        ("[Rossi2020, chapter IV]", "Rossi2020"),
        ("[Rossi2020 | ch. 3]", "Rossi2020"),
        ("[Rossi2020, section 2.1]", "Rossi2020"),
        ("[Rossi2020 | § 4]", "Rossi2020"),
    ],
)
def test_every_legal_pack_key_and_locator_is_recognised(marker, expected_key):
    assert internal_marker_keys(marker) == [expected_key]


def test_chapter_and_section_locators_survive_rendering():
    pack = _pack(("Rossi2020", ["Mario Rossi"], 2020))

    result = convert_pack_markers(
        "Capitolo [Rossi2020, ch. 3], sezione [Rossi2020 | section 2.1].",
        pack,
        citation_style=CitationStyle.APA,
    )

    assert result.content == (
        "Capitolo (Rossi, 2020, ch. 3), sezione (Rossi, 2020, sec. 2.1)."
    )
    assert result.unresolved_keys == []


@pytest.mark.parametrize(
    ("citation_style", "first", "second"),
    [
        (CitationStyle.APA, "(Rossi, 2020a)", "(Rossi, 2020aa)"),
        (CitationStyle.CHICAGO, "(Mario Rossi, 2020a)", "(Mario Rossi, 2020aa)"),
        (CitationStyle.HARVARD, "(Mario Rossi, 2020a)", "(Mario Rossi, 2020aa)"),
    ],
)
def test_author_date_styles_render_complete_collision_suffix(
    citation_style, first, second
):
    pack = _pack(
        ("Rossi2020a", ["Mario Rossi"], 2020),
        ("Rossi2020aa", ["Mario Rossi"], 2020),
    )

    result = convert_pack_markers(
        "Prima [Rossi2020a]. Seconda [Rossi2020aa].",
        pack,
        citation_style=citation_style,
    )

    assert first in result.content
    assert second in result.content
    assert first != second
    assert result.unresolved_keys == []


def test_mla_same_author_sources_use_unique_short_titles():
    pack = SourcePack(
        document_id=1,
        topic="digital work",
        sources=[
            PackedSource(
                source=SourceDoc(
                    title="Digital Universities in Italy",
                    authors=["Mario Rossi"],
                    year=2020,
                ),
                citation_key="Rossi2020",
                on_topic_score=1.0,
            ),
            PackedSource(
                source=SourceDoc(
                    title="Digital Work in Europe",
                    authors=["Mario Rossi"],
                    year=2021,
                ),
                citation_key="Rossi2021",
                on_topic_score=1.0,
            ),
        ],
    )

    result = convert_pack_markers(
        "Prima [Rossi2020]. Seconda [Rossi2021].",
        pack,
        citation_style=CitationStyle.MLA,
    )

    assert '(Mario Rossi, "Digital Universities")' in result.content
    assert '(Mario Rossi, "Digital Work")' in result.content
    assert result.unresolved_keys == []


@pytest.mark.parametrize(
    "citation_style",
    [CitationStyle.APA, CitationStyle.CHICAGO, CitationStyle.HARVARD],
)
def test_author_date_bibliographies_include_complete_collision_suffix(
    citation_style,
):
    source = SourceDocument(
        title="Digital Universities in Italy",
        authors=["Mario Rossi"],
        year=2020,
    )

    reference = CitationFormatter.format_reference(
        source,
        style=citation_style,
        year_suffix="aa",
    )

    assert "2020aa" in reference
    assert year_suffix_from_citation_key("Rossi2020aa") == "aa"


def test_delivered_author_date_citation_keeps_complete_suffix_when_extracted():
    citations = CitationFormatter.extract_citations_from_text(
        "Due fonti distinte (Rossi, 2020a; Rossi, 2020aa)."
    )

    assert [item["year_suffix"] for item in citations] == ["a", "aa"]
