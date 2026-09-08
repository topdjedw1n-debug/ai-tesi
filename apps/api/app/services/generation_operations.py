"""Durable receipts for each SDK call, inside every existing retry layer.

Only request/response digests are stored, never prompts or credentials. A started
receipt without a confirmed response is unknown spend, including process death.
This journal is observational: late provider receipts do not mutate work or leases.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, TypeVar
from uuid import uuid4

from sqlalchemy import select

from app.core import database
from app.models.document import DocumentProvenance
from app.services.academic_context import digest
from app.services.cost_estimator import UsageTracker
from app.services.generation_outcomes import failure_reason

T = TypeVar("T")

# The business purpose of the current external operation (outline review,
# plan preparation, claim check...). Set by the caller that knows it, read by
# the SDK wrapper below, so legacy provider call signatures stay unchanged.
operation_purpose: ContextVar[str | None] = ContextVar(
    "generation_operation_purpose", default=None
)

_REVIEW_PURPOSE_MARKERS = ("review", "preparation")


def _stage_for_purpose(purpose: str) -> str:
    return (
        "review"
        if any(marker in purpose for marker in _REVIEW_PURPOSE_MARKERS)
        else purpose
    )


async def _append(context: dict[str, Any], payload: dict[str, Any]) -> None:
    # No job/document lock here: the caller can already hold a fenced stage lock.
    # Provenance has only a Document FK; this cannot commit the caller's work.
    async with database.AsyncSessionLocal() as db:
        db.add(
            DocumentProvenance(
                document_id=context["document_id"],
                stage="provider",
                event_type="generation_provider_attempt",
                payload={**context, **payload},
            )
        )
        await db.commit()


async def recorded_provider_call(
    call: Callable[..., Awaitable[T]],
    *,
    provider: str,
    model: str,
    request: dict[str, Any],
    usage_tracker: UsageTracker | None,
    purpose: str,
) -> T:
    context = getattr(usage_tracker, "generation_context", None)
    if not isinstance(context, dict):
        return await call(**request)
    purpose = operation_purpose.get() or purpose
    base = {
        "attempt_id": str(uuid4()),
        "stage": purpose,
        "provider": provider,
        "model": model,
        "input_fingerprint": digest(request),
        "output_reference": None,
    }
    # If the journal cannot commit, do not begin a paid external operation.
    await _append(context, {**base, "outcome": "started", "usage": None})
    try:
        response = await call(**request)
    except BaseException as error:
        reason = failure_reason(error, stage=_stage_for_purpose(purpose))
        # A cancelled request may have reached the provider; no zero-cost claim.
        await asyncio.shield(
            _append(
                context,
                {
                    **base,
                    "outcome": "outcome_unknown",
                    "reason_code": reason,
                    "usage": None,
                },
            )
        )
        raise
    usage = getattr(response, "usage", None)
    confirmed = None
    if usage is not None:
        confirmed = {
            "input_tokens": int(
                getattr(
                    usage,
                    "prompt_tokens" if provider == "openai" else "input_tokens",
                    0,
                )
                or 0
            ),
            "output_tokens": int(
                getattr(
                    usage,
                    "completion_tokens" if provider == "openai" else "output_tokens",
                    0,
                )
                or 0
            ),
        }
    response_id = getattr(response, "id", None)
    await _append(
        context,
        {
            **base,
            "outcome": "received",
            "output_reference": response_id if isinstance(response_id, str) else None,
            "usage": confirmed,
        },
    )
    return response


async def journal_usage(
    db: Any, document_id: int, job_id: int
) -> tuple[UsageTracker, int]:
    events = (
        await db.execute(
            select(DocumentProvenance)
            .where(
                DocumentProvenance.document_id == document_id,
                DocumentProvenance.event_type == "generation_provider_attempt",
            )
            .order_by(DocumentProvenance.id)
        )
    ).scalars()
    attempts: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event.payload or {}
        if payload.get("job_id") == job_id:
            attempts[payload["attempt_id"]] = payload
    totals = UsageTracker()
    unknown = 0
    for event in attempts.values():
        usage = event.get("usage")
        if isinstance(usage, dict):
            totals.add(
                event["provider"],
                event["model"],
                usage["input_tokens"],
                usage["output_tokens"],
            )
        else:
            unknown += 1
    return totals, unknown
