"""The founder's current final-DOCX acceptance policy (not detector settings)."""

from math import isfinite
from typing import Any

from app.services.provenance_service import derive_quality_gate_status

RELEASE_POLICY_VERSION = "agency-docx-2026-09-04"
DETECTOR_THRESHOLD_PERCENT = 10.0
DETECTOR_NAME = "Compilatio"
REPORT_EVENT = "compilatio_report_attached"
REVIEW_EVENT = "content_reviewed"
MAX_REPORT_BYTES = 20 * 1024 * 1024


def section_release_status(payload: dict[str, Any]) -> str:
    """Compilatio has separate exact-DOCX gates; section detectors are diagnostic.

    Keep their raw ledger results intact. Grammar and any other section checks
    still block; old events without a breakdown retain conservative semantics.
    """
    checks = payload.get("checks")
    if not isinstance(checks, dict) or not checks:
        return derive_quality_gate_status(payload)
    if payload.get("gates_enabled") is False or "grammar" not in checks:
        return "unchecked"
    if payload.get("status") == "failed" and not any(
        isinstance(checks.get(name), dict) and checks[name].get("status") == "failed"
        for name in ("plagiarism", "ai_detection")
    ):
        # A failure not explained by a diagnostic check must remain blocking.
        return "failed"
    statuses = [
        check.get("status") if isinstance(check, dict) else None
        for name, check in checks.items()
        if name not in {"plagiarism", "ai_detection"}
    ]
    if "failed" in statuses:
        return "failed"
    return "passed" if all(status == "passed" for status in statuses) else "unchecked"


def detector_verdict(evidence: dict[str, Any]) -> tuple[str, str]:
    """Re-evaluate stored evidence; a historic/manual PASS has no authority."""
    result = evidence.get("result_percent")
    if (
        evidence.get("policy_version") != RELEASE_POLICY_VERSION
        or str(evidence.get("detector_name", "")).strip().casefold()
        != DETECTOR_NAME.casefold()
        or evidence.get("artifact_format") != "docx"
        or evidence.get("report_matches_artifact") is not True
        or evidence.get("decision") not in {"passed", "failed"}
        or isinstance(result, bool)
        or not isinstance(result, int | float)
        or not isfinite(result)
        or not 0 <= result <= 100
    ):
        return "no_data", "Потрібні повні результати Compilatio за чинними правилами."
    if result > DETECTOR_THRESHOLD_PERCENT:
        return "failed", f"Compilatio: {result}%. Допустимо не більше 10%."
    if evidence["decision"] == "failed":
        return "failed", "Менеджер відхилив результат перевірки."
    return "passed", f"Compilatio: {result}%. Поріг 10% пройдено."
