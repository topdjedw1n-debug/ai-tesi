"""Citations a reviewer accepts: specific acts and decisions, pages inside the parentheses."""

import re

from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.citation_render import (
    is_legal_source,
    legal_label,
    quotes_without_page,
    render_citations,
    suspect_metadata,
    with_locator,
)

MARKER = re.compile(r"\[(STD:[^\[\]\n]+|[\w:./-]+)\]", re.UNICODE)


def source(title, authors, year, **extra):
    return SourceDoc(
        title=title,
        authors=authors,
        year=year,
        canonical_metadata={"verification_provider": "PDF", "origin": "pdf"},
        **extra,
    )


def test_legal_sources_are_recognised_and_labelled():
    cass = source(
        "Corte di Cassazione, sezione lavoro, sentenza 22 settembre 2021, n. 25732",
        ["Corte di Cassazione"],
        2021,
    )
    law = source(
        "Legge 20 maggio 1970, n. 300 (Statuto dei lavoratori), art. 4 (Impianti audiovisivi), testo vigente",
        ["Repubblica Italiana"],
        2015,
    )
    echr = source(
        "Bărbulescu v. Romania [GC], no. 61496/08",
        ["Corte europea dei diritti dell'uomo"],
        2017,
    )
    paper = source(
        "Il potere di controllo sul lavoratore", ["Bellavista, Alessandro"], 2018
    )
    assert is_legal_source(cass) and is_legal_source(law) and is_legal_source(echr)
    assert not is_legal_source(paper)
    assert legal_label(law.title) == "Legge 20 maggio 1970, n. 300"
    assert legal_label(cass.title) == cass.title
    assert with_locator("(Rossi, 2020)", "p", "12") == "(Rossi, 2020, p. 12)"
    assert with_locator("(Rossi, 2020)", "pp", "3 - 5") == "(Rossi, 2020, pp. 3–5)"


def test_render_replaces_markers_with_pages_inside_and_splits_bibliography():
    known = {
        "CASS25732": source(
            "Corte di Cassazione, sezione lavoro, sentenza 22 settembre 2021, n. 25732",
            ["Corte di Cassazione"],
            2021,
            url="https://example.test/25732",
        ),
        "Kabc": source(
            "Il potere di controllo", ["Bellavista, Alessandro"], 2018, doi="10.1/x"
        ),
    }
    text = (
        "La Corte [CASS25732] p. 10 afferma [CASS25732]; la dottrina [Kabc] pp. 3-5 "
        "e ancora [Kabc]. Sconosciuto [Kzzz] qui."
    )
    rendered, entries, missing = render_citations(
        text, known, CitationStyle.APA, MARKER
    )
    assert (
        "(Corte di Cassazione, sezione lavoro, sentenza 22 settembre 2021, n. 25732, p. 10)"
        in rendered
    )
    assert (
        "(Corte di Cassazione, sezione lavoro, sentenza 22 settembre 2021, n. 25732);"
        in rendered
    )
    assert (
        "(Bellavista, 2018, pp. 3–5)" in rendered and "(Bellavista, 2018)." in rendered
    )
    assert "[" not in rendered and " p. " not in rendered.replace(", p. ", "")
    assert missing == [("Kzzz", "Sconosciuto [Kzzz] qui.")]
    assert entries["CASS25732"]["kind"] == "legal"
    assert entries["CASS25732"]["formatted"].startswith(
        "Corte di Cassazione, sezione lavoro"
    )
    assert entries["CASS25732"]["formatted"].endswith("https://example.test/25732")
    assert (
        entries["Kabc"]["kind"] == "academic"
        and "Bellavista" in entries["Kabc"]["formatted"]
    )
    assert entries["Kabc"]["verified"] is True and entries["Kabc"]["origin"] == "pdf"
    assert entries["Kabc"]["sort_key"].startswith("bellavista")


def test_suspect_metadata_flags_what_a_reviewer_rejects():
    assert suspect_metadata(
        source("Titolo lungo abbastanza", ["Rossi, M."], 2026), 2025
    ) == ["рік 2026 у майбутньому"]
    assert suspect_metadata(source("Titolo lungo abbastanza", [], None), 2025) == [
        "рік відсутній",
        "автори відсутні",
    ]
    assert (
        suspect_metadata(
            source("Legge 20 maggio 1970, n. 300", ["Repubblica Italiana"], 1970), 2025
        )
        == []
    )
    assert suspect_metadata(source("Corto", ["Rossi, M."], 2020), 2025) == [
        "назва неповна"
    ]


def test_quotes_without_page_are_counted():
    text = (
        "Come afferma la Corte «il controllo difensivo non può prescindere dal sospetto» "
        "(Corte di Cassazione, sentenza n. 25732, p. 10). Altrove «la dottrina ritiene che "
        "il consenso sia debole» (Rossi, 2020). E «una frase molto lunga senza fonte alcuna "
        "qui» senza parentesi."
    )
    assert quotes_without_page(text) == 1


def test_comma_separated_locator_is_folded_and_out_of_range_pages_are_reported():
    from types import SimpleNamespace

    from app.services.citation_render import (
        PAGE_LOCATOR,
        page_counts,
        pages_out_of_range,
    )

    assert PAGE_LOCATOR.match(", p. 15").group(2) == "15"
    assert PAGE_LOCATOR.match(" pp. 3–5").group(2) == "3–5"
    pack = SimpleNamespace(
        passages=[
            SimpleNamespace(citation_key="KORD", page_number=n) for n in (1, 2, 6)
        ]
        + [SimpleNamespace(citation_key="KART", page_number=1)]
    )
    counts = page_counts(pack)
    assert counts == {"KORD": 6, "KART": 1}
    raw = "Testo [KORD] p. 17 e ancora [KORD], pp. 3–5, poi [KART] p. 13 e [KORD] p. 6."
    assert pages_out_of_range(raw, None, counts) == ["KORD p. 17 > 6", "KART p. 13 > 1"]
    assert pages_out_of_range(raw, None, {}) == []


def test_statutes_are_cited_by_article_and_judgments_keep_their_page():
    import re
    from types import SimpleNamespace

    marker = re.compile(r"\[(STD:[^\[\]\n]+|[\w:./-]+)\]")
    meta = {"verification_provider": "manager"}
    statute = SimpleNamespace(
        title="Legge 20 maggio 1970, n. 300 (Statuto dei lavoratori), art. 4, testo vigente",
        authors=["Repubblica Italiana"],
        year=2015,
        url=None,
        venue=None,
        doi=None,
        canonical_metadata=meta,
    )
    judgment = SimpleNamespace(
        title="Corte di Cassazione, sezione lavoro, ordinanza 3 giugno 2024, n. 15391",
        authors=["Corte di Cassazione"],
        year=2024,
        url=None,
        venue=None,
        doi=None,
        canonical_metadata=meta,
    )
    text = "Vieta [ART4] art. 4, comma 1 e [ART4] p. 1; la Corte [CASS], p. 3."
    out, _, _ = render_citations(
        text, {"ART4": statute, "CASS": judgment}, "apa", marker
    )
    assert "(Legge 20 maggio 1970, n. 300, art. 4, comma 1)" in out
    assert "n. 300)" in out and "p. 1" not in out
    assert "n. 15391, p. 3)" in out
    quoted = "«una citazione lunga abbastanza» (Legge 20 maggio 1970, n. 300, art. 4, comma 1)."
    assert quotes_without_page(quoted) == 0


def test_quoted_share_counts_words_between_guillemets():
    from app.services.citation_render import quoted_share

    assert quoted_share("Uno due «tre quattro» cinque.") == 2 / 5
    assert quoted_share("Senza virgolette.") == 0.0
