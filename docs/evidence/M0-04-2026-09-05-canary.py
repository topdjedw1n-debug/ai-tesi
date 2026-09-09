"""Bounded public-metadata canary; no LLM, application DB, PDFs or generation.

Run with ENV_FILE=/dev/null and test-only settings. English terms and the two
representative section scopes below are prepared inputs, not generated outline
or translator proof. CitationVerifier cache is disabled to force current lookups.
"""

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.services.ai_pipeline.source_pack import MIN_CITABLE_SOURCES, SourcePackBuilder
from app.services.ai_pipeline.source_pack_preflight import preverify_source_pack
from app.services.background_jobs import _merge_source_packs
from app.services.citation_verifier import CitationVerifier

logging.basicConfig(level=logging.WARNING)


async def main():
    report = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "scope": "public bibliographic metadata only; no LLM, production DB, PDFs or DOCX",
        "topic": "Il ruolo dell’infermiere nell’area perinatale e nella transizione extrauterina del neonato",
        "alt_topic": "The role of the nurse in perinatal care and neonatal transition to extrauterine life",
        "section_titles": ["Assistenza infermieristica perinatale", "Adattamento neonatale alla vita extrauterina"],
        "alt_section_titles": ["Perinatal nursing care", "Neonatal adaptation to extrauterine life"],
        "input_boundary": "Founder-selected topic; English translation and two representative section scopes prepared manually for this canary, not the saved outline",
        "profile": {"target": 24, "minimum": 18, "reserve": 48, "min_on_topic_score": 0.35},
        "paid_calls": 0,
    }
    builder = SourcePackBuilder()
    common = dict(topic=report["topic"], language="it", document_id=0,
                  alt_topic=report["alt_topic"], min_on_topic_score=0.35,
                  raise_on_provider_error=True)

    async def check():
        initial = await builder.build(**common, target_size=24)
        report["initial"] = {
            "citable": len(initial.sources), "context": len(initial.context_sources),
            "underfilled": initial.underfilled, "provider_errors": initial.provider_errors,
        }
        print(json.dumps({"initial": report["initial"]}), flush=True)
        if initial.underfilled and len(initial.sources) < MIN_CITABLE_SOURCES:
            report["result"] = "provider_unavailable" if initial.provider_errors else "insufficient_initial_sources"
            return
        section_args = dict(section_titles=report["section_titles"],
                            alt_section_titles=report["alt_section_titles"],
                            target_size=48, allow_threshold_relaxation=False)
        section_pack = await builder.build(**common, **section_args)
        candidates = _merge_source_packs(initial, section_pack, limit=48)
        report["candidates"] = {
            "citable": len(candidates.sources), "provider_errors": candidates.provider_errors,
            "initial_keys_retained": set(initial.keys()).issubset(set(candidates.keys())),
        }
        print(json.dumps({"candidates": report["candidates"]}), flush=True)
        verifier = CitationVerifier(cache_enabled=False)
        outcome = await preverify_source_pack(candidates, verifier, target_size=24, minimum_verified=18)
        topped_up = False
        if outcome.needs_top_up:
            topped_up = True
            top_up = await builder.build(**common, **section_args, retrieval_page=2)
            candidates = _merge_source_packs(candidates, top_up, limit=96)
            outcome = await preverify_source_pack(candidates, verifier, target_size=24, minimum_verified=18)
        report["preflight"] = outcome.provenance_payload(top_up_attempted=topped_up)
        report["sources"] = [
            {"key": item.citation_key, "title": item.source.title,
             "authors": item.source.authors, "year": item.source.year,
             "doi": item.source.doi, "type": item.source.source_type,
             "relevance_score": item.on_topic_score,
             "verification_status": item.source.verification_status,
             "canonical_metadata": item.source.canonical_metadata}
            for item in outcome.pack.sources
        ]
        report["result"] = "pass" if outcome.meets_minimum else "insufficient_preverified_sources"

    try:
        await asyncio.wait_for(check(), timeout=300)
    except Exception as error:
        report["result"] = "error"
        report["error"] = f"{type(error).__name__}: {error}"
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    Path(sys.argv[1]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "sources"}, ensure_ascii=False), flush=True)
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
