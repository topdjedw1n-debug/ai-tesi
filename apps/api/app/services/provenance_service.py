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
