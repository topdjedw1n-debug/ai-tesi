"""Re-assemble a recorded work with the current citation rendering and DOCX
formatting, without any model call.

Usage: python scripts/rerender_recording.py RECORDING.json.gz OUT.docx --job-id N
       [--notes] [--web-sources WEB.json]

Takes the recorded plan, pack and section texts with their raw citation
markers, renders citations with the production S5 renderer, assembles the
document with the production assembly (levels, numbering, typography,
bibliography lists) and writes the DOCX exactly as the export route would.
The advisory S6 review is not repeated. Prints what changed in numbers.

--notes renders the Italian traditional style instead of the brief's style:
every citation becomes a Word footnote (citation_notes). WEB.json maps a
citation key to {"site", "url", "accessed"} for web pages uploaded as PDFs:
they are cited by URL without pages and listed under the web-sources heading.
"""

import argparse
import gzip
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ENV = {
    "ENV_FILE": "/dev/null",
    "ENVIRONMENT": "test",
    "DEBUG": "true",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "SECRET_KEY": "offline-rerender-only-secret-never-an-account-key",
    "JWT_SECRET": "offline-rerender-only-secret-never-an-account-key",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--notes", action="store_true")
    parser.add_argument("--web-sources", type=Path)
    args = parser.parse_args()
    os.environ.update(ENV)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from docx import Document as DocxDocument

    from app.services.ai_pipeline.citation_formatter import CitationStyle
    from app.services.ai_pipeline.rag_retriever import SourceDoc
    from app.services.citation_notes import render_notes
    from app.services.citation_render import render_citations
    from app.services.docx_export import (
        add_footnotes,
        add_table_of_contents,
        append_markdown,
        apply_academic_profile,
        assemble_document,
        normalize_typography,
        with_chapter_headings,
    )
    from app.services.executor_v2.sections import MARKER

    raw = args.recording.read_bytes()
    data = json.loads(gzip.decompress(raw) if args.recording.suffix == ".gz" else raw)
    events = [
        e
        for e in data.get("document_provenance", data.get("provenance", []))
        if (e.get("payload") or {}).get("job_id", args.job_id) == args.job_id
    ]

    def last(kind):
        rows = [e["payload"] for e in events if e.get("event_type") == kind]
        if not rows:
            raise SystemExit(f"no {kind} in the recording")
        return rows[-1]

    inputs = last("generation_replay_inputs")["executor_inputs"]
    brief = inputs["brief"]
    nodes = last("executor_scopes")["nodes"]
    levels = {}

    def walk(items, depth):
        for node in items:
            levels[node["scope_id"]] = depth
            walk(node.get("children", []), depth + 1)

    walk(nodes, 1)
    outline = {s["section_index"]: s for s in last("executor_outline")["sections"]}
    known = {}
    for row in last("executor_source_pack")["sources"]:
        known[row["citation_key"]] = SourceDoc(**row["source"])
    for row in inputs.get("library", []):
        if row.get("verification_status") == "verified":
            source = SourceDoc(**row["source"])
            source.canonical_metadata = {
                **(source.canonical_metadata or {}),
                "verification_provider": row["verification_provider"],
                "origin": "library",
            }
            known.setdefault(row["key"], source)
    sections = {}
    for e in events:
        if e.get("event_type") == "executor_section":
            sections[e["payload"]["section_index"]] = e["payload"]
    style = CitationStyle(brief["citation_style"])
    entries, rendered, missing_total = {}, [], 0
    raws = [
        sections[i].get("raw_content") or sections[i]["content"]
        for i in sorted(sections)
    ]
    notes = []
    if args.notes:
        web = json.loads(args.web_sources.read_text()) if args.web_sources else {}
        raws, notes, entries, missing = render_notes(raws, known, web)
        missing_total = len(missing)
    for index, raw_text in zip(sorted(sections), raws, strict=True):
        section = sections[index]
        text = raw_text
        if not args.notes:
            text, found, missing = render_citations(raw_text, known, style, MARKER)
            missing_total += len(missing)
            entries.update({k: v for k, v in found.items() if k not in entries})
        plan = outline.get(index, {})
        rendered.append(
            {
                "title": section["title"],
                "content": text,
                "scope_ids": plan.get("scope_ids", []),
                "level": min(
                    (levels[s] for s in plan.get("scope_ids", []) if s in levels),
                    default=1,
                ),
            }
        )
    content = assemble_document(
        with_chapter_headings(rendered, nodes),
        list(entries.values()),
        brief["language"],
    )
    docx = DocxDocument()
    docx.core_properties.title = str(brief.get("title") or "")
    docx.core_properties.author = ""
    docx.core_properties.last_modified_by = ""
    docx.core_properties.comments = ""
    stamp = datetime.fromisoformat(inputs["exported_at"]).replace(tzinfo=None)
    docx.core_properties.created = docx.core_properties.modified = stamp
    apply_academic_profile(docx)
    docx.add_heading(brief["title"], 0)
    add_table_of_contents(docx, brief["language"])
    append_markdown(docx, content)
    if notes:
        add_footnotes(docx, [normalize_typography(n) for n in notes])
    stream = io.BytesIO()
    docx.save(stream)
    args.output.write_bytes(stream.getvalue())
    quotes = re.findall(r"«[^»]{20,}»\s*\(([^)]*)\)", content)
    print(
        json.dumps(
            {
                "sections": len(rendered),
                "levels": {
                    str(k): sum(1 for r in rendered if r["level"] == k)
                    for k in (1, 2, 3)
                },
                "bibliography": {
                    "academic": sum(
                        1 for e in entries.values() if e["kind"] == "academic"
                    ),
                    "legal": sum(1 for e in entries.values() if e["kind"] == "legal"),
                    "web": sum(1 for e in entries.values() if e["kind"] == "web"),
                },
                "footnotes": len(notes),
                "markers_without_source": missing_total,
                "quotes_with_citation": len(quotes),
                "quotes_without_page": sum(
                    1 for q in quotes if " p. " not in q and " pp. " not in q
                ),
                "bytes": len(stream.getvalue()),
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
