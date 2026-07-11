"""Universal task contract: every rule has a value, a source, and a flag.

Course decision 2026-07-11 (owner-ratified): the centre of the product is
the requirements contract, not the methodology file. The mandatory core is
topic / work type / language / volume; methodology, uploaded PDFs and
wishes are optional enrichers. Each derived rule records WHERE it came
from ("intake", "methodology", "system_default") and whether it is
explicit, assumed, or manager-confirmed. Works without a methodology run
on a neutral academic structure — but only after the manager has seen and
confirmed the assumptions, and the delivered evidence honestly says
"standard academic rules", never "university requirements".
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# The four styles the citation formatter actually renders. The narrow
# Italian pilot clamped everything to APA; the clamp is now a per-document
# contract value, not a global system requirement.
SUPPORTED_CITATION_STYLES = frozenset({"apa", "mla", "chicago", "harvard"})

# Neutral academic structures by work type — the default when no
# methodology exists. UNIBO's guidance is a saved TEMPLATE, not the system
# standard (GPT correction 2026-07-11, confirmed by owner).
WORK_TYPE_STRUCTURES: dict[str, str] = {
    "tesi_triennale": (
        "introduction; 2-3 numbered chapters including a literature review; "
        "conclusions; bibliography"
    ),
    "tesi_magistrale": (
        "introduction with research question; numbered chapters and "
        "sub-paragraphs including a literature review; discussion; "
        "conclusions; bibliography and sitography"
    ),
    "diploma": (
        "introduction; numbered chapters including a literature review; "
        "conclusions; bibliography"
    ),
    "essay": "introduction; argument development; conclusions; references",
    "report": "introduction; methods; findings; discussion; references",
}
DEFAULT_WORK_TYPE = "tesi_magistrale"


def _rule(
    key: str, value: Any, source: str, status: str, note: str | None = None
) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "key": key,
        "value": value,
        "source": source,  # intake | methodology | system_default
        "status": status,  # explicit | assumed | confirmed
    }
    if note:
        rule["note"] = note
    return rule


def build_task_contract(
    document: Any,
    *,
    uploaded_files: list[Any] | None = None,
) -> dict[str, Any]:
    """Assemble the contract from a Document (+ optional uploaded sources).

    Pure and synchronous on purpose: the worker's trust-boundary check and
    the release gate must be able to recompute it without extra IO beyond
    what they already load.
    """
    methodology_present = bool(document.requirements_file_processed) and bool(
        str(document.additional_requirements or "").strip()
    )
    work_type = str(document.work_type or "").strip().lower() or None
    citation_style = str(document.citation_style or "").strip().lower() or "apa"

    rules: list[dict[str, Any]] = [
        _rule("topic", str(document.topic or ""), "intake", "explicit"),
        _rule("language", str(document.language or "en"), "intake", "explicit"),
        _rule("target_pages", int(document.target_pages or 0), "intake", "explicit"),
        _rule("citation_style", citation_style, "intake", "explicit"),
    ]

    if work_type:
        rules.append(_rule("work_type", work_type, "intake", "explicit"))
    else:
        work_type = DEFAULT_WORK_TYPE
        rules.append(
            _rule(
                "work_type",
                work_type,
                "system_default",
                "assumed",
                note="work type was not specified; assumed a master's thesis",
            )
        )

    if methodology_present:
        rules.append(
            _rule(
                "structure",
                "university_methodology",
                "methodology",
                "explicit",
                note="structure and formatting follow the uploaded methodology",
            )
        )
        basis = "university_methodology"
    else:
        structure = WORK_TYPE_STRUCTURES.get(
            work_type, WORK_TYPE_STRUCTURES[DEFAULT_WORK_TYPE]
        )
        rules.append(
            _rule(
                "structure",
                structure,
                "system_default",
                "assumed",
                note="no methodology uploaded; neutral academic structure "
                "for the work type",
            )
        )
        basis = "standard_academic"

    uploaded_files = uploaded_files or []
    mandatory_keys = [
        str(f.citation_key) for f in uploaded_files if getattr(f, "mandatory", False)
    ]
    supplementary_keys = [
        str(f.citation_key)
        for f in uploaded_files
        if not getattr(f, "mandatory", False)
    ]
    if uploaded_files:
        rules.append(
            _rule(
                "sources_policy",
                {
                    "mode": "uploaded_plus_auto",
                    "mandatory_files": mandatory_keys,
                    "supplementary_files": supplementary_keys,
                },
                "intake",
                "explicit",
                note="uploaded PDFs are used together with automatically "
                "found academic sources; mandatory ones gate generation",
            )
        )
    else:
        rules.append(
            _rule(
                "sources_policy",
                {"mode": "auto"},
                "system_default",
                "explicit",
                note="academic sources are retrieved automatically",
            )
        )

    assumptions = [r for r in rules if r["status"] == "assumed"]
    # Honesty rule: without a methodology the evidence may never claim
    # "meets university requirements".
    basis_label = (
        "university methodology"
        if basis == "university_methodology"
        else "standard academic rules with manager-confirmed parameters"
    )
    return {
        "version": 1,
        "document_id": int(document.id),
        "basis": basis,
        "basis_label": basis_label,
        "rules": rules,
        "assumptions": assumptions,
        "confirmation_required": basis == "standard_academic",
        "sha256": task_contract_sha256(document),
    }


def task_contract_sha256(document: Any) -> str:
    """Fingerprint of the contract-relevant document inputs.

    Confirmation binds to this sha: uploading a methodology, editing the
    intake or changing sources shifts it, so a stale confirmation never
    lets a changed task through.
    """
    payload = {
        "version": 1,
        "topic": str(document.topic or ""),
        "language": str(document.language or "en").strip().lower(),
        "target_pages": int(document.target_pages or 0),
        "citation_style": str(document.citation_style or "").strip().lower(),
        "work_type": str(document.work_type or "").strip().lower(),
        "methodology_present": bool(document.requirements_file_processed)
        and bool(str(document.additional_requirements or "").strip()),
        "requirements_sha256": hashlib.sha256(
            str(document.additional_requirements or "").encode("utf-8")
        ).hexdigest(),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contract_confirmation_error(document: Any) -> str | None:
    """Why generation must not start yet, or None.

    Explicit basis (methodology) needs no confirmation. An assumed basis
    (standard academic structure) requires the manager to have confirmed
    the CURRENT contract fingerprint.
    """
    methodology_present = bool(document.requirements_file_processed) and bool(
        str(document.additional_requirements or "").strip()
    )
    if methodology_present:
        return None
    confirmed = str(document.contract_confirmed_sha256 or "")
    if not confirmed:
        return (
            "no methodology uploaded: the manager must review and confirm "
            "the assumed task contract (standard academic structure) first"
        )
    if confirmed != task_contract_sha256(document):
        return (
            "the task inputs changed after the contract was confirmed: "
            "review and confirm the updated assumptions"
        )
    return None


def structure_directive(document: Any) -> str | None:
    """Outline/section guidance for works WITHOUT a methodology."""
    methodology_present = bool(document.requirements_file_processed) and bool(
        str(document.additional_requirements or "").strip()
    )
    if methodology_present:
        return None
    work_type = str(document.work_type or "").strip().lower() or DEFAULT_WORK_TYPE
    structure = WORK_TYPE_STRUCTURES.get(
        work_type, WORK_TYPE_STRUCTURES[DEFAULT_WORK_TYPE]
    )
    return (
        f"[Task contract] No university methodology was provided. Use the "
        f"standard academic structure for a {work_type.replace('_', ' ')}: "
        f"{structure}."
    )
