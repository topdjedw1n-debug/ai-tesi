#!/usr/bin/env python3
"""
Local grounding report for a generated document (read-only).

Computes local quality-proxy metrics for an already-generated document and
emits a Compilatio-ready plain-text artifact for manual upload. It does NOT
call any external AI detector and makes NO claim about detector scores — the
authoritative check is uploading the emitted artifact to Compilatio/GPTZero.

Usage:
    python apps/api/scripts/grounding_report.py <document_id> [--out DIR]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile

# Make `import app...` work regardless of the current working directory.
_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

from sqlalchemy import select  # noqa: E402

from app.core import database  # noqa: E402
from app.models.document import Document, DocumentSection  # noqa: E402
from app.services.quality_metrics import (  # noqa: E402
    burstiness,
    citation_grounding_rate,
    connector_cliche_density,
    evidence_presence,
    hedging_density,
    outline_adherence,
    sentence_length_stats,
)
from app.services.source_verification_stage import load_source_pack  # noqa: E402


async def _build_report(document_id: int) -> dict:
    async with database.AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        if document is None:
            raise SystemExit(f"Document {document_id} not found")

        sections_result = await db.execute(
            select(DocumentSection)
            .where(DocumentSection.document_id == document_id)
            .order_by(DocumentSection.section_index.asc())
        )
        sections = list(sections_result.scalars().all())
        pack = await load_source_pack(db, document_id)

        language = str(document.language or "en")
        promised = (document.outline or {}).get("sections", []) or []
        delivered = [
            {
                "title": s.title,
                "word_count": s.word_count,
                "content": s.content or "",
            }
            for s in sections
        ]

        section_reports = []
        full_text_parts = []
        for s in sections:
            content = s.content or ""
            full_text_parts.append(f"{s.title}\n\n{content}")
            rep = {
                "section_index": s.section_index,
                "title": s.title,
                "sentence_stats": sentence_length_stats(content),
                "burstiness": burstiness(content),
                "connector_cliche": connector_cliche_density(content, language),
                "hedging": hedging_density(content, language),
                "has_evidence": evidence_presence(content, pack),
            }
            if pack is not None:
                rep["grounding_rate"] = citation_grounding_rate(
                    {"content": content}, pack
                )
            section_reports.append(rep)

        pack_summary = None
        if pack is not None:
            scores = [ps.on_topic_score for ps in pack.sources]
            pack_summary = {
                "size": len(pack.sources),
                "mean_on_topic_score": (
                    round(sum(scores) / len(scores), 3) if scores else 0.0
                ),
                "min_on_topic_score": round(min(scores), 3) if scores else 0.0,
                "underfilled": pack.underfilled,
                "keys": pack.keys(),
            }

        grounding_rates = [
            r["grounding_rate"] for r in section_reports if "grounding_rate" in r
        ]
        return {
            "document_id": document_id,
            "topic": document.topic,
            "language": language,
            "status": document.status,
            "source_pack": pack_summary,
            "outline_adherence": outline_adherence(promised, delivered),
            "aggregate": {
                "sections": len(section_reports),
                "mean_grounding_rate": (
                    round(sum(grounding_rates) / len(grounding_rates), 3)
                    if grounding_rates
                    else None
                ),
                "sections_with_evidence": sum(
                    1 for r in section_reports if r["has_evidence"]
                ),
            },
            "sections": section_reports,
            "_full_text": "\n\n".join(full_text_parts),
        }


def _print_report(report: dict, artifact_path: str) -> None:
    print("=" * 72)
    print(f"GROUNDING REPORT — document {report['document_id']} ({report['language']})")
    print(f"Topic : {report['topic']}")
    print(f"Status: {report['status']}")
    print("=" * 72)

    pack = report["source_pack"]
    if pack is None:
        print("Source pack : NONE (SOURCE_GROUNDING_ENABLED was off for this run)")
    else:
        print(
            f"Source pack : {pack['size']} sources, "
            f"mean on-topic {pack['mean_on_topic_score']}, "
            f"min {pack['min_on_topic_score']}"
            + (" [UNDERFILLED]" if pack["underfilled"] else "")
        )

    adh = report["outline_adherence"]
    print(
        f"Outline     : {adh['delivered_sections']}/{adh['promised_sections']} "
        f"delivered (adherence {adh['adherence']}, "
        f"fully_delivered={adh['fully_delivered']})"
    )
    agg = report["aggregate"]
    print(
        f"Aggregate   : mean grounding {agg['mean_grounding_rate']}, "
        f"{agg['sections_with_evidence']}/{agg['sections']} sections with evidence"
    )
    print("-" * 72)
    for r in report["sections"]:
        gr = r.get("grounding_rate", "n/a")
        print(
            f"[{r['section_index']:>2}] {str(r['title'])[:40]:<40} "
            f"grounding={gr} burst={r['burstiness']} "
            f"cliche/1k={r['connector_cliche']['per_1000_words']} "
            f"hedge/1k={r['hedging']['per_1000_words']} "
            f"evidence={r['has_evidence']}"
        )
    print("-" * 72)
    print("NOTE: local proxy metrics only — NOT a detector score.")
    print(f"Compilatio-ready artifact written to:\n  {artifact_path}")
    print("Upload it to Compilatio/GPTZero for the authoritative AI/plagiarism score.")
    print("=" * 72)
    # Machine-readable dump (drop the bulky text body).
    dump = {k: v for k, v in report.items() if k != "_full_text"}
    print(json.dumps(dump, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Local grounding report")
    parser.add_argument("document_id", type=int)
    parser.add_argument(
        "--out",
        default=os.path.join(tempfile.gettempdir(), "thesica_grounding"),
        help="Directory for the Compilatio-ready artifact",
    )
    args = parser.parse_args()

    report = asyncio.run(_build_report(args.document_id))

    os.makedirs(args.out, exist_ok=True)
    artifact_path = os.path.join(args.out, f"document_{args.document_id}.txt")
    with open(artifact_path, "w", encoding="utf-8") as fh:
        fh.write(report["_full_text"])

    _print_report(report, artifact_path)


if __name__ == "__main__":
    main()
