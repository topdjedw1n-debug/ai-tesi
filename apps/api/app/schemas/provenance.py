"""
Frozen payload contracts for document_provenance events.

Source of truth for the payload shapes returned by
GET /api/v1/documents/{id}/provenance. The frontend reads these keys
directly — see apps/web/lib/provenance.ts and
apps/web/components/admin/documents/ProvenanceTimeline.tsx, which are
hand-maintained mirrors of this module (update them together).

Enforcement strategy (deliberate): these models are validated against
real emitted payloads in tests only (tests/test_provenance_schemas.py and
the frozen-contract tests in tests/test_citation_pipeline_integration.py).
Emission sites in app/services/background_jobs.py,
source_verification_stage.py and claim_verification_stage.py are
intentionally NOT routed through these models at runtime: several event types
are written inside existing generation transactions, which a validation layer
must not disturb.

Migration path (post-stabilization): first unify the direct db.add()
provenance writes through provenance_service.record_event, then construct
payloads via these models' model_dump() at emission sites.

No schema_version field: both frontend consumers tolerate additive keys,
and adding the field now would itself change emitted payloads. Introduce
it as an additive key the moment a breaking change is actually needed.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SourceStatus = Literal["verified", "mismatched", "not_found", "failed"]
Policy = Literal["strict", "mark_only"]
ClaimVerdictName = Literal["supported", "unsupported", "uncertain"]
# "unchecked" = the check did not run (provider disabled/unconfigured or
# threw). It is non-blocking for generation but must never read as passed.
CheckStatusName = Literal["passed", "failed", "unchecked"]
# "warning" = mark_only policy let the pipeline continue despite not_found
# sources; release gates surface it instead of a plain pass.
CitationGateStatus = Literal["passed", "failed", "warning", "unchecked"]


class _FrozenPayload(BaseModel):
    """Drift in either direction (renamed or extra keys) must fail tests."""

    model_config = ConfigDict(extra="forbid")


class VerifiedSourceRecord(_FrozenPayload):
    """verification_summary.sources[] item."""

    title: str
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    status: SourceStatus


class RetrievedSourceRecord(_FrozenPayload):
    """rag_retrieved.sources[] item — different shape than VerifiedSourceRecord."""

    title: str
    doi: str | None = None
    year: int | None = None
    verification_status: Literal["unverified"]


class VerificationSummaryPayload(_FrozenPayload):
    total: int
    counts: dict[SourceStatus, int]
    policy: Policy
    sources: list[VerifiedSourceRecord]
    providers: list[str]
    # Absent in the no-sources variant; present (possibly empty) otherwise
    not_found_titles: list[str] | None = None


class CitationGatePayload(_FrozenPayload):
    """Four emission variants share this shape (optional keys differ)."""

    passed: bool
    policy: Policy
    # Optional for legacy events; new emissions always set it. mark_only
    # with not_found sources emits passed=True + status="warning".
    status: CitationGateStatus | None = None
    counts: dict[SourceStatus, int] | None = None
    total: int | None = None
    not_found_count: int | None = None
    not_found_titles: list[str] | None = None
    mismatched_count: int | None = None
    mismatched_titles: list[str] | None = None


class CitationClosurePayload(_FrozenPayload):
    """Proof that every citation marker used in the text was verified."""

    passed: bool
    used_keys: list[str]
    verified_keys: list[str]
    missing_keys: list[str]
    unverified_keys: list[str]
    used_total: int
    verified_total: int


class IntegrityReportPayload(_FrozenPayload):
    """Shared by integrity_gate_failed (strict) and integrity_report (mark_only)."""

    policy: Policy
    not_found_count: int
    not_found_titles: list[str]
    mismatched_count: int | None = None
    mismatched_titles: list[str] | None = None


class ErrorPayload(_FrozenPayload):
    """Shared by verification_error and claim_verification_error."""

    error: str


class UnsupportedClaim(_FrozenPayload):
    sentence: str
    citation: str
    source_title: str | None = None
    explanation: str


class ClaimsVerifiedPayload(_FrozenPayload):
    section_index: int
    total: int
    checked: int
    counts: dict[ClaimVerdictName, int]
    unsupported: list[UnsupportedClaim]
    uncertain: list[UnsupportedClaim]


class ClaimCheckSummaryPayload(_FrozenPayload):
    total_claims: int
    checked: int
    counts: dict[ClaimVerdictName, int]
    budget: int
    budget_exhausted: bool
    reserved_checks: int
    incomplete: int = 0


class RagRetrievedPayload(_FrozenPayload):
    section_index: int
    section_title: str
    sources_used: int
    sources: list[RetrievedSourceRecord]


class SectionGeneratedPayload(_FrozenPayload):
    section_index: int
    section_title: str
    provider: str | None = None
    model: str | None = None
    word_count: int
    tokens_used: int
    attempts: int


class HumanizedPayload(_FrozenPayload):
    section_index: int
    ai_score_before: float | None = None
    ai_score_after: float | None = None
    multi_pass: bool
    threshold: float


class QualityCheckEvidence(_FrozenPayload):
    """Per-check breakdown inside quality_gate.checks."""

    status: CheckStatusName
    score: float | None = None
    reason: str | None = None
    # Only populated for ai_detection
    provider: str | None = None


class QualityGatePayload(_FrozenPayload):
    """Pass variant carries scores; fail variant only {section_index, passed, detail}."""

    section_index: int
    passed: bool
    # Optional for legacy events; new emissions always set both. Readers
    # must derive a status for legacy payloads (null score => unchecked,
    # gates_enabled=False => unchecked) instead of trusting passed=True.
    status: CheckStatusName | None = None
    checks: (
        dict[Literal["grammar", "plagiarism", "ai_detection"], QualityCheckEvidence]
        | None
    ) = None
    gates_enabled: bool | None = None
    grammar_score: float | None = None
    plagiarism_score: float | None = None
    ai_detection_score: float | None = None
    quality_score: float | None = None
    detail: str | None = None


class PanelReviewPayload(_FrozenPayload):
    section_index: int
    overall_score: float | None = None
    passed: bool | None = None
    critical_override: bool
    attempts: int
    # QualityValidator pass-through report; intentionally not over-specified
    panel: dict[str, Any] | None = None


class PanelGateFailedPayload(_FrozenPayload):
    section_index: int
    attempts: int
    overall_score: float | None = None
    critical_override: bool
    panel: dict[str, Any] | None = None


class ExportedPayload(_FrozenPayload):
    formats: list[str]
    paths: dict[str, str | None]
    file_size: int | None = None


PROVENANCE_PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "verification_summary": VerificationSummaryPayload,
    "citation_gate": CitationGatePayload,
    "citation_closure": CitationClosurePayload,
    "integrity_gate_failed": IntegrityReportPayload,
    "integrity_report": IntegrityReportPayload,
    "verification_error": ErrorPayload,
    "claims_verified": ClaimsVerifiedPayload,
    "claim_check_summary": ClaimCheckSummaryPayload,
    "claim_verification_error": ErrorPayload,
    "rag_retrieved": RagRetrievedPayload,
    "section_generated": SectionGeneratedPayload,
    "humanized": HumanizedPayload,
    "quality_gate": QualityGatePayload,
    "panel_review": PanelReviewPayload,
    "panel_gate_failed": PanelGateFailedPayload,
    "exported": ExportedPayload,
}
