"""Narrow operational gateway. No admin, arbitrary SQL, shell or deploy tools.

The Telegram transport supplies the verified numeric sender ID. Never take it
from LLM arguments. The gateway independently maps that ID to an active user
and checks document ownership on every request, including confirmation replay.
"""

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.generate import enqueue_full_document
from app.core.config import settings
from app.core.database import get_db
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    DocumentSourceFile,
    ProductionCase,
)
from app.models.operator_bot import OperatorBotAction, OperatorSupportRequest
from app.schemas.document import AsyncGenerationRequest
from app.services.generation_contract import generation_contract_sha256
from app.services.task_contract import build_task_contract
from app.services.uploaded_sources import (
    uploaded_sources_blockers,
    uploaded_sources_digest,
)

router = APIRouter()


async def operator_identity(
    x_operator_bot_key: str = Header(default=""),
    x_telegram_user_id: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> tuple[str, User]:
    secret = settings.OPERATOR_BOT_SECRET
    if (
        not secret
        or len(secret) < 32
        or not secrets.compare_digest(x_operator_bot_key, secret)
    ):
        raise HTTPException(
            401, "Bot access is not configured or credential is invalid."
        )
    uid = settings.OPERATOR_BOT_USERS.get(x_telegram_user_id)
    if not uid or not x_telegram_user_id.isdecimal():
        raise HTTPException(403, "Telegram account has no Thesica access.")
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or cast(datetime | None, user.deletion_requested_at) is not None
    ):
        raise HTTPException(403, "Thesica account is unavailable.")
    return x_telegram_user_id, user


async def owned_document(db: AsyncSession, document_id: int, user_id: int) -> Document:
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Роботу не знайдено серед доступних тобі.")
    return doc


async def latest_job(db: AsyncSession, document_id: int) -> AIGenerationJob | None:
    return (
        await db.execute(
            select(AIGenerationJob)
            .where(AIGenerationJob.document_id == document_id)
            .order_by(AIGenerationJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def safe_error(message: Any) -> str | None:
    if not message:
        return None
    # Do not forward credentials, signed URLs, filesystem paths or stack traces
    # to the transport/model. Keep actionable stage/quality failure details.
    value = str(message).split("Traceback (most recent call last)")[0]
    value = re.sub(r"https?://\S+", "[URL приховано]", value)
    value = re.sub(
        r"(?i)(bearer\s+|(?:api[_-]?key|token|password|secret)\s*[=:]\s*)\S+",
        r"\1[приховано]",
        value,
    )
    value = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[приховано]", value)
    value = re.sub(r"/(?:opt|app|home|Users|tmp)/\S+", "[шлях приховано]", value)
    return value[:2000]


async def diagnostic(db: AsyncSession, doc: Document) -> dict[str, Any]:
    job = await latest_job(db, int(doc.id))
    case = (
        await db.execute(
            select(ProductionCase).where(ProductionCase.document_id == doc.id)
        )
    ).scalar_one_or_none()
    blockers, warnings = await uploaded_sources_blockers(db, int(doc.id))
    files = (
        (
            await db.execute(
                select(DocumentSourceFile)
                .where(DocumentSourceFile.document_id == doc.id)
                .order_by(DocumentSourceFile.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "document_id": doc.id,
        "topic": doc.topic,
        "status": doc.status,
        "pages": doc.target_pages,
        "language": doc.language,
        "url": f"https://app.thesica.co/dashboard/documents/{doc.id}",
        "job": (
            None
            if job is None
            else {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "error": safe_error(job.error_message),
            }
        ),
        "source_blockers": blockers,
        "source_warnings": warnings,
        "release_status": case.release_status if case else "not_reviewed",
        "contract": build_task_contract(doc, uploaded_files=list(files)),
        "document_requirements": doc.additional_requirements,
        "case_requirements": case.requirements_text if case else None,
        "delivery_note": "Завершена генерація ще не означає перевірений і дозволений до видачі DOCX.",
    }


async def fingerprint(db: AsyncSession, doc: Document) -> str:
    case = (
        await db.execute(
            select(ProductionCase).where(ProductionCase.document_id == doc.id)
        )
    ).scalar_one_or_none()
    # A generated case's initial defaults must not make the pre-run snapshot
    # match a materially different request. Include all persisted requirements.
    contract = generation_contract_sha256(
        doc,
        case,
        cast(str | None, case.requirements_text) if case else None,
        await uploaded_sources_digest(db, int(doc.id)),
    )
    return hashlib.sha256(
        json.dumps(
            {
                "generation": contract,
                "task": build_task_contract(doc)["sha256"],
                "status": doc.status,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


class PrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retry_reason: str | None = Field(default=None, max_length=2000)


class ProposedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(max_length=300)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    patch: str = Field(min_length=1, max_length=50000)


class SupportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    document_id: int | None = Field(default=None, gt=0)
    summary: str = Field(min_length=5, max_length=6000)
    proposed_changes: list[ProposedChange] = Field(default_factory=list, max_length=8)


@router.get("/me")
async def me(identity: tuple[str, User] = Depends(operator_identity)) -> dict[str, Any]:
    return {
        "project": "Thesica",
        "user_id": identity[1].id,
        "unlimited_generation": identity[1].id
        in settings.UNLIMITED_GENERATION_USER_IDS,
        "deploy_allowed": False,
    }


@router.get("/documents")
async def documents(
    before_id: int | None = None,
    identity: tuple[str, User] = Depends(operator_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    query = select(Document).where(Document.user_id == identity[1].id)
    if before_id is not None:
        query = query.where(Document.id < before_id)
    rows = (
        (await db.execute(query.order_by(Document.id.desc()).limit(21))).scalars().all()
    )
    return {
        "documents": [
            {"id": d.id, "topic": d.topic, "status": d.status, "pages": d.target_pages}
            for d in rows[:20]
        ],
        "next_before_id": rows[19].id if len(rows) > 20 else None,
    }


@router.get("/documents/{document_id}")
async def document_status(
    document_id: int,
    identity: tuple[str, User] = Depends(operator_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await diagnostic(
        db, await owned_document(db, document_id, int(identity[1].id))
    )


@router.get("/jobs/{job_id}")
async def job_status(
    job_id: int,
    identity: tuple[str, User] = Depends(operator_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = (
        await db.execute(
            select(AIGenerationJob).where(
                AIGenerationJob.id == job_id, AIGenerationJob.user_id == identity[1].id
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Спробу не знайдено.")
    await owned_document(db, int(job.document_id), int(identity[1].id))
    return {
        "job_id": job.id,
        "document_id": job.document_id,
        "status": job.status,
        "progress": job.progress,
        "error": safe_error(job.error_message),
    }


@router.post("/documents/{document_id}/prepare")
async def prepare_generation(
    document_id: int,
    payload: PrepareRequest,
    identity: tuple[str, User] = Depends(operator_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    doc = await owned_document(db, document_id, int(identity[1].id))
    job = await latest_job(db, document_id)
    if doc.status in {"completed", "generating"} or (
        job and job.status in {"queued", "running"}
    ):
        raise HTTPException(
            409, "Робота вже завершена або вже генерується. Перевір її стан."
        )
    if job and not (payload.retry_reason or "").strip():
        raise HTTPException(
            409, "Для повтору вкажи, що змінилося після попередньої спроби."
        )
    info = await diagnostic(db, doc)
    case = (
        await db.execute(
            select(ProductionCase).where(ProductionCase.document_id == document_id)
        )
    ).scalar_one_or_none()
    if (
        case
        and str(case.citation_style or "apa").lower().replace("apa-7", "apa")
        != str(doc.citation_style or "apa").lower()
    ):
        raise HTTPException(
            409,
            "Стиль цитування у виробничій справі та роботі відрізняється. Узгодь його на сайті перед запуском.",
        )
    if info["source_blockers"]:
        raise HTTPException(409, {"source_blockers": info["source_blockers"]})
    action = OperatorBotAction(
        id=secrets.token_hex(16),
        telegram_user_id=identity[0],
        user_id=identity[1].id,
        document_id=document_id,
        fingerprint=await fingerprint(db, doc),
        last_job_id=job.id if job else None,
        retry_reason=payload.retry_reason,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    db.add(action)
    await db.commit()
    return {
        "action_id": action.id,
        "diagnostic": info,
        "retry_reason": payload.retry_reason,
        "message": "Після перегляду умов натисни «Підтверджую і запускаю». Це платна генерація.",
    }


@router.post("/actions/{action_id}/confirm")
async def confirm_generation(
    action_id: str,
    identity: tuple[str, User] = Depends(operator_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # Same lock order as normal enqueue (user -> document -> case).
    user = (
        await db.execute(
            select(User)
            .where(User.id == identity[1].id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if (
        not user.is_active
        or cast(datetime | None, user.deletion_requested_at) is not None
    ):
        raise HTTPException(403, "Обліковий запис недоступний.")
    action = (
        await db.execute(
            select(OperatorBotAction)
            .where(
                OperatorBotAction.id == action_id,
                OperatorBotAction.user_id == user.id,
                OperatorBotAction.telegram_user_id == identity[0],
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if action is None:
        raise HTTPException(404, "Підтвердження не знайдено.")
    await owned_document(db, int(action.document_id), int(user.id))
    prior_result = cast(dict[str, Any] | None, action.result)
    if prior_result is not None:
        return prior_result
    if action.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
        raise HTTPException(
            409, "Підтвердження застаріло. Переглянь актуальні умови ще раз."
        )
    doc = (
        await db.execute(
            select(Document)
            .where(Document.id == action.document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    await db.execute(
        select(ProductionCase)
        .where(ProductionCase.document_id == doc.id)
        .with_for_update()
    )
    job = await latest_job(db, int(doc.id))
    if (job.id if job else None) != action.last_job_id or await fingerprint(
        db, doc
    ) != action.fingerprint:
        raise HTTPException(
            409, "Робота змінилася після перегляду. Перевір актуальний стан і умови."
        )
    contract = build_task_contract(doc)
    doc.contract_confirmed_sha256 = contract["sha256"]
    # Legacy Column descriptors are instance values at runtime.
    doc.contract_confirmed_at = datetime.utcnow()  # type: ignore[assignment]
    db.add(
        DocumentProvenance(
            document_id=doc.id,
            stage="intake",
            event_type="task_contract_confirmed",
            payload={
                "sha256": contract["sha256"],
                "basis": contract["basis"],
                "assumptions": contract["assumptions"],
                "confirmed_by_user_id": user.id,
                "channel": "telegram",
                "telegram_user_id": identity[0],
                "action_id": action.id,
                "retry_reason": action.retry_reason,
            },
        )
    )

    def receipt(enqueued: AIGenerationJob) -> None:
        # Receipt and job commit atomically: retries after network/process failure
        # return this job even if it has since failed or completed.
        action.result = {  # type: ignore[assignment]
            "job_id": enqueued.id,
            "document_id": doc.id,
            "status": "queued",
        }
        db.add(action)

    await db.flush()  # enqueue refreshes the locked document from the database
    result = await enqueue_full_document(
        AsyncGenerationRequest(document_id=int(doc.id)),
        user,
        db,
        on_enqueued=receipt,
    )
    if cast(dict[str, Any] | None, action.result) is None:
        action.result = {  # type: ignore[assignment]
            "job_id": result.job_id,
            "document_id": doc.id,
            "status": result.status,
        }
        db.add(action)
        await db.commit()
    return cast(dict[str, Any], action.result)


@router.post("/support-requests")
async def request_support(
    payload: SupportRequest,
    identity: tuple[str, User] = Depends(operator_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    existing = await db.get(OperatorSupportRequest, payload.request_id)
    if existing:
        if (
            existing.user_id != identity[1].id
            or existing.telegram_user_id != identity[0]
        ):
            raise HTTPException(404, "Звернення не знайдено.")
        return {"request_id": existing.id, "status": existing.status}
    evidence = {}
    if payload.document_id is not None:
        evidence = await diagnostic(
            db, await owned_document(db, payload.document_id, int(identity[1].id))
        )
    if payload.proposed_changes:
        evidence["code_proposal"] = {
            "changes": [change.model_dump() for change in payload.proposed_changes],
            "validation": "not_applied_or_tested",
            "deployment": "not_authorized",
        }
    row = OperatorSupportRequest(
        id=payload.request_id,
        telegram_user_id=identity[0],
        user_id=identity[1].id,
        document_id=payload.document_id,
        summary=payload.summary,
        evidence=evidence,
        status="pending_review",
    )
    db.add(row)
    await db.commit()
    return {
        "request_id": row.id,
        "status": row.status,
        "has_code_proposal": bool(payload.proposed_changes),
        "message": (
            "Пропозицію виправлення збережено. Вона ще не застосована, не протестована й не встановлена."
            if payload.proposed_changes
            else "Звернення збережено для розбору. Виправлення ще не підготовлене і не встановлене."
        ),
    }


@router.get("/support-requests")
async def support_requests(
    identity: tuple[str, User] = Depends(operator_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                select(OperatorSupportRequest)
                .where(
                    OperatorSupportRequest.user_id == identity[1].id,
                    OperatorSupportRequest.telegram_user_id == identity[0],
                )
                .order_by(OperatorSupportRequest.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return {
        "requests": [
            {
                "id": row.id,
                "document_id": row.document_id,
                "summary": row.summary,
                "status": row.status,
                "has_code_proposal": bool(row.evidence.get("code_proposal")),
            }
            for row in rows
        ]
    }
