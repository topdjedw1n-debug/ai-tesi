"""
Provenance ledger service.

Append-only audit trail of document generation pipeline events
(table document_provenance). Writes are best-effort: a failed write
must never break the generation pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentProvenance

logger = logging.getLogger(__name__)


def derive_quality_gate_status(payload: dict[str, Any] | None) -> str:
    """
    Honest status of a quality_gate event: "passed" | "failed" | "unchecked".

    New events carry an explicit `status`. Legacy events (written when
    provider failures silently passed) are reinterpreted at read time:
    gates disabled or any check score missing means the checks did not
    actually run — "unchecked", never "passed".

    Mirrored in apps/web/lib/provenance.ts (deriveQualityGateStatus);
    update both together.
    """
    payload = payload or {}
    status = payload.get("status")
    if status in {"passed", "failed", "unchecked"}:
        return status
    if payload.get("passed") is False:
        return "failed"
    if payload.get("gates_enabled") is False:
        return "unchecked"
    if any(
        payload.get(key) is None
        for key in ("grammar_score", "plagiarism_score", "ai_detection_score")
    ):
        return "unchecked"
    return "passed"


async def record_event(
    db: AsyncSession,
    document_id: int,
    stage: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Append one event to the document's provenance ledger (best-effort).

    Commits immediately so the event survives later pipeline failures.
    ⚠️ Non-critical: never raises. On failure logs and rolls back so the
    shared pipeline session stays usable.
    """
    try:
        db.add(
            DocumentProvenance(
                document_id=document_id,
                stage=stage,
                event_type=event_type,
                payload=payload,
            )
        )
        await db.commit()
    except Exception as e:
        logger.warning(
            f"⚠️ Failed to record provenance event {stage}/{event_type} "
            f"for document {document_id}: {e}"
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.warning(
                f"⚠️ Rollback after provenance write failed: {rollback_error}"
            )
