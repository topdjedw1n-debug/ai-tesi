"""
Gold-set eval for CitationVerifier (LIVE bibliographic APIs - manual run only).

Run from apps/api (CWD matters: Settings reads .env):

    venv/bin/python -m evals.run_citation_eval                 # full run, no cache
    venv/bin/python -m evals.run_citation_eval --limit 3       # smoke
    venv/bin/python -m evals.run_citation_eval --ids cit-mis-001,cit-nf-002

By default the Redis cache is BYPASSED (cache_enabled=False) so repeat runs
measure the verifier, not the cache; --use-cache opts back in. The verifier's
own per-provider rate limits and concurrency semaphore are reused untouched,
so live APIs are respected. Reports land in eval_reports/ (gitignored).
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from app.services.citation_verifier import CitationVerifier, SourceInput
from app.services.source_verification_stage import map_verification_status
from evals.common import (
    CITATION_EXPECTED_LABELS,
    CITATION_PREDICTED_LABELS,
    DATASETS_DIR,
    confusion_matrix,
    load_citation_dataset,
    per_class_metrics,
    print_report,
    select_cases,
    write_json_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate CitationVerifier against the gold citation set"
    )
    parser.add_argument("--dataset", default=str(DATASETS_DIR / "citations_gold.yaml"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", default=None, help="comma-separated case ids")
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="opt back into the Redis cache (default: bypassed)",
    )
    parser.add_argument("--report-out", default="eval_reports")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    dataset = load_citation_dataset(args.dataset)
    cases = select_cases(dataset.cases, args.ids, args.limit)
    if not cases:
        print("No cases selected.")
        return 1

    print(
        f"Running citation eval: {len(cases)} case(s), "
        f"cache={'ON' if args.use_cache else 'BYPASSED'} (live APIs, be patient)"
    )

    verifier = CitationVerifier(cache_enabled=args.use_cache)
    inputs = [
        SourceInput(
            title=case.source.title,
            authors=list(case.source.authors),
            year=case.source.year,
            doi=case.source.doi,
            arxiv_id=case.source.arxiv_id,
        )
        for case in cases
    ]
    # Order-preserving and never raises (contract of verify_sources)
    results = await verifier.verify_sources(inputs)

    records: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    expected_list: list[str] = []
    predicted_list: list[str] = []
    failed_count = 0

    for case, result in zip(cases, results, strict=True):
        predicted = map_verification_status(result)
        correct = predicted == case.expected
        if predicted == "failed":
            failed_count += 1
        details = {
            "raw_status": result.status.value,
            "match_score": result.match_score,
            "provider": result.provider,
            "resolved_title": result.title,
            "resolved_doi": result.doi,
            "reason": result.reason,
            "from_cache": result.from_cache,
        }
        record = {
            "id": case.id,
            "group": case.group,
            "expected": case.expected,
            "predicted": predicted,
            "correct": correct,
            "details": details,
        }
        records.append(record)
        expected_list.append(case.expected)
        predicted_list.append(predicted)
        if not correct:
            mismatches.append(
                {
                    "id": case.id,
                    "expected": case.expected,
                    "predicted": predicted,
                    **details,
                }
            )

    matrix = confusion_matrix(
        expected_list,
        predicted_list,
        CITATION_EXPECTED_LABELS,
        CITATION_PREDICTED_LABELS,
    )
    metrics = per_class_metrics(matrix)
    print_report("Citation verification gold-set eval", matrix, metrics, mismatches)

    if failed_count:
        print(
            f"\n⚠️  {failed_count} case(s) predicted 'failed' (unresolvable). "
            "These usually reflect provider outages/rate limiting, not verifier "
            "quality - consider re-running."
        )

    from app.services.citation_verifier import FUZZY_MATCH_THRESHOLD

    report_path = write_json_report(
        kind="citation",
        dataset_path=args.dataset,
        records=records,
        metrics={"matrix": matrix, **metrics},
        config_snapshot={
            "fuzzy_match_threshold": FUZZY_MATCH_THRESHOLD,
            "cache_enabled": args.use_cache,
        },
        out_dir=args.report_out,
    )
    print(f"\nJSON report: {report_path}")
    return 0


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
