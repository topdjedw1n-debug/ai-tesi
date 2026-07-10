"""Stable fingerprint for the exact requirements used by one generation run."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _text_sha256(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _timestamp(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def generation_contract_payload(
    document: Any,
    production_case: Any | None,
    run_requirements: str | None,
    uploaded_sources_sha: str | None = None,
) -> dict[str, Any]:
    """Return canonical, non-secret inputs that determine a run's contract.

    Long methodology/intake text is represented by SHA-256 rather than copied
    into logs or release-gate evidence. ``uploaded_sources_sha`` (digest of
    the document's uploaded source PDFs) joins the contract only when
    sources exist, so documents without uploads keep their original hashes.
    """
    case_payload = None
    if production_case is not None:
        case_payload = {
            "id": int(production_case.id),
            "citation_style": str(production_case.citation_style or "apa")
            .strip()
            .lower(),
            "deadline_at": _timestamp(production_case.deadline_at),
            "requirements_sha256": _text_sha256(production_case.requirements_text),
        }

    payload = {
        "version": 1,
        "document_id": int(document.id),
        "title_sha256": _text_sha256(document.title),
        "topic_sha256": _text_sha256(document.topic),
        "language": str(document.language or "").strip().lower(),
        "target_pages": int(document.target_pages or 0),
        "citation_style": str(document.citation_style or "").strip().lower(),
        "ai_provider": str(document.ai_provider or ""),
        "ai_model": str(document.ai_model or ""),
        "requirements_file_processed": bool(document.requirements_file_processed),
        "document_requirements_sha256": _text_sha256(document.additional_requirements),
        "production_case": case_payload,
        "run_requirements_sha256": _text_sha256(run_requirements),
    }
    if uploaded_sources_sha is not None:
        payload["uploaded_sources_sha256"] = str(uploaded_sources_sha)
    return payload


def generation_contract_sha256(
    document: Any,
    production_case: Any | None,
    run_requirements: str | None,
    uploaded_sources_sha: str | None = None,
) -> str:
    payload = generation_contract_payload(
        document, production_case, run_requirements, uploaded_sources_sha
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def generation_contract_error(document: Any) -> str | None:
    """Return why the narrow Italian generation contract is incomplete."""
    if not bool(document.requirements_file_processed):
        return "methodology file was not processed"
    if not str(document.additional_requirements or "").strip():
        return "processed methodology text is missing"
    if str(document.citation_style or "").strip().lower() != "apa":
        return "citation style must be APA"
    return None
