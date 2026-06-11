"""
Shape tests for the frozen provenance payload contracts.

Each canonical example below is a literal copy of what the emission sites
in background_jobs.py / source_verification_stage.py /
claim_verification_stage.py actually construct. If an emission site gains,
loses or renames a key, the corresponding example here must be updated
together with app/schemas/provenance.py AND the frontend mirror
apps/web/lib/provenance.ts — that forced synchronization is the point.
"""

import pytest
from pydantic import ValidationError

from app.schemas.provenance import (
    PROVENANCE_PAYLOAD_SCHEMAS,
    CitationGatePayload,
    QualityGatePayload,
    VerificationSummaryPayload,
)

# Literal copies of emitted payloads (one canonical example per event type)
CANONICAL_EXAMPLES: dict[str, dict] = {
    "verification_summary": {
        "total": 2,
        "counts": {"verified": 1, "not_found": 1},
        "policy": "mark_only",
        "not_found_titles": ["Imaginary Paper"],
        "sources": [
            {
                "title": "Attention Is All You Need",
                "authors": ["Vaswani"],
                "year": 2017,
                "doi": "10.5555/3295222",
                "status": "verified",
            },
            {
                "title": "Imaginary Paper",
                "authors": [],
                "year": None,
                "doi": None,
                "status": "not_found",
            },
        ],
        "providers": ["crossref"],
    },
    "citation_gate": {
        "passed": False,
        "policy": "strict",
        "counts": {"verified": 1, "not_found": 1},
        "not_found_count": 1,
        "not_found_titles": ["Imaginary Paper"],
    },
    "integrity_gate_failed": {
        "policy": "strict",
        "not_found_count": 1,
        "not_found_titles": ["Imaginary Paper"],
    },
    "integrity_report": {
        "policy": "mark_only",
        "not_found_count": 1,
        "not_found_titles": ["Imaginary Paper"],
    },
    "verification_error": {"error": "Redis connection refused"},
    "claims_verified": {
        "section_index": 1,
        "total": 3,
        "checked": 2,
        "counts": {"supported": 1, "unsupported": 1, "uncertain": 1},
        "unsupported": [
            {
                "sentence": "Transformers eliminate recurrence entirely.",
                "citation": "[Vaswani, 2017]",
                "source_title": "Attention Is All You Need",
                "explanation": "Abstract does not state this claim.",
            }
        ],
    },
    "claim_check_summary": {
        "total_claims": 3,
        "checked": 2,
        "counts": {"supported": 1, "unsupported": 1, "uncertain": 1},
        "budget": 50,
        "budget_exhausted": False,
    },
    "claim_verification_error": {"error": "LLM provider timeout"},
    "rag_retrieved": {
        "section_index": 1,
        "section_title": "Introduction",
        "sources_used": 1,
        "sources": [
            {
                "title": "Attention Is All You Need",
                "doi": "10.5555/3295222",
                "year": 2017,
                "verification_status": "unverified",
            }
        ],
    },
    "section_generated": {
        "section_index": 1,
        "section_title": "Introduction",
        "provider": "openai",
        "model": "gpt-4",
        "word_count": 850,
        "tokens_used": 1200,
        "attempts": 1,
    },
    "humanized": {
        "section_index": 1,
        "ai_score_before": 78.5,
        "ai_score_after": 42.0,
        "multi_pass": False,
        "threshold": 55.0,
    },
    "quality_gate": {
        "section_index": 1,
        "passed": True,
        "gates_enabled": True,
        "grammar_score": 95.0,
        "plagiarism_score": 92.0,
        "ai_detection_score": 42.0,
        "quality_score": 88.0,
    },
    "panel_review": {
        "section_index": 1,
        "overall_score": 81.0,
        "passed": True,
        "critical_override": False,
        "attempts": 1,
        "panel": {"reviewers": []},
    },
    "panel_gate_failed": {
        "section_index": 1,
        "attempts": 2,
        "overall_score": 55.0,
        "critical_override": True,
        "panel": {"reviewers": []},
    },
    "exported": {
        "formats": ["docx"],
        "paths": {"docx": "/api/v1/documents/1/download"},
        "file_size": 24576,
    },
}


def test_registry_is_complete():
    assert set(PROVENANCE_PAYLOAD_SCHEMAS) == set(CANONICAL_EXAMPLES)


@pytest.mark.parametrize("event_type", sorted(CANONICAL_EXAMPLES))
def test_canonical_payload_validates(event_type):
    schema = PROVENANCE_PAYLOAD_SCHEMAS[event_type]
    schema.model_validate(CANONICAL_EXAMPLES[event_type])


def test_verification_summary_empty_variant_has_no_not_found_titles():
    # Emitted when no sources are persisted (source_verification_stage)
    payload = {
        "total": 0,
        "counts": {},
        "policy": "mark_only",
        "sources": [],
        "providers": [],
    }
    parsed = VerificationSummaryPayload.model_validate(payload)
    assert parsed.not_found_titles is None


@pytest.mark.parametrize(
    "payload",
    [
        # no-sources gate (total + counts, no not_found keys)
        {"passed": True, "policy": "mark_only", "total": 0, "counts": {}},
        # all-verified pass (counts only)
        {"passed": True, "policy": "strict", "counts": {"verified": 2}},
        # strict failure (full detail)
        {
            "passed": False,
            "policy": "strict",
            "counts": {"not_found": 1},
            "not_found_count": 1,
            "not_found_titles": ["X"],
        },
        # mark_only continue (full detail, passed)
        {
            "passed": True,
            "policy": "mark_only",
            "counts": {"not_found": 1},
            "not_found_count": 1,
            "not_found_titles": ["X"],
        },
    ],
)
def test_citation_gate_all_four_variants(payload):
    CitationGatePayload.model_validate(payload)


def test_quality_gate_fail_variant():
    # Failure path emits only these three keys
    QualityGatePayload.model_validate(
        {"section_index": 2, "passed": False, "detail": "grammar below threshold"}
    )


def test_extra_key_rejected():
    payload = dict(CANONICAL_EXAMPLES["citation_gate"])
    payload["surprise"] = 1
    with pytest.raises(ValidationError):
        CitationGatePayload.model_validate(payload)


def test_bad_policy_literal_rejected():
    payload = dict(CANONICAL_EXAMPLES["citation_gate"])
    payload["policy"] = "lenient"
    with pytest.raises(ValidationError):
        CitationGatePayload.model_validate(payload)


def test_bad_counts_key_rejected():
    payload = {
        "total": 1,
        "counts": {"hallucinated": 1},
        "policy": "strict",
        "sources": [],
        "providers": [],
    }
    with pytest.raises(ValidationError):
        VerificationSummaryPayload.model_validate(payload)
