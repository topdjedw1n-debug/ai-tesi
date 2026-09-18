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


def test_section_issues_strip_bare_keys_and_flag_decision_years():
    import re
    from types import SimpleNamespace

    from app.services.citation_render import section_issues

    marker = re.compile(r"\[(STD:[^\[\]\n]+|[\w:./-]+)\]")
    judgment = SimpleNamespace(
        title="Corte di Cassazione, sezione lavoro, ordinanza 3 giugno 2024, n. 15391",
        authors=["Corte di Cassazione"],
        canonical_metadata={"verification_provider": "manager"},
    )
    text = (
        "La Corte (Ke9df5a146528) conferma; cfr. anche K8737a9239957. "
        "L'ordinanza n. 15391/2022 e la n. 15391/2024 «una citazione lunga abbastanza» (Rossi, 2020)."
    )
    section = {"raw_content": text, "section_index": 4}
    cleaned, notes = section_issues(section, text, marker, {}, {"CASS": judgment}, 0.15)
    assert "Ke9df5a146528" not in cleaned and "K8737a9239957" not in cleaned
    assert cleaned.startswith("La Corte conferma; cfr. anche.")
    assert dict(notes["warnings"]) == {
        "citation_unresolved": "K8737a9239957; Ke9df5a146528",
        "decision_year_mismatch": "n. 15391/2022 (fonte: 2024)",
    }
    assert notes["unpaged"] == ["§4: 1"] and notes["quoted"][0].startswith("§4: ")


def test_official_name_parenthesis_survives_and_asides_are_dropped():
    assert (
        legal_label(
            "Regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio (GDPR), "
            "articoli 4, 5, 6, 9, 13, 22, 25, 35 e 88"
        )
        == "Regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio"
    )
    assert legal_label("Direttiva 95/46/CE (abrogata)") == "Direttiva 95/46/CE"
    assert (
        legal_label(
            "Legge 20 maggio 1970, n. 300 (Statuto dei lavoratori), art. 4 "
            "(Impianti audiovisivi), testo vigente"
        )
        == "Legge 20 maggio 1970, n. 300"
    )
    assert (
        legal_label(
            "Decreto legislativo 14 settembre 2015, n. 151, art. 23 "
            "(Modifiche all'articolo 4 della legge 20 maggio 1970, n. 300)"
        )
        == "Decreto legislativo 14 settembre 2015, n. 151, art. 23"
    )


def test_article_locators_on_acts_named_by_an_article():
    """Law run of 16.09.2026: "(Regolamento, art. 88, comma 1)", "(…, n. 151,
    art. 23, art. 23, comma 1)" and "(…, art. 23, art. 4, comma 1)" — the
    amending act's article and the amended act's article are different
    references, so neither "art." is dropped; the pairing is made explicit."""
    from app.services.citation_render import legal_citation

    meta = {"verification_provider": "manager"}
    gdpr = source(
        "Regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio (GDPR), "
        "articoli 4, 5, 6, 9, 13, 22, 25, 35 e 88",
        ["Parlamento europeo e Consiglio dell'Unione europea"],
        2016,
    )
    decree = source(
        "Decreto legislativo 14 settembre 2015, n. 151, art. 23 "
        "(Modifiche all'articolo 4 della legge 20 maggio 1970, n. 300)",
        ["Repubblica Italiana"],
        2015,
    )
    statute = source(
        "Legge 20 maggio 1970, n. 300 (Statuto dei lavoratori), art. 4 "
        "(Impianti audiovisivi e altri strumenti di controllo), testo vigente",
        ["Repubblica Italiana"],
        2015,
    )
    for item in (gdpr, decree, statute):
        item.canonical_metadata = meta
    known = {"GDPR2016": gdpr, "DLGS151ART23": decree, "ART4": statute}
    text = (
        "Salvezza [GDPR2016] art. 88, comma 1 e in generale [GDPR2016]. "
        "La rubrica [DLGS151ART23] art. 23, comma 1; il nuovo testo "
        "[DLGS151ART23] art. 4, comma 1; la novella [DLGS151ART23] p. 1 e "
        "il testo vigente [ART4] art. 4, comma 1."
    )
    out, entries, missing = render_citations(text, known, CitationStyle.APA, MARKER)
    assert missing == []
    assert (
        "(Regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio, "
        "art. 88, comma 1)" in out
    )
    assert "(Regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio)." in out
    assert "(Decreto legislativo 14 settembre 2015, n. 151, art. 23, comma 1);" in out
    assert (
        "(Legge 20 maggio 1970, n. 300, art. 4, comma 1, come modificato "
        "dall'art. 23, Decreto legislativo 14 settembre 2015, n. 151);" in out
    )
    assert "(Decreto legislativo 14 settembre 2015, n. 151, art. 23) e" in out
    assert "(Legge 20 maggio 1970, n. 300, art. 4, comma 1)." in out
    assert "art. 23, art." not in out and "(Regolamento," not in out
    assert " p. 1" not in out and "[" not in out
    # Bibliography keeps the manager's full titles.
    assert entries["GDPR2016"]["formatted"].startswith(
        "Regolamento (UE) 2016/679 del Parlamento europeo e del Consiglio (GDPR)"
    )
    assert entries["DLGS151ART23"]["formatted"].endswith("n. 300).")
    # An article the title does not explain stays as written, never merged.
    label = "Decreto legislativo 14 settembre 2015, n. 151, art. 23"
    assert legal_citation(label, label, "art. 171") == f"({label}, art. 171)"
    assert legal_citation(label, label, "art. 23") == f"({label})"
    assert legal_citation("Legge 20 maggio 1970, n. 300", "x", "art. 4-bis") == (
        "(Legge 20 maggio 1970, n. 300, art. 4-bis)"
    )


def test_locator_in_parentheses_and_locator_lists_are_folded():
    from app.services.citation_render import normalize_locators, pages_out_of_range

    assert normalize_locators("dati [Kabc] (p. 4), poi [Kabc] (pp. 3-5).") == (
        "dati [Kabc] p. 4, poi [Kabc] pp. 3-5."
    )
    assert normalize_locators("causale [Kabc] p. 3; p. 9. Gli") == (
        "causale [Kabc] pp. 3, 9. Gli"
    )
    known = {
        "Kabc": source("Il potere", ["Bellavista, Alessandro"], 2018, doi="10.1/x")
    }
    rendered, _, missing = render_citations(
        "Riportati in [Kabc] (p. 4), il 92 %; direzione [Kabc] p. 3; p. 9. Fine.",
        known,
        CitationStyle.APA,
        MARKER,
    )
    assert "(Bellavista, 2018, p. 4)," in rendered
    assert "(Bellavista, 2018, pp. 3, 9). Fine." in rendered
    assert ") (p." not in rendered and "); p." not in rendered and missing == []
    assert pages_out_of_range("Testo [Kabc] (p. 40) qui.", None, {"Kabc": 6}) == [
        "Kabc p. 40 > 6"
    ]


def test_bare_keys_inside_parentheses_leave_no_double_punctuation():
    from app.services.citation_render import section_issues

    section = {"raw_content": "x", "section_index": 3}
    text = (
        "fonti primarie corrispondenti (Kdb3df6f45432, Kb4e3607db74e), i cui abstract."
    )
    cleaned, findings = section_issues(section, text, MARKER, {}, {}, 0.5)
    assert cleaned == "fonti primarie corrispondenti, i cui abstract."
    assert ("citation_unresolved", "Kb4e3607db74e; Kdb3df6f45432") in findings[
        "warnings"
    ]
