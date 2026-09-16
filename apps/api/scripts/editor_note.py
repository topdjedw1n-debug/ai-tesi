"""Note for the editor: the mechanical signals of one generated work.

Usage: python scripts/editor_note.py RECORDING OUT.md [--job-id N]

RECORDING is a full recording (.json or .json.gz with document_provenance) or
an events dump ({"document", "job", "events", "sections"}). No model is called
and the DOCX is not touched. The note lists only what the recording holds:

- the warnings of the run, each with its section; a recorded placeholder
  warning that the current detector no longer raises is marked as historical;
- citation-like numbers and quotations not found in the texts the recording
  holds ("non trovato nelle fonti disponibili", never "invented"), with the
  honest scope of that check (a dump without full-text pages checks against
  abstracts and uploaded excerpts only);
- direct quotations whose citation carries no page;
- sections written without full-text documents.

Absence of signals is not accepted quality: the checklist reading decides.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
os.environ.setdefault("ENV_FILE", "/dev/null")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "offline-note-only-secret-never-an-account-key")
os.environ.setdefault("JWT_SECRET", "offline-note-only-secret-never-an-account-key")

from fabrication_check import check_text, corpus_texts, section_texts  # noqa: E402

from app.services.citation_render import QUOTED_CITATION  # noqa: E402
from app.services.executor_v2.budgets import POLICY  # noqa: E402
from app.services.placeholder_notes import find_placeholders  # noqa: E402

# The executor's closed warning vocabulary, for an Italian-reading editor.
LABELS = {
    "source_coverage_gap": "Poche fonti con testo disponibile per una parte del tema",
    "source_no_readable_text": "Fonte verificata ma senza testo leggibile per la scrittura",
    "source_full_text_unavailable": "Testo integrale non ottenuto per alcune fonti",
    "section_without_documents": "Sezione scritta senza documenti a testo integrale",
    "catalogue_unavailable": "Catalogo delle fonti non disponibile durante la ricerca",
    "standard_reference_used": "Fonte della biblioteca standard",
    "plan_material_gap": "Materiale insufficiente nel pacchetto per la sezione",
    "frame_rewritten": "Sezione di cornice riscritta senza il riepilogo dei capitoli",
    "outline_scope_unmapped": "Il piano non copre una parte del compito",
    "output_truncated_retried": "Risposta troncata del modello ripresa con una seconda chiamata",
    "output_truncated_kept": "Sezione troncata due volte; conservato il testo fino all'ultima frase completa",
    "citation_unresolved": "Riferimento sconosciuto rimosso dal testo",
    "length_off_target": "Lunghezza della sezione diversa da quella pianificata",
    "reference_replaced": "Riferimento non confermato rimosso dal testo",
    "review_negative": "La revisione finale ha rilevato difetti",
    "review_note": "La revisione finale ha lasciato osservazioni",
    "page_out_of_range": "Pagina citata oltre la fine del documento",
    "decision_year_mismatch": "Anno della decisione diverso da quello della fonte",
    "quote_share_high": "Troppe citazioni tra virgolette (oltre il 15 %)",
    "quote_without_page": "Citazioni dirette senza numero di pagina",
    "bibliography_suspect": "Voci bibliografiche con dati dubbi (anno, autori, titolo)",
    "detector_unchecked": "Rilevatore esterno non disponibile",
    "placeholder_text": "Segnaposto editoriale rimasto nel testo",
}
KINDS = {
    "decision": "decisione",
    "article": "articolo",
    "act": "atto",
    "page": "pagina",
    "quote": "citazione",
}


def load(path: Path) -> tuple[dict, list[tuple[str, dict]]]:
    """Document/job/section rows and provenance events of a dump or a recording."""
    raw = path.read_bytes()
    data = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    if isinstance(data, dict) and "events" in data and "document" in data:
        meta = {
            "document": data.get("document") or {},
            "job": data.get("job") or {},
            "sections": data.get("sections") or [],
        }
        rows = data["events"] or []
    else:
        documents = data.get("documents") or []
        jobs = data.get("ai_generation_jobs") or []
        meta = {
            "document": documents[-1] if documents else {},
            "job": jobs[-1] if jobs else {},
            "sections": data.get("document_sections") or [],
        }
        rows = data.get("document_provenance", data.get("provenance", []))
    return meta, [(e["event_type"], e.get("payload") or {}) for e in rows]


def job_events(events, job_id):
    if job_id is None:
        artifacts = [p for et, p in events if et == "executor_artifact"]
        job_id = (artifacts[-1] if artifacts else {}).get("job_id")
    if job_id is None:
        return events
    return [(et, p) for et, p in events if p.get("job_id") in (job_id, None)]


def fragment(text: str, limit: int = 110) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def placeholder_state(warning, section):
    """Whether the current detector still raises the recorded placeholder."""
    if section is None:
        return None
    current = find_placeholders(
        section.get("content", "") + "\n" + section.get("raw_content", ""),
        POLICY["placeholder_phrases"],
    )
    recorded = [d.strip().casefold() for d in str(warning.get("detail", "")).split(";")]
    return any(d in current for d in recorded if d)


def quotes_without_page(text):
    return [
        ("«" + fragment(m.group(0)[1 : m.group(0).index("»")], 90) + "»", m.group(1))
        for m in QUOTED_CITATION.finditer(text)
        if not re.search(r"\b(?:pp?|artt?)\.\s*\d", m.group(1))
    ]


def rendered_texts(meta, sections):
    """The text the editor reads: saved section rows carry the rendered
    citations; the executor_section events still hold the raw markers."""
    saved = {
        int(r["section_index"]): r.get("content") or ""
        for r in meta.get("sections") or []
        if r.get("section_index") is not None and r.get("content")
    }
    return {i: saved.get(i) or s.get("content", "") for i, s in sections.items()}


def compact(rows):
    """One line per code for general warnings that only differ by detail."""
    merged, order = {}, []
    for w in rows:
        key = (w.get("code"), w.get("section_index"))
        if key not in merged:
            merged[key] = {**w, "detail": [w.get("detail")] if w.get("detail") else []}
            order.append(key)
        elif w.get("detail"):
            merged[key]["detail"].append(w["detail"])
    return [{**merged[k], "detail": ", ".join(merged[k]["detail"])} for k in order]


def build_note(meta, events, job_id=None) -> str:
    events = job_events(events, job_id)
    sections = section_texts(events)
    titles = {i: s.get("title", "") for i, s in sections.items()}
    texts = rendered_texts(meta, sections)
    haystack, held = corpus_texts(events)
    evidence = {
        p["section_index"]: p.get("evidence") or []
        for et, p in events
        if et == "executor_section_evidence"
    }
    warnings = [p for et, p in events if et == "generation_warning"]
    outline = [p for et, p in events if et == "executor_outline"]
    full_text = [p for et, p in events if et == "executor_full_text"]
    fetched = sum(
        1 for s in (full_text[-1].get("sources") if full_text else []) if s.get("pages")
    )
    document, job = meta.get("document") or {}, meta.get("job") or {}
    title = document.get("title") or (outline[-1].get("title") if outline else "") or ""

    def heading(index):
        return f"§{index} {titles.get(index, '')}".strip()

    lines = [
        f"# Nota per il redattore — {title}".rstrip(" —"),
        "",
        "Segnali meccanici tratti dalla registrazione della generazione"
        + (f" (documento {document['id']}" if document.get("id") else "")
        + (f", esecuzione {job['id']}" if job.get("id") else "")
        + (")" if document.get("id") else "")
        + ". Nessun giudizio di merito: l'assenza di segnali non significa contenuto"
        " accettato. Decide la lettura secondo la checklist; ogni riga rimanda alla"
        " sezione o al frammento da leggere.",
        "",
        "## Materiale disponibile per il controllo",
        "",
        f"- Sezioni scritte: {len(sections)}. Pacchetto: {held['pack']} fonti;"
        f" testi integrali letti dal sistema: {fetched} documenti.",
    ]
    if held["full_text_pages"] or held["passages"]:
        lines.append(
            f"- La registrazione contiene {held['passages']} frammenti caricati e"
            f" {held['full_text_pages']} pagine di testo integrale: numeri e"
            " citazioni sono confrontati con tutto il materiale."
        )
    else:
        lines.append(
            "- La registrazione non contiene le pagine dei testi integrali né i"
            " frammenti caricati: numeri e citazioni sono confrontati solo con"
            " titoli, abstract ed estratti del pacchetto. «Non trovato» qui"
            " significa non presente in quel materiale, non assente dalle fonti."
        )
    bare = [
        heading(i)
        for i in sorted(sections)
        if i in evidence and not any(r.get("windows") for r in evidence[i])
    ]
    if bare:
        lines.append(
            "- Sezioni scritte senza documenti a testo integrale: "
            + "; ".join(bare)
            + "."
        )
    lines += ["", f"## Avvisi della generazione ({len(warnings)})", ""]
    if not warnings:
        lines.append("- Nessun avviso registrato.")
    grouped = defaultdict(list)
    for w in compact(warnings):
        grouped[w.get("section_index")].append(w)
    for index in sorted(grouped, key=lambda i: (i is not None, i or 0)):
        lines.append(f"### {'Generali' if index is None else heading(index)}")
        lines.append("")
        for w in grouped[index]:
            code = w.get("code", "")
            line = f"- [{code}] {LABELS.get(code, w.get('message_uk', code))}"
            if w.get("detail"):
                line += f": {fragment(w['detail'], 400)}"
            if code == "placeholder_text":
                still = placeholder_state(w, sections.get(index))
                if still is False:
                    line += (
                        " — storico: il rilevatore attuale (16.09.2026) non lo"
                        " considera un segnaposto, è italiano ordinario."
                    )
            lines.append(line)
        lines.append("")
    lines += ["## Numeri e citazioni non trovati nelle fonti disponibili", ""]
    missing_total = 0
    for index in sorted(sections):
        rows = [r for r in check_text(texts[index], haystack) if not r["found"]]
        if not rows:
            continue
        missing_total += len(rows)
        lines.append(f"### {heading(index)}")
        lines.append("")
        for r in rows:
            item = f"- [{KINDS.get(r['kind'], r['kind'])}] «{fragment(r['text'], 140)}» — non trovato nelle fonti disponibili"
            if r.get("partial"):
                item += f" (trovata in parte: «…{fragment(r['partial'], 70)}…»)"
            lines.append(item)
        lines.append("")
    if not missing_total:
        lines += [
            "- Nessuno: ogni numero e citazione controllati compaiono nel materiale disponibile.",
            "",
        ]
    lines += ["## Citazioni dirette senza pagina", ""]
    unpaged = [(i, q) for i in sorted(sections) for q in quotes_without_page(texts[i])]
    for index, (quote, citation) in unpaged:
        lines.append(f"- {heading(index)}: {quote} ({fragment(citation, 80)})")
    if not unpaged:
        lines.append("- Nessuna.")
    lines += [
        "",
        "## Non controllato qui",
        "",
        "- Corrispondenza al brief, cornice, metodologia, casi promessi, lingua e"
        " apparato: solo la lettura secondo la checklist.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--job-id", type=int, default=None)
    args = parser.parse_args()
    meta, events = load(args.recording)
    note = build_note(meta, events, args.job_id)
    args.output.write_text(note, encoding="utf-8")
    print(f"{args.output}: {len(note.splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
