"""
Shared infrastructure for the Academic Quality Engine gold-set evals.

Gold datasets (evals/datasets/*.yaml) hold hand-curated cases with known
expected labels. The eval runners (run_citation_eval.py, run_claim_eval.py)
load them, run the real verifiers and report precision/recall per class.

This module is import-safe for CI (no network, no app settings side effects
beyond what importing pydantic/yaml costs); tests/test_gold_datasets.py uses
the same loaders so the schema cannot drift between CI and the runners.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# Expected-label vocabularies. Citation labels use the *document status*
# vocabulary produced by map_verification_status (the layer policy tuning
# cares about). 'failed' (unresolvable / provider outage) is a possible
# *prediction* but never an expectation - outages are not verifier quality.
CITATION_EXPECTED_LABELS = ("verified", "mismatched", "not_found")
CITATION_PREDICTED_LABELS = ("verified", "mismatched", "not_found", "failed")
CLAIM_LABELS = ("supported", "unsupported", "uncertain")


# ----------------------------------------------------------------------
# Dataset schemas
# ----------------------------------------------------------------------


class CitationSource(BaseModel):
    """Mirrors citation_verifier.SourceInput"""

    model_config = ConfigDict(extra="forbid")

    title: str
    authors: list[str] = []
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source title must not be blank")
        return v


class CitationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    expected: Literal["verified", "mismatched", "not_found"]
    group: str
    note: str | None = None
    # Canonical (real) title of the identifier's paper; REQUIRED for
    # mismatched cases so CI can deterministically assert the encoded
    # similarity is below FUZZY_MATCH_THRESHOLD.
    canonical_title: str | None = None
    source: CitationSource

    @model_validator(mode="after")
    def mismatched_needs_identifier_and_canonical(self) -> CitationCase:
        if self.expected == "mismatched":
            if not (self.source.doi or self.source.arxiv_id):
                raise ValueError(
                    f"{self.id}: 'mismatched' is only reachable for DOI/arXiv "
                    "identifier hits - the case must carry doi or arxiv_id"
                )
            if not self.canonical_title:
                raise ValueError(
                    f"{self.id}: 'mismatched' case must carry canonical_title"
                )
        return self


class CitationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    cases: list[CitationCase]

    @field_validator("cases")
    @classmethod
    def unique_ids(cls, v: list[CitationCase]) -> list[CitationCase]:
        seen: set[str] = set()
        for case in v:
            if case.id in seen:
                raise ValueError(f"duplicate case id: {case.id}")
            seen.add(case.id)
        return v


class ClaimCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    expected: Literal["supported", "unsupported", "uncertain"]
    sentence: str
    citation_text: str
    source_title: str
    # Cases sharing a source_key share one synthetic source_id in the runner,
    # exercising the S1..Sn abstract dedup in ClaimVerifier._build_batch_prompt
    source_key: str
    abstract: str
    note: str | None = None

    @field_validator("sentence", "abstract", "source_title", "citation_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be blank")
        return v


class ClaimDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    cases: list[ClaimCase]

    @field_validator("cases")
    @classmethod
    def unique_ids(cls, v: list[ClaimCase]) -> list[ClaimCase]:
        seen: set[str] = set()
        for case in v:
            if case.id in seen:
                raise ValueError(f"duplicate case id: {case.id}")
            seen.add(case.id)
        return v


# ----------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"


def load_citation_dataset(path: str | Path) -> CitationDataset:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return CitationDataset.model_validate(data)


def load_claim_dataset(path: str | Path) -> ClaimDataset:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ClaimDataset.model_validate(data)


def select_cases(cases: list[Any], ids: str | None, limit: int | None) -> list[Any]:
    """Apply --ids / --limit selection shared by both runners"""
    selected = list(cases)
    if ids:
        wanted = {token.strip() for token in ids.split(",") if token.strip()}
        unknown = wanted - {case.id for case in selected}
        if unknown:
            raise SystemExit(f"Unknown case id(s): {', '.join(sorted(unknown))}")
        selected = [case for case in selected if case.id in wanted]
    if limit is not None:
        selected = selected[: max(0, limit)]
    return selected


# ----------------------------------------------------------------------
# Metrics (hand-rolled; expected labels = rows, predicted labels = columns)
# ----------------------------------------------------------------------


def confusion_matrix(
    expected: list[str],
    predicted: list[str],
    expected_labels: tuple[str, ...],
    predicted_labels: tuple[str, ...],
) -> dict[str, dict[str, int]]:
    matrix = {row: dict.fromkeys(predicted_labels, 0) for row in expected_labels}
    for exp, pred in zip(expected, predicted, strict=True):
        matrix[exp][pred] += 1
    return matrix


def per_class_metrics(matrix: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Precision/recall/support per expected class + overall accuracy"""
    classes: dict[str, dict[str, Any]] = {}
    total = sum(sum(row.values()) for row in matrix.values())
    correct = sum(matrix[label].get(label, 0) for label in matrix)

    for label, row in matrix.items():
        true_positive = row.get(label, 0)
        support = sum(row.values())
        predicted_as_label = sum(other.get(label, 0) for other in matrix.values())
        classes[label] = {
            "support": support,
            "precision": (
                round(true_positive / predicted_as_label, 3)
                if predicted_as_label
                else None
            ),
            "recall": round(true_positive / support, 3) if support else None,
        }

    return {
        "classes": classes,
        "accuracy": round(correct / total, 3) if total else None,
        "total": total,
        "correct": correct,
    }


def print_report(
    title: str,
    matrix: dict[str, dict[str, int]],
    metrics: dict[str, Any],
    mismatches: list[dict[str, Any]],
) -> None:
    predicted_labels = list(next(iter(matrix.values())).keys()) if matrix else []
    width = max([10] + [len(label) for label in predicted_labels]) + 2

    print(f"\n=== {title} ===")
    print("\nConfusion matrix (rows = expected, columns = predicted):")
    header = " " * width + "".join(label.rjust(width) for label in predicted_labels)
    print(header)
    for expected_label, row in matrix.items():
        cells = "".join(str(row[label]).rjust(width) for label in predicted_labels)
        print(expected_label.rjust(width) + cells)

    print("\nPer-class metrics:")
    for label, stats in metrics["classes"].items():
        print(
            f"  {label:<12} support={stats['support']:<3} "
            f"precision={stats['precision']} recall={stats['recall']}"
        )
    print(
        f"\nAccuracy: {metrics['accuracy']} "
        f"({metrics['correct']}/{metrics['total']})"
    )

    if mismatches:
        print(f"\nMisclassified cases ({len(mismatches)}):")
        for item in mismatches:
            print(f"  - {json.dumps(item, ensure_ascii=False)}")
    else:
        print("\nAll cases classified correctly.")


# ----------------------------------------------------------------------
# JSON report
# ----------------------------------------------------------------------


def _git_commit() -> str | None:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
            or None
        )
    except Exception:
        return None


def write_json_report(
    kind: str,
    dataset_path: str | Path,
    records: list[dict[str, Any]],
    metrics: dict[str, Any],
    config_snapshot: dict[str, Any],
    out_dir: str | Path = "eval_reports",
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dataset_bytes = Path(dataset_path).read_bytes()
    payload = {
        "kind": kind,
        "timestamp_utc": timestamp,
        "git_commit": _git_commit(),
        "dataset": str(dataset_path),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "config": config_snapshot,
        "metrics": metrics,
        "cases": records,
    }
    report_path = out / f"{kind}_eval_{timestamp}.json"
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report_path
