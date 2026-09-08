"""Explicit, idempotent retry of an unchecked review of an unchanged DOCX."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.config import settings
from app.models.document import AIGenerationJob, DocumentProvenance
from app.services.academic_review import (
    REVIEW_MAX_CHARS,
    review_binding,
    review_prompt,
    validate_review,
)
from app.services.ai_service import AIService
from app.services.cost_estimator import UsageTracker
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_profile import generation_profile_sha256
from app.services.source_evidence import evidence_text
from app.services.source_verification_stage import load_source_pack
from app.services.storage_service import StorageService
from app.services.uploaded_sources import (
    build_uploaded_source_pack,
    uploaded_sources_digest,
)

RETRY_STARTED = "academic_review_retry_started"
RETRY_EXPIRY_SECONDS = 120


def retry_pending(event: Any) -> bool:
    created = event.created_at
    if created is None:
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return bool((datetime.now(UTC) - created).total_seconds() < RETRY_EXPIRY_SECONDS)


async def _snapshot(
    db: Any, case_id: int
) -> tuple[Any, Any, Any, list[Any], dict[str, Any]]:
    # Local import avoids the release-service/review-service cycle.
    from app.services.production_case_service import ProductionCaseService

    case, doc = await ProductionCaseService(db).get_case_and_document_for_update(
        case_id
    )
    job = (
        await db.execute(
            select(AIGenerationJob)
            .where(
                AIGenerationJob.document_id == doc.id,
                AIGenerationJob.job_type == "full_document",
                AIGenerationJob.status == "completed",
            )
            .order_by(AIGenerationJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if (
        doc.status != "completed"
        or job is None
        or not doc.docx_sha256
        or not doc.docx_path
    ):
        raise HTTPException(409, "Потрібна завершена робота зі збереженим DOCX.")
    active = (
        await db.execute(
            select(AIGenerationJob.id).where(
                AIGenerationJob.document_id == doc.id,
                AIGenerationJob.status.in_(
                    ["queued", "running", "pending", "retrying"]
                ),
            )
        )
    ).first()
    if active:
        raise HTTPException(409, "Для цієї роботи вже триває генерація.")
    payload = job.request_payload or {}
    if generation_contract_sha256(
        doc,
        case,
        payload.get("additional_requirements"),
        await uploaded_sources_digest(db, int(doc.id)),
    ) != payload.get("generation_contract_sha256"):
        raise HTTPException(409, "Завдання змінилося після генерації.")
    pack = await load_source_pack(db, int(doc.id))
    if pack:
        uploaded = await build_uploaded_source_pack(db, int(doc.id), str(doc.topic))
        pack.passages = uploaded.passages if uploaded else None
    if (
        not pack
        or pack.sha256() != job.source_pack_sha256
        or any(not evidence_text(p.source) for p in pack.sources)
    ):
        raise HTTPException(409, "Докази джерел змінилися або відсутні.")
    events = list(
        (
            await db.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.document_id == doc.id)
                .order_by(DocumentProvenance.id.asc())
            )
        )
        .scalars()
        .all()
    )
    return doc, job, pack, events, review_binding(doc, job, pack.sha256(), kind="whole")


async def retry_academic_review(
    db: Any, case_id: int, attempt_id: str, actor_id: int, *, ai_service: Any = None
) -> dict[str, Any]:
    """No row lock during the model call; a fresh fenced snapshot owns publish.

    The committed request ID makes browser resubmission free. A different
    request ID is a new explicit manager action, permitted only for unchecked
    results. It never regenerates, re-exports or rewrites content.
    """
    from app.services.generation_pause import require_generation_open

    await require_generation_open(db)
    doc, job, pack, events, binding = await _snapshot(db, case_id)
    same_attempt = [
        e for e in events if (e.payload or {}).get("attempt_id") == attempt_id
    ]
    if same_attempt:
        # Replays must also remain bound to the current work.
        if any((e.payload or {}).get("binding") != binding for e in same_attempt):
            raise HTTPException(409, "Цей запит стосується іншої версії роботи.")
        result = next(
            (
                e.payload
                for e in reversed(same_attempt)
                if e.event_type != RETRY_STARTED
            ),
            None,
        )
        pending = retry_pending(same_attempt[-1]) if result is None else False
        await db.rollback()
        return (
            dict(result)
            if result
            else {
                "status": "pending" if pending else "unchecked",
                "reason": "Перевірка ще триває або була перервана. Новий платний виклик не запускався.",
                "attempt_id": attempt_id,
            }
        )
    # A new paid review is bound to the job's recorded profile. A changed or
    # missing generator/reviewer profile needs an explicit decision first;
    # replays above stay free and unaffected.
    if (job.request_payload or {}).get("profile_sha256") != generation_profile_sha256(
        doc, job.user_id
    ):
        raise HTTPException(
            409,
            "Версія генератора або політики перевірки змінилася після цієї роботи; "
            "повторна перевірка потребує окремого рішення.",
        )
    completed_ids = {
        (e.payload or {}).get("attempt_id")
        for e in events
        if e.event_type in {"academic_review", "academic_review_retry_discarded"}
    }
    if any(
        e.event_type == RETRY_STARTED
        and (e.payload or {}).get("attempt_id") not in completed_ids
        and retry_pending(e)
        for e in events
    ):
        raise HTTPException(409, "Академічна перевірка вже триває.")
    previous = (
        next(
            (e.payload for e in reversed(events) if e.event_type == "academic_review"),
            {},
        )
        or {}
    )
    artifact = (
        next(
            (
                e.payload
                for e in reversed(events)
                if e.event_type == "academic_review_artifact"
            ),
            {},
        )
        or {}
    )
    if (
        previous.get("status") != "unchecked"
        or previous.get("binding") != binding
        or artifact.get("binding") != binding
    ):
        raise HTTPException(
            409,
            "Повтор доступний лише для технічно незавершеної перевірки цього самого тексту.",
        )
    if (
        artifact.get("docx_sha256") != doc.docx_sha256
        or artifact.get("docx_path") != doc.docx_path
    ):
        raise HTTPException(409, "DOCX змінився після перевірки.")
    if await StorageService().get_file_sha256(str(doc.docx_path)) != doc.docx_sha256:
        raise HTTPException(409, "Збережений файл не відповідає контрольній сумі.")
    method = (
        next(
            (
                e.payload
                for e in reversed(events)
                if e.event_type == "source_pack_preflight"
                and (e.payload or {}).get("sha256") == pack.sha256()
            ),
            {},
        )
        or {}
    )
    if not method.get("retrieval_trace"):
        raise HTTPException(409, "Немає фактичного запису пошуку джерел.")
    prompt, reviewed = review_prompt(
        doc,
        pack,
        method,
        kind="whole",
        run_requirements=(job.request_payload or {}).get("additional_requirements"),
    )
    if len(prompt) > REVIEW_MAX_CHARS:
        raise HTTPException(409, "Повний текст перевищує місткість перевірки.")
    base = {
        "binding": binding,
        "kind": "whole",
        "attempt_id": attempt_id,
        "actor_id": actor_id,
    }
    db.add(
        DocumentProvenance(
            document_id=doc.id,
            stage="quality",
            event_type=RETRY_STARTED,
            payload={**base, "status": "pending"},
        )
    )
    await db.commit()  # releases document/case locks before the model call
    original_artifact = (str(doc.docx_path), str(doc.docx_sha256))
    job_id = int(job.id)
    section_count = len((doc.outline or {}).get("sections") or [])
    from app.services.generation_operations import journal_usage

    previous_usage, _unknown = await journal_usage(db, int(doc.id), job_id)
    previous_cost_offset = max(
        0, int(job.cost_cents or 0) - previous_usage.cost_usd_cents()
    )
    usage = UsageTracker()
    # Every SDK call of this retry gets a durable receipt on the same job.
    usage.generation_context = {
        "document_id": int(doc.id),
        "job_id": job_id,
        "worker_attempt": int(job.attempt_count or 0),
        "review_retry_attempt_id": attempt_id,
    }
    cancellation = None
    try:
        service = ai_service or AIService(db, usage_tracker=usage, max_retries=0)
        response = await asyncio.wait_for(
            service.call_with_fallback(
                prompt,
                purpose="academic_review_retry",
                chain_override=settings.AI_FALLBACK_CHAIN_LIST[:1],
            ),
            timeout=90,
        )
        outcome = {
            **base,
            **validate_review(response, reviewed, section_count, set(pack.keys())),
        }
    except asyncio.CancelledError as error:
        cancellation = error
        outcome = {
            **base,
            "status": "unchecked",
            "reason": "Повторну перевірку перервано.",
        }
    except Exception as error:
        outcome = {
            **base,
            "status": "unchecked",
            "reason": f"Повторна перевірка не завершена ({type(error).__name__}).",
        }
    # Reacquire the same lock order. A stale callback may record spend, but it
    # cannot replace a newer attempt's review or attach to a changed artifact.
    from app.services.production_case_service import ProductionCaseService

    db.expire_all()
    _, current_doc = await ProductionCaseService(db).get_case_and_document_for_update(
        case_id
    )
    db.expire(current_doc)
    await db.refresh(current_doc)
    current_events = list(
        (
            await db.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.document_id == current_doc.id)
                .order_by(DocumentProvenance.id.asc())
            )
        )
        .scalars()
        .all()
    )
    latest_claim = (
        next(
            (
                e.payload
                for e in reversed(current_events)
                if e.event_type == RETRY_STARTED
            ),
            {},
        )
        or {}
    )
    current = False
    if latest_claim.get("attempt_id") == attempt_id:
        try:
            _, _, _, _, current_binding = await _snapshot(db, case_id)
            current = (
                current_binding == binding
                and (str(current_doc.docx_path), str(current_doc.docx_sha256))
                == original_artifact
            )
        except HTTPException:
            current = False
    if current:
        try:
            current = (
                await StorageService().get_file_sha256(original_artifact[0])
                == original_artifact[1]
            )
        except Exception:
            current = False
    if not current:
        outcome = {
            **base,
            "status": "unchecked",
            "reason": "Результат відкинуто: робота або поточна спроба змінилася.",
        }
    db.add(
        DocumentProvenance(
            document_id=current_doc.id,
            stage="quality",
            event_type=(
                "academic_review" if current else "academic_review_retry_discarded"
            ),
            payload=outcome,
        )
    )
    if current:
        db.add(
            DocumentProvenance(
                document_id=current_doc.id,
                stage="export",
                event_type="academic_review_artifact",
                payload={**artifact, "binding": binding},
            )
        )
    await db.execute(
        update(AIGenerationJob)
        .where(AIGenerationJob.id == job_id)
        .values(
            total_tokens=func.coalesce(AIGenerationJob.total_tokens, 0)
            + usage.total_tokens,
            cost_cents=previous_cost_offset + usage.cost_usd_cents(previous_usage),
        )
    )
    await db.commit()  # result and incremental spend are atomic, once per request
    if cancellation:
        raise cancellation
    return outcome
