"""Material fix of 16.09.2026: a node is covered only by a record with the
node's own terms; a section's material passes one exam for every document;
frame titles with a colon are frames; a plan promotes a primary document
only when it is about the section."""

import json
from pathlib import Path

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.executor_v2.scopes import flatten
from app.services.material_fit import about_section, covers, section_fit
from app.services.pack_seats import scope_metadata, seat, tag_scopes
from app.services.plan_check import review
from app.services.search_queries import plan
from app.services.section_material import is_frame, writing_order
from app.services.source_evidence import freeze_evidence

E2_NODES = [
    {
        "scope_id": "s-intro",
        "title": "Introduzione",
        "required": True,
        "terms_local": ["domanda di ricerca", "obiettivi"],
        "terms_en": ["research question", "objectives"],
        "children": [],
    },
    {
        "scope_id": "s-credit",
        "title": "Il finanziamento delle PMI italiane e i vincoli di accesso al credito",
        "required": True,
        "terms_local": [
            "piccole e medie imprese",
            "accesso al credito",
            "credito bancario",
        ],
        "terms_en": ["small and medium enterprises", "access to credit", "bank credit"],
        "children": [
            {
                "scope_id": "s-rationing",
                "title": "I vincoli di accesso al credito e il razionamento",
                "required": True,
                "terms_local": ["razionamento del credito", "asimmetrie informative"],
                "terms_en": ["credit rationing", "information asymmetries"],
                "children": [],
            }
        ],
    },
    {
        "scope_id": "s-crowd",
        "title": "Crowdfunding e minibond come strumenti complementari",
        "required": True,
        "terms_local": ["crowdfunding", "minibond", "strumenti complementari"],
        "terms_en": ["crowdfunding", "minibonds", "complementary instruments"],
        "children": [
            {
                "scope_id": "s-forms",
                "title": "Le forme di crowdfunding",
                "required": True,
                "terms_local": ["equity crowdfunding", "lending crowdfunding"],
                "terms_en": ["equity crowdfunding", "lending crowdfunding"],
                "children": [],
            },
            {
                "scope_id": "s-minibond",
                "title": "I minibond e la finanza obbligazionaria per le PMI",
                "required": True,
                "terms_local": ["minibond", "emissioni obbligazionarie"],
                "terms_en": ["minibonds", "bond issuance"],
                "children": [],
            },
        ],
    },
]
TOPIC = (
    "L'accesso al credito delle piccole e medie imprese italiane nell'era del "
    "fintech: lending alternativo, crowdfunding e ruolo delle banche tradizionali"
)


def packed(key, title, abstract, level="abstract", pdf=False):
    source = SourceDoc(
        title=title,
        authors=["Rossi, M."],
        year=2020,
        abstract=abstract,
        doi=f"10.1/{key}",
        provider="openalex",
        canonical_metadata={"evidence_level": "pdf" if pdf else level},
    )
    freeze_evidence(source, [], key, query=title)
    if pdf:
        source.canonical_metadata["evidence_level"] = "pdf"
    return PackedSource(source, key, 1.0)


def test_own_terms_cover_a_node_and_generic_words_do_not():
    forms = E2_NODES[2]["children"][0]
    assert covers(forms, "Equity crowdfunding: caratteristiche e diffusione") == 1
    assert covers(forms, "Reward-based and lending-based crowdfunding") == 1
    assert (
        covers(forms, "La regolazione del rischio cibernetico nel mercato bancario")
        == 0
    )
    minibond = E2_NODES[2]["children"][1]
    assert covers(minibond, "PROS AND CONS OF MINIBONDS FOR SMES") == 1
    assert covers(minibond, "Bank lending rates in Italy") == 0
    assert (
        covers(E2_NODES[0], "Introduzione alla domanda di ricerca") == 0
    )  # structural


def test_scope_tags_credit_chapters_through_their_leaves():
    nodes = flatten(E2_NODES)
    _, parents, _ = plan(TOPIC, E2_NODES)
    hits = tag_scopes("Equity crowdfunding: the case of Italy", nodes, parents)
    assert hits == {"s-forms": 1, "s-crowd": 1}
    hits = tag_scopes("Credit rationing and information asymmetries", nodes, parents)
    assert set(hits) == {"s-rationing", "s-credit"}
    assert (
        tag_scopes("Migrazioni, politiche e territorio in Veneto", nodes, parents) == {}
    )


def test_reserved_seats_go_to_records_with_the_nodes_own_terms():
    """E2, 16.09: 27 verified crowdfunding/minibond records never got a seat
    because generic bank-credit records returned by the same query had been
    credited to the node. Now the node's seats go to its own records."""
    nodes = flatten(E2_NODES)
    _, parents, _ = plan(TOPIC, E2_NODES)
    rows = []
    for n in range(6):
        rows.append(
            packed(
                f"KGEN{n}",
                f"Il credito bancario alle PMI {n}",
                "Accesso al credito delle imprese.",
            )
        )
    rows.append(
        packed(
            "KCROWD", "Equity crowdfunding in Italy", "Equity crowdfunding for SMEs."
        )
    )
    rows.append(
        packed(
            "KMINI", "Pros and cons of minibonds", "Minibond issuance by Italian SMEs."
        )
    )
    rows.append(packed("KOFF", "Migrazioni in Veneto", "Politiche migratorie."))
    for row in rows:
        row.source.canonical_metadata.update(scope_metadata(row.source, nodes, parents))
    selected, coverage = seat(rows, nodes, minimum=2, max_sources=6)
    keys = [r.citation_key for r in selected]
    assert "KCROWD" in keys and "KMINI" in keys
    assert coverage["s-forms"] == 1 and coverage["s-minibond"] == 1
    assert coverage["s-crowd"] == 2 and coverage["s-credit"] >= 2
    assert len(selected) == 6 and "KOFF" not in keys[:6] or "KOFF" not in keys
    # The query that found a record is not coverage: no record is credited to
    # a node without its own terms.
    assert all(
        "s-forms" not in (r.source.canonical_metadata.get("scope_ids") or [])
        for r in selected
        if r.citation_key.startswith("KGEN")
    )


def test_a_document_is_about_a_section_by_own_terms_or_the_sections_wording():
    nodes = flatten(E2_NODES)
    section = {
        "title": "Le forme di crowdfunding per le PMI",
        "purpose": "Descrivere equity, lending e reward crowdfunding",
        "question": "Quali forme di crowdfunding usano le PMI italiane?",
        "main_points": ["Equity crowdfunding", "Lending crowdfunding"],
        "scope_ids": ["s-forms"],
    }
    assert about_section(
        section, nodes, packed("K1", "Equity e lending crowdfunding", "").source
    )
    # No own term and fewer than three words of the wording: not about it.
    minibond = {
        "title": "I minibond per le PMI",
        "purpose": "Il ruolo dei minibond",
        "main_points": [],
        "scope_ids": ["s-minibond"],
    }
    assert not about_section(
        minibond, nodes, packed("K0", "Sovereign debt markets in Asia", "").source
    )
    # An own term in either language is enough; the same-field full texts on
    # other questions are handled by the document-level topic share.
    assert about_section(
        minibond, nodes, packed("K4", "Bond issuance by Italian firms", "").source
    )
    book = packed(
        "K2",
        "La regolazione del rischio cibernetico nel mercato bancario",
        "Banche e credito.",
    ).source
    assert not about_section(section, nodes, book)
    assert (
        section_fit(section, nodes, "Crowdfunding per le PMI: forme e regole")[0] == 0
    )
    # Three distinct content words of the section's wording are enough.
    assert about_section(
        section,
        nodes,
        packed("K3", "Forme di crowdfunding e finanziamento delle PMI", "").source,
    )


def test_plan_check_promotes_a_primary_document_only_when_it_is_about_the_section():
    nodes = flatten(E2_NODES)
    book = packed(
        "KBOOK",
        "La regolazione del rischio cibernetico nel mercato bancario",
        "Banche.",
        pdf=True,
    )
    crowd = packed(
        "KCROWD", "Equity crowdfunding in Italy", "Equity crowdfunding for SMEs."
    )
    review_pdf = packed(
        "KREV", "Crowdfunding: a review", "Equity and lending crowdfunding.", pdf=True
    )
    _, parents, _ = plan(TOPIC, E2_NODES)
    for row in (book, crowd, review_pdf):
        row.source.canonical_metadata.update(scope_metadata(row.source, nodes, parents))
    pack = SourcePack(1, TOPIC, sources=[book, crowd, review_pdf])
    section = {
        "title": "Le forme di crowdfunding per le PMI",
        "purpose": "Forme di crowdfunding",
        "main_points": [],
        "scope_ids": ["s-forms"],
        "evidence_keys": ["KBOOK", "KCROWD"],
    }
    warnings = review([section], pack, nodes)
    # The book is not promoted for having a file; the crowdfunding review is
    # added from the section's own scopes and leads.
    assert section["evidence_keys"][0] == "KREV" and "KBOOK" in section["evidence_keys"]
    assert warnings == []
    bare = {**section, "evidence_keys": ["KBOOK"]}
    warnings = review([bare], SourcePack(1, TOPIC, sources=[book, crowd]), nodes)
    assert bare["evidence_keys"] == ["KBOOK"]
    assert warnings == [
        ("plan_material_gap", "Le forme di crowdfunding per le PMI: без першоджерела")
    ]


def test_frame_titles_with_a_colon_are_frames_and_written_last():
    assert is_frame(
        {"title": "Introduzione: domanda di ricerca, obiettivi e metodologia"}
    )
    assert is_frame({"title": "Conclusioni: sintesi e prospettive"})
    assert is_frame({"title": "Conclusioni e prospettive future"})
    # Psychology 17.09: a comma after the frame word left the conclusions
    # without the frame rule and the findings (48 % AI).
    assert is_frame({"title": "Conclusioni, limiti e prospettive future"})
    assert is_frame({"title": "Introduzione, obiettivi e metodologia"})
    assert is_frame({"title": "Conclusioni – limiti e prospettive"})
    assert not is_frame({"title": "Conclusioni sul mercato del credito"})
    assert not is_frame({"title": "Conclusione del contratto di lavoro"})
    assert not is_frame({"title": "Introduzione al marketing digitale"})
    assert not is_frame(
        {"title": "Discussione: implicazioni per il finanziamento delle PMI"}
    )
    outline = [
        {
            "title": "Introduzione: domanda di ricerca, obiettivi e metodologia",
            "section_index": 1,
        },
        {"title": "Il ruolo delle PMI", "section_index": 2},
        {"title": "Discussione: implicazioni", "section_index": 3},
        {"title": "Conclusioni e prospettive future", "section_index": 4},
    ]
    assert [s["section_index"] for s in writing_order(outline)] == [2, 3, 4, 1]


def test_recorded_e2_introduction_is_now_a_frame():
    events = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "material"
            / "e2-outline-2026-09-16.json"
        ).read_text()
    )
    titles = [s["title"] for s in events["sections"]]
    order = [s["title"] for s in writing_order(events["sections"])]
    assert order[-1].startswith("Introduzione") and order[-2].startswith("Conclusioni")
    assert titles[0].startswith("Introduzione:") and order[0] != titles[0]


def test_a_full_text_on_another_subject_hands_no_pages_and_is_not_primary():
    """Biology, 16.09.2026: a 105-page thesis on HIV-integrase chimeras had
    windows that matched section wording, so it led sections on antibiotic
    resistance. A document's pages serve only when at least half of its
    windows carry a topic anchor; its abstract stays at most."""
    from app.services.full_text_sources import (
        document_windows,
        full_text_usable,
        section_evidence,
    )
    from app.services.material_fit import document_topic_share
    from app.services.search_queries import anchors

    topic = "La resistenza agli antibiotici: meccanismi molecolari della resistenza batterica"
    nodes = [
        {
            "scope_id": "s-mech",
            "title": "Meccanismi molecolari di resistenza batterica",
            "required": True,
            "terms_local": ["meccanismi di resistenza", "resistenza batterica"],
            "terms_en": ["resistance mechanisms", "bacterial resistance"],
            "children": [],
        }
    ]
    on_topic_pages = [
        "I meccanismi di resistenza batterica agli antibiotici comprendono enzimi e pompe. "
        * 8
    ] * 3
    off_pages = [
        "La chimera dell'integrasi di HIV mostra attività idrolizzante in vitro. " * 8
    ] * 6
    off_pages.append(
        "Alcuni ceppi batterici mostrano resistenza agli antibiotici in coltura. " * 8
    )
    passages = document_windows("KAMR", "u1", on_topic_pages)
    passages += document_windows("KHIV", "u2", off_pages)
    amr = packed(
        "KAMR",
        "Antibiotic resistance mechanisms in bacteria",
        "Enzymes and efflux pumps.",
        pdf=True,
    )
    hiv = packed(
        "KHIV",
        "Costruzione di chimere dell'integrasi di HIV",
        "Attività idrolizzante della chimera.",
        pdf=True,
    )
    pack = SourcePack(1, topic, sources=[amr, hiv], passages=passages)
    pattern = anchors(topic)
    assert (
        document_topic_share(
            [w.text for w in passages if w.citation_key == "KAMR"], pattern
        )
        == 1.0
    )
    assert (
        document_topic_share(
            [w.text for w in passages if w.citation_key == "KHIV"], pattern
        )
        < 0.5
    )
    assert full_text_usable(pack, "KAMR", nodes) and not full_text_usable(
        pack, "KHIV", nodes
    )
    section = {
        "title": "Meccanismi molecolari di resistenza batterica",
        "purpose": "Enzimi, pompe di efflusso e mutazioni",
        "main_points": ["Meccanismi di resistenza"],
        "scope_ids": ["s-mech"],
        "evidence_keys": ["KHIV", "KAMR"],
    }
    items, report = section_evidence(pack, section, nodes)
    assert [i["key"] for i in items] == ["KAMR"]
    assert {r["key"]: r["reason"] for r in report} == {
        "KAMR": "support",
        "KHIV": "off_topic_text",
    }
    warnings = review([dict(section)], pack, nodes)
    assert warnings == []
    only_hiv = {**section, "evidence_keys": ["KHIV"]}
    review([only_hiv], SourcePack(1, topic, sources=[hiv], passages=passages), nodes)
    assert only_hiv["evidence_keys"] == ["KHIV"]  # kept as written, never promoted
