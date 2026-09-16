"""Warnings of one generation run, as the manager reads them.

The executor records every advisory finding as a `generation_warning`
provenance event (code, severity, stage, section, message_uk, detail). The
delivery page and the work page show the same rows, so both read them here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentProvenance


def section_label(payload: dict[str, Any]) -> str:
    index = payload.get("section_index")
    return f"Розділ {index}" if index else "Загальні зауваження"


async def generation_warnings(
    db: AsyncSession, document_id: int, job_id: int
) -> list[dict[str, Any]]:
    """Executor v2 warnings of the job, in the order they were recorded."""
    events = (
        await db.execute(
            select(DocumentProvenance)
            .where(
                DocumentProvenance.document_id == document_id,
                DocumentProvenance.event_type == "generation_warning",
            )
            .order_by(DocumentProvenance.id)
        )
    ).scalars()
    return [
        {"id": event.id, **payload, "section_label": section_label(payload)}
        for event in events
        if (payload := event.payload or {}).get("job_id") == job_id
    ]
