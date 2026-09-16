"""S3 plan checks (16.09.2026): a primary document leads every subject
section, and a "case studies" section without a case in the pack is reported."""

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.plan_check import is_primary, review
from app.services.section_material import frame_violations


def packed(key, title, level, scopes=(), abstract=None, authors=("Rossi, M.",)):
    doc = SourceDoc(
        title=title,
        authors=list(authors),
        year=2020,
        abstract=abstract,
        provider="openalex",
        canonical_metadata={"evidence_level": level, "scope_ids": list(scopes)},
    )
    return PackedSource(doc, key, 1.0)


def pack_of(*sources):
    return SourcePack(
        1, "Social media e fidelizzazione nelle PMI", sources=list(sources)
    )


def test_primary_document_leads_and_is_added_from_the_scopes_when_missing():
    pack = pack_of(
        packed(
            "Kabs", "Review of loyalty", "abstract", ["scope-2"], abstract="loyalty"
        ),
        packed("Kpdf", "Survey data on SMEs", "pdf", ["scope-2"]),
        packed("Kother", "Another study", "pdf", ["scope-9"]),
    )
    sections = [
        {"title": "Introduzione", "scope_ids": ["scope-1"], "evidence_keys": ["Kabs"]},
        {
            "title": "Il concetto di fidelizzazione",
            "question": "Che cos'è la fidelizzazione?",
            "scope_ids": ["scope-2"],
            "evidence_keys": ["Kabs", "Kpdf"],
        },
        {
            "title": "Determinanti della fidelizzazione",
            "scope_ids": ["scope-2"],
            "evidence_keys": ["Kabs"],
        },
        {"title": "Prospettive", "scope_ids": ["scope-7"], "evidence_keys": ["Kabs"]},
    ]
    warnings = review(sections, pack)
    assert sections[0]["evidence_keys"] == ["Kabs"], "framing sections untouched"
    assert sections[1]["evidence_keys"] == ["Kpdf", "Kabs"]
    assert sections[2]["evidence_keys"] == ["Kpdf", "Kabs"], "primary from the scope"
    assert sections[3]["evidence_keys"] == ["Kabs"]
    assert warnings == [("plan_material_gap", "Prospettive: без першоджерела")]


def test_legal_acts_count_as_primary_even_without_full_text():
    act = packed(
        "Anonymous2016",
        "Regolamento (UE) 2016/679 (GDPR), articoli 4, 5, 6",
        "abstract",
        authors=("Parlamento europeo e Consiglio dell'Unione europea",),
    )
    assert is_primary(act)
    assert not is_primary(packed("Kabs", "A review", "abstract"))


def test_case_section_without_any_case_in_the_pack_is_reported():
    pack = pack_of(
        packed("Kpdf", "Drivers of digital transformation in SMEs", "pdf", ["scope-3"]),
        packed(
            "Kcase",
            "Creative crowdsourcing: il caso Zooppa",
            "pdf",
            ["scope-3"],
            abstract="Il caso di una piattaforma",
        ),
    )
    without = [
        {
            "title": "Casi di studio di PMI italiane",
            "scope_ids": ["scope-3"],
            "evidence_keys": ["Kpdf"],
        }
    ]
    assert review(without, pack) == [
        ("plan_material_gap", "Casi di studio di PMI italiane: у пакеті немає кейсів")
    ]
    with_case = [
        {
            "title": "Casi di studio di PMI italiane",
            "scope_ids": ["scope-3"],
            "evidence_keys": ["Kpdf", "Kcase"],
        }
    ]
    assert review(with_case, pack) == []


def test_frame_violations_catch_the_chapter_walk_only():
    walked = (
        "Il primo capitolo colloca il marketing digitale entro la trasformazione. "
        "Il secondo capitolo mostra che i social media non operano in modo uniforme. "
        "La tesi si articola in tre parti."
    )
    assert len(frame_violations(walked)) == 3
    clean = (
        "Le evidenze raccolte indicano una risposta affermativa ma condizionata: "
        "l'adozione dipende dal contesto tecnologico (Omrani et al., 2024, p. 10)."
    )
    assert frame_violations(clean) == []
