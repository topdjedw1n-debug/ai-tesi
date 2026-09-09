"""Non-secret initial state for an isolated local generation replay."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.models.document import (
    DocumentProvenance,
    DocumentSection,
    DocumentSource,
    DocumentSourceFile,
    ProductionCase,
    SourceFilePage,
)
from app.services.generation_profile import generation_profile
from app.services.model_recording import json_value

_REPLAY_PREFIXES = (
    "AI_",
    "QUALITY_",
    "GROUNDING_",
    "SOURCE_",
    "CLAIM_",
    "HUMANIZER_",
    "PLAGIARISM_",
    "LANGUAGETOOL_",
    "TRAINING_DATA_",
    "METHODOLOGY_",
    "PROVENANCE_",
    "CITATION_",
    "ACADEMIC_",
    "CROSSREF_",
    "OPENALEX_",
    "SEMANTIC_SCHOLAR_",
    "TAVILY_",
    "SERPER_",
    "PERPLEXITY_",
    "GPTZERO_",
    "ORIGINALITY_",
    "COPYSCAPE_",
)
# A tape cannot redirect DB/storage/account configuration before the network guard.
REPLAY_SETTING_NAMES = frozenset(
    name
    for name in type(settings).model_fields
    if name.startswith(_REPLAY_PREFIXES)
    and not any(
        word in name
        for word in ("KEY", "SECRET", "TOKEN", "PASSWORD", "USERNAME", "URL", "PATH")
    )
) | {"LANGUAGETOOL_API_URL"}


def row_data(row: Any) -> dict[str, Any]:
    return {
        column.name: json_value(getattr(row, column.name))
        for column in row.__table__.columns
    }


async def snapshot_inputs(
    db: Any, document: Any, job: Any, *, worker_attempt: int
) -> dict[str, Any]:
    # A claim/rollback may expire server-populated columns. Load them through
    # the async session before synchronous serialization touches attributes.
    await db.refresh(document)
    await db.refresh(job)
    tables = {}
    for model in (DocumentSection, DocumentSource, DocumentSourceFile, ProductionCase):
        rows = (
            (await db.execute(select(model).where(model.document_id == document.id)))
            .scalars()
            .all()
        )
        tables[model.__tablename__] = [row_data(row) for row in rows]
    file_ids = [r["id"] for r in tables["document_source_files"]]
    pages = (
        (
            await db.execute(
                select(SourceFilePage).where(
                    SourceFilePage.source_file_id.in_(file_ids)
                )
            )
        )
        .scalars()
        .all()
        if file_ids
        else []
    )
    tables["source_file_pages"] = [row_data(row) for row in pages]
    prior = (
        (
            await db.execute(
                select(DocumentProvenance)
                .where(
                    DocumentProvenance.document_id == document.id,
                    DocumentProvenance.event_type.not_in(
                        [
                            "generation_replay_inputs",
                            "generation_provider_attempt",
                            "generation_dependency",
                        ]
                    ),
                )
                .order_by(DocumentProvenance.id)
            )
        )
        .scalars()
        .all()
    )
    tables["document_provenance"] = [row_data(row) for row in prior]
    return {
        "job_id": job.id,
        "worker_attempt": worker_attempt,
        "document": row_data(document),
        # Fencing credentials and user account secrets are not replay inputs.
        "job": {
            k: v
            for k, v in row_data(job).items()
            if k not in {"lease_token", "lease_owner"}
        },
        "profile": generation_profile(document, job.user_id),
        "replay_settings": {
            name: json_value(getattr(settings, name))
            for name in sorted(REPLAY_SETTING_NAMES)
        },
        "provider_presence": {
            name: bool(getattr(settings, name))
            for name in type(settings).model_fields
            if name.endswith("_API_KEY") or name == "COPYSCAPE_USERNAME"
        },
        "tables": tables,
    }
