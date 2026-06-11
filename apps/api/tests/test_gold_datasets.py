"""
CI schema guard for the AQE gold-set datasets (no network, no cost).

Uses the same loaders as the eval runners (evals.common), so schema drift
between CI and the runners is impossible. The mismatched-similarity guard
deterministically reproduces the verifier's fuzzy-matching arithmetic.
"""

from collections import Counter
from difflib import SequenceMatcher

from app.services.citation_verifier import FUZZY_MATCH_THRESHOLD, normalize_title
from evals.common import DATASETS_DIR, load_citation_dataset, load_claim_dataset

CITATIONS_PATH = DATASETS_DIR / "citations_gold.yaml"
CLAIMS_PATH = DATASETS_DIR / "claims_gold.yaml"


def test_citation_dataset_schema_and_composition():
    dataset = load_citation_dataset(CITATIONS_PATH)
    assert dataset.version == 1

    counts = Counter(case.expected for case in dataset.cases)
    # Minimum per-class support so metrics stay meaningful
    assert counts["verified"] >= 5
    assert counts["mismatched"] >= 5
    assert counts["not_found"] >= 5

    # Identifier coverage: at least one arXiv-only and one fabricated-DOI case
    assert any(case.source.arxiv_id and not case.source.doi for case in dataset.cases)
    assert any(
        case.expected == "not_found" and case.source.doi for case in dataset.cases
    )


def test_mismatched_cases_are_below_fuzzy_threshold():
    """A curated 'mismatched' title must actually score below the verifier's
    threshold against the canonical title - otherwise the verifier would
    legitimately report it as verified and the gold label would be wrong."""
    dataset = load_citation_dataset(CITATIONS_PATH)
    for case in dataset.cases:
        if case.expected != "mismatched":
            continue
        ratio = SequenceMatcher(
            None,
            normalize_title(case.source.title),
            normalize_title(case.canonical_title),
        ).ratio()
        assert ratio < FUZZY_MATCH_THRESHOLD, (
            f"{case.id}: encoded title is too similar to the canonical title "
            f"(ratio={ratio:.3f} >= {FUZZY_MATCH_THRESHOLD}) - the verifier "
            "would correctly report 'verified', not 'mismatched'"
        )


def test_corrupted_minor_cases_normalize_to_exact_match():
    """corrupted_minor entries carry only cosmetic noise that normalize_title
    must erase completely - they probe the false-positive direction."""
    dataset = load_citation_dataset(CITATIONS_PATH)
    minor_cases = [c for c in dataset.cases if c.group == "corrupted_minor"]
    assert minor_cases, "dataset must include corrupted_minor probes"
    for case in minor_cases:
        assert case.expected == "verified"


def test_claim_dataset_schema_and_composition():
    dataset = load_claim_dataset(CLAIMS_PATH)
    assert dataset.version == 1

    counts = Counter(case.expected for case in dataset.cases)
    assert counts["supported"] >= 5
    assert counts["unsupported"] >= 5
    assert counts["uncertain"] >= 3

    # At least one source_key must be shared so a batch exercises the
    # S1..Sn abstract dedup in ClaimVerifier._build_batch_prompt
    key_counts = Counter(case.source_key for case in dataset.cases)
    assert max(key_counts.values()) > 1

    # Cases sharing a source_key must share the same abstract text,
    # otherwise the synthetic shared source_id would be a lie
    abstracts_by_key: dict[str, str] = {}
    for case in dataset.cases:
        seen = abstracts_by_key.setdefault(case.source_key, case.abstract)
        assert seen == case.abstract, (
            f"{case.id}: abstract differs from other cases with "
            f"source_key={case.source_key}"
        )
