"""Explicit same-job recovery and durable receipts for all handled intents."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import settings
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    DocumentSection,
    ProductionCase,
)
from app.services.academic_context import digest
from app.services.academic_review import review_binding
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_outcomes import MANUAL_REASONS, outcome_fields
from app.services.generation_pause import require_generation_open
from app.services.generation_profile import generation_profile_sha256
from app.services.generation_worker import utc_now
from app.services.source_evidence import evidence_text
from app.services.source_verification_stage import load_source_pack
from app.services.uploaded_sources import (
    build_uploaded_source_pack,
    uploaded_sources_digest,
)


def terminal_fingerprint(job: Any) -> str:
    return digest(
        {
            "id": job.id,
            "status": job.status,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "completed_at": str(job.completed_at),
            "error": job.error_message,
            "payload": job.request_payload,
            "source_pack": job.source_pack_sha256,
        }
    )


def orphan_result_state(document: Any) -> dict[str, Any]:
    return {
        "reason_code": "legacy_unknown",
        "allowed_actions": ["new_version"],
        "expected_fingerprint": digest(
            {
                "document_id": document.id,
                "status": document.status,
                "outline": document.outline,
                "content": document.content,
                "docx_sha256": document.docx_sha256,
                "pdf_sha256": document.pdf_sha256,
            }
        ),
    }


async def latest_job_for_update(db: Any, document_id: int) -> Any:
    return (
        await db.execute(
            select(AIGenerationJob)
            .where(
                AIGenerationJob.document_id == document_id,
                AIGenerationJob.job_type == "full_document",
            )
            .order_by(AIGenerationJob.id.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def intent_receipt(
    db: Any, document_id: int, actor_id: int, intent_id: str | None
) -> dict[str, Any] | None:
    if not intent_id:
        return None
    # The User -> Job -> Document locks serialize inserts; provenance stays append-only.
    events = (
        await db.execute(
            select(DocumentProvenance)
            .where(
                DocumentProvenance.document_id == document_id,
                DocumentProvenance.event_type == "generation_intent_receipt",
            )
            .order_by(DocumentProvenance.id.desc())
        )
    ).scalars()
    return next(
        (
            e.payload
            for e in events
            if (e.payload or {}).get("intent_id") == intent_id
            and (e.payload or {}).get("actor_id") == actor_id
        ),
        None,
    )


def record_intent(
    db: Any,
    document_id: int,
    actor_id: int,
    intent_id: str | None,
    job_id: int,
    action: str,
    expected: str | None,
    *,
    granted: bool = False,
) -> None:
    if intent_id:
        db.add(
            DocumentProvenance(
                document_id=document_id,
                stage="generation",
                event_type="generation_intent_receipt",
                payload={
                    "actor_id": actor_id,
                    "intent_id": intent_id,
                    "job_id": job_id,
                    "action": action,
                    "expected_fingerprint": expected,
                    "granted": granted,
                },
            )
        )


async def recovery_state(
    db: Any, document: Any, job: Any, case: Any = None
) -> dict[str, Any]:
    payload = job.request_payload or {}
    result = dict(payload.get("last_outcome") or {})
    reason = result.get("reason_code") or (
        "cancelled_by_user" if job.status == "cancelled" else "legacy_unknown"
    )
    if job.status in {"queued", "running"}:
        return {
            **result,
            "allowed_actions": [],
            "expected_fingerprint": terminal_fingerprint(job),
        }
    if job.status == "completed":
        # Only the outcome written at completion describes a finished job; a
        # failure that preceded a resume/retry is history in provenance. An
        # actual failed whole-work review is kept as academic_content_rejected.
        current = result if result.get("outcome") == "completed" else {}
        return {
            **current,
            "reason_code": current.get("reason_code"),
            "allowed_actions": ["new_version"],
            "expected_fingerprint": terminal_fingerprint(job),
        }
    if not payload.get("profile_sha256"):
        reason = "legacy_unknown"
    elif payload["profile_sha256"] != generation_profile_sha256(document, job.user_id):
        reason = "contract_or_profile_mismatch"
    elif payload.get("generation_contract_sha256") != generation_contract_sha256(
        document,
        case,
        payload.get("additional_requirements"),
        await uploaded_sources_digest(db, int(document.id)),
    ):
        reason = "contract_or_profile_mismatch"
    if reason in MANUAL_REASONS:
        sections = list(
            (
                await db.execute(
                    select(DocumentSection)
                    .where(
                        DocumentSection.document_id == document.id,
                        DocumentSection.status == "completed",
                    )
                    .order_by(DocumentSection.section_index)
                )
            ).scalars()
        )
        pack = await load_source_pack(db, int(document.id))
        if pack:
            uploaded = await build_uploaded_source_pack(
                db, int(document.id), str(document.topic)
            )
            pack.passages = uploaded.passages if uploaded else None
        events = list(
            (
                await db.execute(
                    select(DocumentProvenance)
                    .where(
                        DocumentProvenance.document_id == document.id,
                        DocumentProvenance.event_type.in_(
                            ["academic_outline_review", "source_pack_preflight"]
                        ),
                    )
                    .order_by(DocumentProvenance.id)
                )
            ).scalars()
        )
        if job.source_pack_sha256 and (
            not pack
            or any(not evidence_text(p.source) for p in pack.sources)
            or not any(
                e.event_type == "source_pack_preflight"
                and (e.payload or {}).get("sha256") == job.source_pack_sha256
                and (e.payload or {}).get("retrieval_trace")
                for e in events
            )
        ):
            reason = "checkpoint_integrity_error"
        if sections and not any(
            e.event_type == "academic_outline_review"
            and (e.payload or {}).get("status") == "passed"
            and (e.payload or {}).get("binding")
            == review_binding(document, job, job.source_pack_sha256, kind="outline")
            for e in events
        ):
            reason = "checkpoint_integrity_error"

        if (
            job.source_pack_sha256
            and (not pack or pack.sha256() != job.source_pack_sha256)
        ) or (sections and not job.source_pack_sha256):
            reason = "checkpoint_integrity_error"
        elif sections and pack is not None:
            outline = document.outline or {}
            for section in sections:
                index = int(section.section_index) - 1
                planned = outline.get("sections") or []
                if (
                    index < 0
                    or index >= len(planned)
                    or section.title != planned[index].get("title")
                    or not section.content
                ):
                    reason = "checkpoint_integrity_error"
                    break
                if not set(section.pack_keys_used or []).issubset(set(pack.keys())):
                    reason = "checkpoint_integrity_error"
                    break
    action = (
        "resume"
        if reason in MANUAL_REASONS and job.status in {"failed", "cancelled"}
        else "new_version"
    )
    return {
        **result,
        "reason_code": reason,
        "allowed_actions": [action]
        if job.status in {"failed", "cancelled", "completed"}
        else [],
        "expected_fingerprint": terminal_fingerprint(job),
    }


async def resume_generation(db: Any, document_id: int, actor: Any, request: Any) -> Any:
    from app.api.v1.endpoints.generate import _enforce_generation_gate

    await require_generation_open(db)
    owner = (
        await db.execute(
            select(User)
            .where(User.id == int(actor.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if owner is None or not owner.is_active or owner.deletion_requested_at is not None:
        raise HTTPException(409, "Обліковий запис недоступний для генерації.")
    # Ownership is checked before acquiring a foreign job lock.
    owned = (
        await db.execute(
            select(Document.id).where(
                Document.id == document_id, Document.user_id == actor.id
            )
        )
    ).scalar_one_or_none()
    if owned is None:
        raise HTTPException(404, "Роботу не знайдено.")
    job = await latest_job_for_update(db, document_id)
    document = (
        await db.execute(
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    case = (
        await db.execute(
            select(ProductionCase)
            .where(ProductionCase.document_id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(409, "Немає збереженої задачі для продовження.")
    receipt = await intent_receipt(db, document_id, int(actor.id), request.intent_id)
    if receipt:
        if (
            receipt["action"] != "resume"
            or receipt["expected_fingerprint"] != request.expected_fingerprint
        ):
            raise HTTPException(409, {"reason_code": "intent_conflict"})
        result = await db.get(AIGenerationJob, receipt["job_id"])
        await db.commit()
        return result
    if job.status in {"queued", "running"}:
        record_intent(
            db,
            document_id,
            int(actor.id),
            request.intent_id,
            int(job.id),
            "resume",
            request.expected_fingerprint,
        )
        await db.commit()
        return job
    state = await recovery_state(db, document, job, case)
    if request.expected_fingerprint != state["expected_fingerprint"]:
        raise HTTPException(409, {"reason_code": "terminal_state_changed", **state})
    if "resume" not in state["allowed_actions"]:
        raise HTTPException(409, state)
    if not request.confirm_paid or (
        state["reason_code"] == "provider_access_required"
        and not request.confirm_access_restored
    ):
        raise HTTPException(409, {"reason_code": "confirmation_required"})
    await _enforce_generation_gate(db, document, int(actor.id))
    # The claim budget is spent only while sections are still being written.
    # When every planned section is already saved (review/export-only
    # recovery), an exhausted budget cannot block reuse of the saved text.
    planned_sections = len((document.outline or {}).get("sections") or [])
    completed_sections = (
        await db.execute(
            select(func.count())
            .select_from(DocumentSection)
            .where(
                DocumentSection.document_id == document.id,
                DocumentSection.status == "completed",
            )
        )
    ).scalar_one()
    writing_remaining = planned_sections == 0 or completed_sections < planned_sections
    if (
        writing_remaining
        and actor.id not in settings.UNLIMITED_GENERATION_USER_IDS
        and int(job.claim_checks_used or 0) >= settings.CLAIM_VERIFICATION_MAX_CHECKS
    ):
        raise HTTPException(409, {"reason_code": "claim_budget_exhausted"})
    payload = job.request_payload or {}
    old = {
        "status": job.status,
        "error_message": job.error_message,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "total_tokens": job.total_tokens,
        "cost_cents": job.cost_cents,
        "claim_checks_used": job.claim_checks_used,
        "source_pack_sha256": job.source_pack_sha256,
        "profile_sha256": payload.get("profile_sha256"),
        # Full detail of the stop this resume answers stays in history.
        "last_outcome": payload.get("last_outcome"),
    }
    job.max_attempts = (
        int(job.attempt_count or 0) + settings.GENERATION_JOB_MAX_ATTEMPTS
    )
    db.add(
        DocumentProvenance(
            document_id=document_id,
            stage="generation",
            event_type="generation_resume",
            payload={
                "job_id": job.id,
                "actor_id": actor.id,
                "intent_id": request.intent_id,
                "expected_fingerprint": request.expected_fingerprint,
                "previous": old,
                "max_attempts": job.max_attempts,
                "reason_code": state["reason_code"],
            },
        )
    )
    record_intent(
        db,
        document_id,
        int(actor.id),
        request.intent_id,
        int(job.id),
        "resume",
        request.expected_fingerprint,
        granted=True,
    )
    # The current view is a resumed job with no present failure; the answered
    # stop is referenced, not repeated as if it were still in force.
    job.request_payload = {
        **payload,
        "last_outcome": {
            **outcome_fields(
                "resume",
                None,
                {"job_id": job.id, "attempt_count": job.attempt_count},
                request.intent_id,
            ),
            "outcome": "resumed",
            "previous_reason_code": state["reason_code"],
        },
    }
    job.status = "queued"
    job.completed_at = None
    job.success = None
    job.available_at = utc_now()
    job.lease_owner = job.lease_token = job.lease_expires_at = None
    document.status = "generating"
    if case:
        case.generation_status = "generating"
        case.release_status = "blocked"
        case.delivery_status = "not_ready"
    await db.commit()
    return job
