"""
Gold-set eval for ClaimVerifier's LLM judgment (PAID LLM calls - manual only).

Run from apps/api (CWD matters: Settings reads .env):

    venv/bin/python -m evals.run_claim_eval --dry-run         # zero-cost preview
    venv/bin/python -m evals.run_claim_eval --max-llm-claims 5 --yes
    venv/bin/python -m evals.run_claim_eval --yes             # full run

CitedClaim objects are constructed directly from the dataset (bypassing
extract_claims/source matching, which stay covered by free unit tests), so
this measures ONLY the LLM verdict quality. Cases sharing a source_key share
one synthetic source_id, exercising the S1..Sn prompt abstract dedup.

Cost control: cases are sliced to --max-llm-claims BEFORE the call and the
budget passed to verify_claims equals the slice size, so no scored case can
fall into the REASON_BUDGET 'uncertain' bucket and pollute the metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import math
from typing import Any

from app.core.config import settings
from app.services.ai_service import AIService
from app.services.claim_verifier import CitedClaim, ClaimVerifier
from evals.common import (
    CLAIM_LABELS,
    DATASETS_DIR,
    confusion_matrix,
    load_claim_dataset,
    per_class_metrics,
    print_report,
    select_cases,
    write_json_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate ClaimVerifier's LLM judgment on the gold claim set"
    )
    parser.add_argument("--dataset", default=str(DATASETS_DIR / "claims_gold.yaml"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", default=None, help="comma-separated case ids")
    parser.add_argument(
        "--max-llm-claims",
        type=int,
        default=None,
        help="cost cap: at most this many claims are sent (default: all selected)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=f"claims per prompt (default: {settings.CLAIM_VERIFICATION_BATCH_SIZE})",
    )
    parser.add_argument("--report-out", default="eval_reports")
    parser.add_argument("--dry-run", action="store_true", help="print plan, no calls")
    parser.add_argument("--yes", action="store_true", help="skip cost confirmation")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    dataset = load_claim_dataset(args.dataset)
    cases = select_cases(dataset.cases, args.ids, args.limit)
    if args.max_llm_claims is not None:
        cases = cases[: max(0, args.max_llm_claims)]
    if not cases:
        print("No cases selected.")
        return 1

    batch_size = args.batch_size or settings.CLAIM_VERIFICATION_BATCH_SIZE
    llm_calls = math.ceil(len(cases) / max(1, batch_size))
    chain = settings.AI_FALLBACK_CHAIN_LIST
    first_provider = f"{chain[0][0]}/{chain[0][1]}" if chain else "?"
    print(
        f"Plan: {len(cases)} claim(s) -> {llm_calls} LLM call(s) "
        f"(batch={batch_size}) via {first_provider}"
    )
    if args.dry_run:
        print("Dry run - no LLM calls made.")
        return 0
    if not args.yes:
        answer = input("Proceed with paid LLM calls? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1

    # Synthetic shared source ids: cases with the same source_key cite the
    # same source, so the prompt dedups their abstract into one S-block
    source_ids: dict[str, int] = {}
    claims = []
    for case in cases:
        source_id = source_ids.setdefault(case.source_key, len(source_ids) + 1)
        claims.append(
            CitedClaim(
                sentence=case.sentence,
                citation_text=case.citation_text,
                source_id=source_id,
                source_title=case.source_title,
                abstract=case.abstract,
            )
        )

    # call_with_fallback never touches AIService.db -> no session needed
    verifier = ClaimVerifier(AIService(db=None), batch_size=batch_size)
    verdicts, llm_used = await verifier.verify_claims(claims, budget=len(claims))

    records: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    expected_list: list[str] = []
    predicted_list: list[str] = []
    infra_failures: list[str] = []

    for case, verdict in zip(cases, verdicts, strict=True):
        record = {
            "id": case.id,
            "expected": case.expected,
            "predicted": verdict.verdict,
            "correct": verdict.verdict == case.expected,
            "checked_by_llm": verdict.checked_by_llm,
            "explanation": verdict.explanation,
        }
        records.append(record)
        if not verdict.checked_by_llm:
            # LLM failure, not a judgment - excluded from precision/recall
            infra_failures.append(case.id)
            continue
        expected_list.append(case.expected)
        predicted_list.append(verdict.verdict)
        if not record["correct"]:
            mismatches.append(
                {
                    "id": case.id,
                    "expected": case.expected,
                    "predicted": verdict.verdict,
                    "explanation": verdict.explanation,
                }
            )

    if not expected_list:
        print("❌ No scored verdicts (all LLM calls failed) - check API keys.")
        return 1

    matrix = confusion_matrix(expected_list, predicted_list, CLAIM_LABELS, CLAIM_LABELS)
    metrics = per_class_metrics(matrix)
    print_report("Claim faithfulness gold-set eval", matrix, metrics, mismatches)
    print(f"\nLLM budget consumed: {llm_used} claim(s) in {llm_calls} call(s)")
    if infra_failures:
        print(
            f"⚠️  {len(infra_failures)} claim(s) had LLM infrastructure failures "
            f"(excluded from metrics): {', '.join(infra_failures)}"
        )

    report_path = write_json_report(
        kind="claim",
        dataset_path=args.dataset,
        records=records,
        metrics={
            "matrix": matrix,
            **metrics,
            "infra_failures": infra_failures,
            "llm_claims_used": llm_used,
        },
        config_snapshot={
            "batch_size": batch_size,
            "fallback_chain_first": first_provider,
        },
        out_dir=args.report_out,
    )
    print(f"\nJSON report: {report_path}")
    return 0


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
