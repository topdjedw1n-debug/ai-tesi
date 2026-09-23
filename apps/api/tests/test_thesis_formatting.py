"""The DOCX a reviewer opens: chapters and sub-sections, a contents field, Word-like typography."""

from docx import Document

from app.services.docx_export import (
    add_table_of_contents,
    assemble_document,
    assemble_section,
    normalize_typography,
)


def test_typography_is_word_like_and_leaves_urls_alone():
    text = """L'art. 4 dell'impianto "tutela" — cioè — "sicurezza"; https://doi.org/10.1/a'b [K1] p. 3"""
    out = normalize_typography(text)
    assert "L’art. 4 dell’impianto «tutela» – cioè – «sicurezza»" in out
    assert (
        "https://doi.org/10.1/a’b" in out
    )  # apostrophe rule only between word characters
    assert "[K1] p. 3" in out and "—" not in out


def test_assembly_numbers_chapters_by_level_and_splits_the_bibliography():
    sections = [
        {"title": "Introduzione", "content": "Testo l'inizio.", "level": 1},
        {"title": "Capitolo I – Evoluzione", "content": "x", "level": 1},
        {"title": "La formulazione originaria", "content": "y", "level": 2},
        {"title": "La riforma", "content": "z", "level": 2},
        {"title": "Il GDPR", "content": "w", "level": 1},
        {"title": "1.1 Già numerato", "content": "v", "level": 2},
        {"title": "Conclusioni", "content": "c", "level": 1},
    ]
    bibliography = [
        {"formatted": "Zeta, A. (2020). T.", "kind": "academic", "sort_key": "zeta"},
        {"formatted": "Alfa, B. (2019). T.", "kind": "academic", "sort_key": "alfa"},
        {
            "formatted": "Legge 20 maggio 1970, n. 300. https://x",
            "kind": "legal",
            "sort_key": "legge",
        },
    ]
    out = assemble_document(sections, bibliography, "it")
    assert out.startswith("# Introduzione\n\nTesto l’inizio.")
    assert "\n\n# Capitolo I – Evoluzione\n\n" in out  # supervisor numbering kept as is
    assert "\n\n## 1.1 La formulazione originaria\n\n" in out
    assert "\n\n## 1.2 La riforma\n\n" in out
    assert "\n\n# 2. Il GDPR\n\n" in out and "\n\n## 1.1 Già numerato\n\n" in out
    assert "\n\n# Conclusioni\n\n" in out
    bib = out.index("# Bibliografia")
    legal = out.index("# Normativa e giurisprudenza")
    assert bib < legal
    assert out.index("Alfa, B.") < out.index("Zeta, A.") < legal
    assert out.rstrip().endswith("Legge 20 maggio 1970, n. 300. https://x")
    # Sub-headings the writer wrote inside a chapter are renumbered in sequence
    # and the chapter title is not duplicated by the writer's own heading line.
    out = assemble_document(
        [
            {
                "title": "Quadro teorico",
                "content": "# Quadro teorico\n\nIntro.\n\n## 1.1 Definizione\n\nt\n\n## 1.2 Altro\n\nu",
                "level": 1,
            },
            {"title": "Evoluzione", "content": "v", "level": 2},
        ],
        [],
        "it",
    )
    assert out.count("Quadro teorico") == 1 and out.startswith("# 1. Quadro teorico\n")
    assert (
        "## 1.1 Definizione" in out
        and "## 1.2 Altro" in out
        and "## 1.3 Evoluzione" in out
    )
    assert normalize_typography("dall' articolo 4") == "dall’articolo 4"
    # A quotation inside «…» takes “…”; the next paragraph starts afresh.
    assert normalize_typography(
        'per lui «"seeing" was a "necessity"».\nIl "vuoto".'
    ) == ("per lui «“seeing” was a “necessity”».\nIl «vuoto».")
    # Old behaviour is untouched when no level and no bibliography kinds are given.
    assert (
        assemble_section("Capitolo 1. Tema", "# Capitolo 1. Tema\n\nTesto")
        == "# Capitolo 1. Tema\n\nTesto"
    )
    assert assemble_section("Sub", "Testo", 2) == "## Sub\n\nTesto"


def test_table_of_contents_field_updates_on_open():
    docx = Document()
    docx.add_heading("Titolo", 0)
    add_table_of_contents(docx, "it")
    docx.add_heading("Introduzione", 1)
    xml = docx.element.xml
    assert 'TOC \\o "1-3" \\h \\z \\u' in xml
    assert docx.settings.element.xml.count("w:updateFields") == 1
    assert [p.text for p in docx.paragraphs][1] == "Indice"
    assert "w:br" in xml  # the contents page ends with a page break


def test_chapter_headings_come_from_the_supervisor_tree_when_the_plan_skips_them():
    from app.services.docx_export import assemble_document, with_chapter_headings

    nodes = [
        {"scope_id": "scope-1", "title": "Introduzione", "children": []},
        {
            "scope_id": "scope-2",
            "title": "Capitolo I. Evoluzione dell'art. 4",
            "children": [
                {
                    "scope_id": "scope-3",
                    "title": "Formulazione originaria",
                    "children": [],
                },
                {"scope_id": "scope-4", "title": "Riforma", "children": []},
            ],
        },
        {"scope_id": "scope-5", "title": "Conclusioni", "children": []},
    ]
    flat = [nodes[0], nodes[1], *nodes[1]["children"], nodes[2]]
    sections = [
        {
            "title": "Introduzione",
            "level": 1,
            "scope_ids": ["scope-1"],
            "content": "Intro.",
        },
        {
            "title": "Formulazione originaria",
            "level": 2,
            "scope_ids": ["scope-3"],
            "content": "A.",
        },
        {"title": "Riforma", "level": 2, "scope_ids": ["scope-4"], "content": "B."},
        {
            "title": "Conclusioni",
            "level": 1,
            "scope_ids": ["scope-5"],
            "content": "Fine.",
        },
    ]
    out = with_chapter_headings(sections, flat)
    assert [s["title"] for s in out] == [
        "Introduzione",
        "Capitolo I. Evoluzione dell'art. 4",
        "Formulazione originaria",
        "Riforma",
        "Conclusioni",
    ]
    text = assemble_document(out, [], "it")
    assert "# Capitolo I. Evoluzione dell'art. 4" in text
    assert "## 1.1 Formulazione originaria" in text and "## 1.2 Riforma" in text
    # A plan that already carries the chapter as a level-1 section is left alone.
    direct = [
        {
            "title": "Capitolo I. Evoluzione dell'art. 4",
            "level": 1,
            "scope_ids": ["scope-2"],
            "content": "C.",
        }
    ]
    assert with_chapter_headings(direct, flat) == direct
