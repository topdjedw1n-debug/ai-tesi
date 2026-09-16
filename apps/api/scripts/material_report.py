"""Offline proof of the material fix on a recorded run ($0, no model call).

Usage: python scripts/material_report.py RECORDING.json.gz OUT_DIR --job-id N

From the recording (all provenance rows, including the recorded catalogue
answers, verifications and full-text pages) the script rebuilds the S2 pack
with the production seating code, runs the production plan check on the
recorded plan and the production section exam for every section, and prints
BEFORE (what the run actually did, from its recorded events) against AFTER
(what the current code does on the same recorded inputs):

- pack seats: which verified candidates are in, coverage per node by the
  nodes' own terms, and which records with a node's own terms were seated;
- per section: the documents that hand the writer pages or an excerpt, with
  their reason (support / windows / unsuitable / capped);
- writing order of the frame sections.

Full texts are the pages the run recorded; a newly seated record whose PDF
was never fetched in this run stays on its abstract (stated as such).
"""

import argparse
import asyncio
import gzip
import json
import os
import sys
from collections import Counter
from pathlib import Path

ENV = {
    "ENV_FILE": "/dev/null",
    "ENVIRONMENT": "test",
    "DEBUG": "true",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "SECRET_KEY": "offline-material-report-secret-never-an-account",
    "JWT_SECRET": "offline-material-report-secret-never-an-account",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()
    os.environ.update(ENV)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    args.output.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run(args))
    (args.output / "material-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1)
    )
    (args.output / "material-report.md").write_text(report["markdown"])
    print(report["markdown"])
    return 0


async def run(args):
    from app.services.academic_context import digest
    from app.services.ai_pipeline.rag_retriever import SourceDoc
    from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
    from app.services.executor_v2.budgets import POLICY
    from app.services.executor_v2.scopes import flatten
    from app.services.full_text_sources import (
        document_windows,
        open_access_link,
        section_evidence,
    )
    from app.services.material_fit import covers
    from app.services.pack_seats import scope_metadata, seat
    from app.services.plan_check import review
    from app.services.search_queries import is_structural, on_topic, plan
    from app.services.section_material import writing_order
    from app.services.source_evidence import evidence_text, freeze_evidence
    from app.services.uploaded_sources import SourcePassage

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
            raise SystemExit(f"recording has no {kind}")
        return rows[-1]

    deps = [
        e["payload"] for e in events if e.get("event_type") == "generation_dependency"
    ]
    inputs = last("generation_replay_inputs")["executor_inputs"]
    tree = last("executor_scopes")["nodes"]
    nodes = flatten(tree)
    topic = inputs["brief"]["topic"]
    queries, parents, anchors = plan(topic, tree)
    # --- BEFORE: the recorded pack and the recorded section evidence ---
    recorded_pack = last("executor_source_pack")["sources"]
    recorded_evidence = {
        e["payload"]["section_index"]: e["payload"]["evidence"]
        for e in events
        if e.get("event_type") == "executor_section_evidence"
    }
    outline = last("executor_outline")["sections"]
    written = [
        e["payload"]["section_index"]
        for e in events
        if e.get("event_type") == "executor_section"
    ]
    # --- AFTER: rebuild the candidates from the recorded catalogue answers ---
    searches = {
        d["input_fingerprint"]: d for d in deps if d.get("kind") == "executor_search"
    }
    verifies = {
        d["input_fingerprint"]: d for d in deps if d.get("kind") == "executor_verify"
    }
    candidates = {}
    for scope_id, query in queries:
        for provider in ("semantic_scholar", "crossref", "openalex"):
            row = searches.get(digest({"provider": provider, "query": query}))
            if not row or row.get("outcome") != "received":
                continue
            for hit in row["response"] or []:
                if not on_topic(hit, anchors):
                    continue
                identity = (hit.get("doi") or hit["title"]).strip().lower()
                item = candidates.setdefault(identity, {"source": hit, "scopes": set()})
                item["scopes"].update({scope_id, parents.get(scope_id)})
                if not item["source"].get("abstract") and hit.get("abstract"):
                    item["source"]["abstract"] = hit["abstract"]
    checked = []
    unverified = 0
    for item in candidates.values():
        verify = verifies.get(digest({"candidate": item["source"]}))
        metadata = (verify or {}).get("response") if verify else None
        if not metadata or metadata.get("status") != "verified":
            unverified += 1
            continue
        row = {
            **item["source"],
            **{
                k: metadata[k]
                for k in ("title", "authors", "year", "doi", "venue")
                if metadata.get(k)
            },
        }
        row["abstract"] = metadata.get("abstract") or row.get("abstract")
        source = SourceDoc(**row)
        source.verification_status = "verified"
        source.canonical_metadata = {
            **metadata,
            "origin": "pack",
            "verification_provider": metadata["provider"],
            "query_scope_ids": sorted(filter(None, item["scopes"])),
            **scope_metadata(source, nodes, parents),
        }
        if open_access_link(item["source"]):
            source.canonical_metadata["open_access_url"] = open_access_link(
                item["source"]
            )
        key = (
            "K"
            + digest({"doi": source.doi, "title": source.title, "year": source.year})[
                :12
            ]
        )
        freeze_evidence(source, [], key)
        source.canonical_metadata["evidence_level"] = (
            "abstract" if evidence_text(source) else "none"
        )
        checked.append(PackedSource(source, key, 1.0))
    selected, coverage = seat(
        checked,
        nodes,
        minimum=POLICY["minimum_evidence_sources"],
        max_sources=POLICY["max_sources"],
    )
    # Full texts: the pages this run recorded, attached to whichever seated
    # record shares the same open-access URL (never fetched again).
    pages_by_url = {
        d["request"]["url"]: (d.get("response") or {}).get("pages") or []
        for d in deps
        if d.get("kind") == "executor_full_text"
    }
    passages = [SourcePassage(**p) for p in inputs.get("passages") or []]
    fetched_keys, not_fetched = [], []
    for row in selected:
        url = (row.source.canonical_metadata or {}).get("open_access_url")
        pages = pages_by_url.get(url) if url else None
        if pages:
            windows = document_windows(row.citation_key, url, pages)
            passages.extend(windows)
            freeze_evidence(row.source, passages, row.citation_key, query=topic)
            row.source.canonical_metadata["evidence_level"] = "pdf"
            fetched_keys.append(row.citation_key)
        elif url and url not in pages_by_url:
            not_fetched.append(row.citation_key)
    pack = SourcePack(0, topic, sources=selected, passages=passages)
    # The recorded plan named keys of the recorded pack; S3 is not re-run
    # offline, so a section's keys are the recorded ones still in the pack
    # plus the new pack's records tagged with the section's own scopes (what
    # the planner picks from the pack listing), most own terms first.
    sections = [dict(s) for s in outline]
    for section in sections:
        wanted = set(section.get("scope_ids") or [])
        keys = [k for k in section.get("evidence_keys") or [] if pack.by_key(k)]
        tagged = sorted(
            (
                p
                for p in selected
                if wanted
                & set((p.source.canonical_metadata or {}).get("scope_hits") or {})
                and p.citation_key not in keys
            ),
            key=lambda p: -sum(
                v
                for k, v in (p.source.canonical_metadata or {})["scope_hits"].items()
                if k in wanted
            ),
        )
        section["evidence_keys"] = keys + [p.citation_key for p in tagged[:3]]
    plan_warnings = review(sections, pack, nodes)
    per_section = []
    for section in sections:
        items, selection = section_evidence(pack, section, nodes)
        per_section.append({"section": section, "selection": selection})
    order = [s["section_index"] for s in writing_order(sections)]

    # --- tables ---
    title_of = {p.citation_key: p.source.title for p in selected}
    rec_title = {r["citation_key"]: r["source"]["title"] for r in recorded_pack}
    node_title = {n["scope_id"]: n["title"] for n in nodes}

    def own_hits(text):
        return {n["scope_id"]: covers(n, text) for n in nodes if covers(n, text)}

    lines = [f"# Material report — {topic[:90]} (job {args.job_id})", ""]
    lines.append(
        f"Recorded candidates on topic: {len(candidates)}; verified: {len(checked)} (dropped or unverified: {unverified})."
    )
    lines.append(
        f"BEFORE pack: {len(recorded_pack)} sources; AFTER pack: {len(selected)} sources; in common: {len(set(rec_title) & set(title_of))}."
    )
    lines.append(
        f"Full texts recorded in this run: {len(pages_by_url)} links with pages: {sum(1 for p in pages_by_url.values() if p)}; seated AFTER with pages: {len(fetched_keys)}; seated AFTER whose PDF was never fetched in this run: {len(not_fetched)}."
    )
    lines += [
        "",
        "## Coverage per node (records with readable text carrying the node's own terms)",
        "",
        "| Node | BEFORE (query-credited) | AFTER (own terms) |",
        "|---|---:|---:|",
    ]
    before_cov = Counter()
    for r in recorded_pack:
        for sid in (r["source"].get("canonical_metadata") or {}).get("scope_ids", []):
            if evidence_text(SourceDoc(**r["source"])):
                before_cov[sid] += 1
    for n in nodes:
        if is_structural(n):
            continue
        lines.append(
            f"| {n['title'][:60]} | {before_cov.get(n['scope_id'], 0)} | {coverage.get(n['scope_id'], 0)} |"
        )
    lines += [
        "",
        "## Records with a node's own terms: seated?",
        "",
        "| Node | verified records with own terms | seated BEFORE | seated AFTER |",
        "|---|---:|---:|---:|",
    ]
    seated_after = {p.citation_key for p in selected}
    for n in nodes:
        if is_structural(n) or n.get("children"):
            continue
        own = [
            p
            for p in checked
            if covers(n, f"{p.source.title} {p.source.abstract or ''}")
        ]
        before = sum(
            1
            for r in recorded_pack
            if covers(n, f"{r['source']['title']} {r['source'].get('abstract') or ''}")
        )
        after = sum(1 for p in own if p.citation_key in seated_after)
        lines.append(f"| {n['title'][:60]} | {len(own)} | {before} | {after} |")
    lines += [
        "",
        "## Sections: documents handing the writer material",
        "",
        "| § | Section | BEFORE (recorded) | AFTER (current code) |",
        "|---|---|---|---|",
    ]
    for entry in per_section:
        s = entry["section"]
        idx = s["section_index"]
        before = recorded_evidence.get(idx, [])
        b = ", ".join(
            f"{rec_title.get(r['key'], r['key'])[:28]}{'★' if r['windows'] else ''}"
            for r in before
            if r.get("windows") or r.get("chars")
        )
        a = ", ".join(
            f"{title_of.get(r['key'], r['key'])[:28]}{'★' if r['windows'] else ''}[{r['reason']}]"
            for r in entry["selection"]
            if r["reason"] != "unsuitable" and (r["windows"] or r["chars"])
        )
        dropped = ", ".join(
            title_of.get(r["key"], r["key"])[:24]
            for r in entry["selection"]
            if r["reason"] == "unsuitable"
        )
        lines.append(
            f"| {idx} | {s['title'][:40]} | {b} | {a}{' — dropped: ' + dropped if dropped else ''} |"
        )
    lines += [
        "",
        f"Plan check warnings AFTER: {plan_warnings}",
        f"Writing order BEFORE (recorded): {written}",
        f"Writing order AFTER: {order}",
        "",
        "★ = pages (windows); no star = excerpt only.",
    ]
    return {
        "job_id": args.job_id,
        "candidates": len(candidates),
        "verified": len(checked),
        "pack_before": [rec_title[k] for k in rec_title],
        "pack_after": [title_of[k] for k in title_of],
        "coverage_after": {node_title[k]: v for k, v in coverage.items()},
        "not_fetched": [title_of[k] for k in not_fetched],
        "plan_warnings": plan_warnings,
        "order_before": written,
        "order_after": order,
        "sections": [
            {
                "section_index": e["section"]["section_index"],
                "title": e["section"]["title"],
                "selection": [
                    {**r, "title": title_of.get(r["key"], r["key"])}
                    for r in e["selection"]
                ],
            }
            for e in per_section
        ],
        "markdown": "\n".join(lines),
    }


if __name__ == "__main__":
    sys.exit(main())
