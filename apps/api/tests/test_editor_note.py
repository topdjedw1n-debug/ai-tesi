"""The editor's note lists only recorded signals, each tied to a section, and
never calls a model (idle session 16.09.2026, point 4)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "editor_note", ROOT / "scripts" / "editor_note.py"
)
editor_note = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editor_note)


def section(index, title, content, raw=None):
    return {
        "job_id": 7,
        "section_index": index,
        "title": title,
        "content": content,
        "raw_content": raw or content,
        "word_count": len(content.split()),
    }


def warning(code, detail="", section_index=None):
    return {
        "job_id": 7,
        "code": code,
        "severity": "warning",
        "stage": "assembling",
        "section_index": section_index,
        "message_uk": "x",
        "detail": detail,
    }


def test_note_lists_recorded_signals_only_and_marks_historical_placeholders():
    pack = {
        "job_id": 7,
        "sources": [
            {
                "citation_key": "KA",
                "source": {
                    "title": "Controlli a distanza",
                    "abstract": "La Corte, sentenza n. 25732/2021, ammette i controlli difensivi.",
                    "canonical_metadata": {},
                },
            }
        ],
    }
    events = [
        ("executor_source_pack", pack),
        ("executor_full_text", {"job_id": 7, "sources": [{"key": "KA", "pages": 3}]}),
        (
            "executor_section",
            section(
                1,
                "Introduzione",
                "Il coordinamento è una costruzione da verificare caso per caso [KA] p. 2.",
            ),
        ),
        (
            "executor_section",
            section(
                2,
                "Le fonti",
                "Il d.lgs. n. 101/2018 adegua il Codice; la n. 25732/2021 lo conferma. "
                "«Una citazione lunga abbastanza per contare qui davvero» [KA].",
            ),
        ),
        (
            "executor_section_evidence",
            {"job_id": 7, "section_index": 1, "evidence": []},
        ),
        (
            "executor_section_evidence",
            {
                "job_id": 7,
                "section_index": 2,
                "evidence": [{"key": "KA", "windows": 4}],
            },
        ),
        ("generation_warning", warning("placeholder_text", "da verificare", 1)),
        ("generation_warning", warning("source_no_readable_text", "K1")),
        ("generation_warning", warning("source_no_readable_text", "K2")),
        ("generation_warning", warning("plan_material_gap", "Casi: senza caso", 2)),
        ("executor_artifact", {"job_id": 7, "sha256": "x"}),
        ("generation_warning", {**warning("review_note", "other job"), "job_id": 8}),
    ]
    meta = {
        "document": {"id": 14, "title": "La tutela dei dati"},
        "job": {"id": 7},
        "sections": [
            {
                "section_index": 2,
                "content": "Il d.lgs. n. 101/2018 adegua il Codice; la n. 25732/2021 lo conferma. "
                "«Una citazione lunga abbastanza per contare qui davvero» (Corte, 2021).",
            }
        ],
    }
    note = editor_note.build_note(meta, events)
    assert note.startswith("# Nota per il redattore — La tutela dei dati")
    assert "documento 14, esecuzione 7" in note
    assert "non contiene le pagine dei testi integrali" in note
    assert "senza documenti a testo integrale: §1 Introduzione." in note
    assert "## Avvisi della generazione (4)" in note
    assert (
        "[source_no_readable_text] Fonte verificata ma senza testo leggibile per la scrittura: K1, K2"
        in note
    )
    assert (
        "### §1 Introduzione\n\n- [placeholder_text] Segnaposto editoriale rimasto nel testo: da verificare — storico"
        in note
    )
    assert (
        "### §2 Le fonti\n\n- [plan_material_gap] Materiale insufficiente nel pacchetto per la sezione: Casi: senza caso"
        in note
    )
    assert "other job" not in note
    assert "- [atto] «d.lgs. n. 101/2018» — non trovato nelle fonti disponibili" in note
    assert "25732/2021" not in note.split("## Numeri e citazioni")[1]
    assert (
        "«Una citazione lunga abbastanza per contare qui davvero» — non trovato" in note
    )
    assert (
        "- §2 Le fonti: «Una citazione lunga abbastanza per contare qui davvero» (Corte, 2021)"
        in note
    )
    assert "inventat" not in note.casefold() and "vigadan" not in note.casefold()
    assert note.rstrip().endswith("solo la lettura secondo la checklist.")


def test_note_without_signals_does_not_claim_quality():
    events = [
        ("executor_source_pack", {"job_id": 7, "sources": []}),
        ("executor_section", section(1, "Introduzione", "Testo semplice.")),
        ("executor_artifact", {"job_id": 7}),
    ]
    note = editor_note.build_note({"document": {}, "job": {}, "sections": []}, events)
    assert "- Nessun avviso registrato." in note
    assert "- Nessuno: ogni numero e citazione controllati" in note
    assert "l'assenza di segnali non significa contenuto accettato" in note
