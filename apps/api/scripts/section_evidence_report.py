"""Offline report: which page windows each section of a recorded job would get.

Usage: python scripts/section_evidence_report.py RECORDING.json.gz OUT_DIR --job-id N
         [--uploaded-sources SPEC.json] [--open-access-lookup] [--fetch]

No model call. The recorded scopes, plan and pack are loaded; optional
manager-style uploads are parsed by the production code; with
--open-access-lookup the DOIs of the pack are resolved through OpenAlex (what
today's search rows would carry) and with --fetch the production fetcher
downloads those PDFs. Then the production section_evidence() runs for every
section and the texts the writer would receive are written to OUT_DIR.
"""

import argparse
import asyncio
import gzip
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ENV = {
    "ENV_FILE": "/dev/null",
    "ENVIRONMENT": "test",
    "DEBUG": "true",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "SECRET_KEY": "offline-report-only-secret-never-an-account",
    "JWT_SECRET": "offline-report-only-secret-never-an-account",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--uploaded-sources", type=Path)
    parser.add_argument("--open-access-lookup", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    os.environ.update(ENV)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    args.output.mkdir(parents=True, exist_ok=False)
    report = asyncio.run(run(args))
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(report["markdown"])
    return 0


async def run(args):
    import httpx
    from s4_lab import load_uploaded_sources, uploaded_inputs

    from app.services.ai_pipeline.rag_retriever import SourceDoc
    from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
    from app.services.executor_v2.scopes import flatten
    from app.services.executor_v2.sections import FULL_TEXT_RULE
    from app.services.full_text_sources import (
        SECTION_EVIDENCE_CHARS,
        attach_full_text,
        section_evidence,
    )
    from app.services.source_evidence import evidence_text, freeze_evidence
    from app.services.uploaded_sources import SourcePassage

    raw = args.recording.read_bytes()
    data = json.loads(gzip.decompress(raw) if args.recording.suffix == ".gz" else raw)
    events = data.get("document_provenance", data.get("provenance", []))

    def last(event_type):
        rows = [
            e["payload"]
            for e in events
            if e.get("event_type") == event_type
            and (e.get("payload") or {}).get("job_id", args.job_id) == args.job_id
        ]
        if not rows:
            raise SystemExit(f"recording has no {event_type} for job {args.job_id}")
        return rows[-1]

    inputs = last("generation_replay_inputs")["executor_inputs"]
    nodes = flatten(last("executor_scopes")["nodes"])
    sections = last("executor_outline")["sections"]
    topic = inputs["brief"]["topic"]
    passages = [SourcePassage(**p) for p in inputs["passages"]]
    sources = []
    for row in last("executor_source_pack")["sources"]:
        source = SourceDoc(**row["source"])
        sources.append(PackedSource(source, row["citation_key"], row["on_topic_score"]))
    report = {
        "recording": str(args.recording),
        "job_id": args.job_id,
        "sections": len(sections),
        "pack_sources": len(sources),
        "uploaded_sources": [],
        "open_access": [],
        "per_section": [],
    }
    if args.uploaded_sources:
        specs = load_uploaded_sources(args.uploaded_sources)
        rows, extra, report["uploaded_sources"] = uploaded_inputs(
            specs, args.uploaded_sources.parent
        )
        passages += [SourcePassage(**p) for p in extra]
        for row in rows:
            source = SourceDoc(**row["source"])
            source.verification_status = "verified"
            source.canonical_metadata = {
                "origin": "pdf",
                "verification_provider": "PDF",
            }
            freeze_evidence(source, passages, row["key"], query=topic)
            source.canonical_metadata["evidence_level"] = "pdf"
            sources.insert(0, PackedSource(source, row["key"], 1.0))
    if args.open_access_lookup:
        async with httpx.AsyncClient(timeout=30) as client:
            for packed in sources:
                doi = packed.source.doi
                if not doi:
                    continue
                response = await client.get(
                    f"https://api.openalex.org/works/doi:{doi}",
                    params={"select": "open_access,best_oa_location"},
                )
                if response.status_code != 200:
                    continue
                work = response.json()
                url = (work.get("best_oa_location") or {}).get("pdf_url") or (
                    work.get("open_access") or {}
                ).get("oa_url")
                if url:
                    packed.source.canonical_metadata = {
                        **(packed.source.canonical_metadata or {}),
                        "open_access_url": url,
                    }
                    report["open_access"].append(
                        {"key": packed.citation_key, "url": url}
                    )
        if args.fetch:
            summary, unavailable = await attach_full_text(
                sources, passages, asyncio.Semaphore(4), topic
            )
            report["fetch"] = {"sources": summary, "unavailable": unavailable}
    pack = SourcePack(0, topic, sources=sources, passages=passages)
    lines = [
        "| § | Розділ | Документи (заплановані / доповнені) | Вікна | Сторінки | Символів | Правило |",
        "|---|---|---|---|---:|---|---:|---|".replace(
            "|---|---|---|---|---:|---|---:|---|", "|---|---|---|---:|---|---:|---|"
        ),
    ]
    for section in sections:
        items, selection = section_evidence(pack, section, nodes)
        text = "\n\n".join(f"### [{i['key']}]\n{i['text']}" for i in items)
        index = section["section_index"]
        (args.output / f"section-{index:02d}-evidence.txt").write_text(text)
        full = any(r["windows"] for r in selection)
        docs = ", ".join(f"{r['key']}{'' if r['planned'] else '+'}" for r in selection)
        pages = "; ".join(
            f"{r['key']}: {','.join(map(str, r['pages']))}"
            for r in selection
            if r["pages"]
        )
        chars = sum(r["chars"] for r in selection)
        report["per_section"].append(
            {
                "section_index": index,
                "title": section["title"],
                "evidence": selection,
                "chars": chars,
                "full_text_rule": full,
            }
        )
        lines.append(
            f"| {index} | {section['title'][:48]} | {docs} | "
            f"{sum(r['windows'] for r in selection)} | {pages} | {chars} | "
            f"{'так' if full else '—'} |"
        )
    with_full = sum(1 for r in report["per_section"] if r["full_text_rule"])
    lines.append("")
    lines.append(
        f"Розділів із повнотекстовими доказами: {with_full} з {len(sections)}; "
        f"бюджет на розділ {SECTION_EVIDENCE_CHARS} символів; "
        f"правило S4: «{FULL_TEXT_RULE.strip()[:60]}…»."
    )
    report["markdown"] = "\n".join(lines)
    report["pack"] = [
        {
            "key": p.citation_key,
            "title": p.source.title,
            "evidence_level": (p.source.canonical_metadata or {}).get("evidence_level"),
            "windows": sum(1 for w in passages if w.citation_key == p.citation_key),
            "excerpt_chars": len(evidence_text(p.source) or ""),
        }
        for p in sources
    ]
    report["passages_total"] = len(passages)
    _ = asdict  # kept for symmetry with the lab's input builder
    return report


if __name__ == "__main__":
    raise SystemExit(main())
