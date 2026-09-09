"""S6: persist complete DOCX before the advisory whole-document review."""

import math
from datetime import datetime

from app.core import database
from app.services.ai_pipeline.citation_formatter import bibliography_heading
from app.services.document_service import DocumentService
from app.services.docx_export import assemble_section
from app.services.generation_operations import journal_usage
from app.services.generation_policy import RecordingPersistenceError
from app.services.generation_worker import (
    persist_generation_artifact,
    update_generation_document,
)

from .budgets import POLICY, model_call
from .warnings import ExecutionStop


async def assemble(ctx, sections, bibliography, pack):
    content = "\n\n".join(assemble_section(s["title"], s["content"]) for s in sections)
    if bibliography:
        content += (
            "\n\n# "
            + bibliography_heading(ctx.inputs["brief"]["language"])
            + "\n\n"
            + "\n\n".join(r["formatted"] for r in bibliography)
        )
    try:
        async with database.AsyncSessionLocal() as db:
            await update_generation_document(
                db, **ctx.fence, values={"content": content}
            )
        async with database.AsyncSessionLocal() as db:
            artifact = await DocumentService(db).export_document(
                ctx.job.document_id,
                "docx",
                ctx.job.user_id,
                persist_pointer=False,
                exported_at=datetime.fromisoformat(ctx.inputs["exported_at"]),
            )
        async with database.AsyncSessionLocal() as db:
            await persist_generation_artifact(
                db,
                **ctx.fence,
                artifact_format="docx",
                storage_path=artifact["storage_path"],
                artifact_sha256=artifact["artifact_sha256"],
            )
    except Exception as error:
        cause = error
        while cause.__cause__ is not None:
            cause = cause.__cause__
        if (
            isinstance(cause, OSError | RecordingPersistenceError)
            or type(cause).__module__.startswith(("sqlalchemy", "botocore", "minio"))
            or (getattr(cause, "status_code", 0) or 0) >= 500
        ):
            raise ExecutionStop("storage_or_db", "Не вдалося зберегти DOCX.") from error
        raise
    docx = {
        "sha256": artifact["artifact_sha256"],
        "size": artifact["file_size"],
        "estimated_pages": max(
            1,
            math.ceil(
                sum(s["word_count"] for s in sections) / POLICY["words_per_page"]
            ),
        ),
        "storage_path": artifact["storage_path"],
    }
    await ctx.emit("executor_artifact", docx)
    # Review is advisory even if the reviewer is unavailable. Recording errors
    # remain technical stops, while the already persisted artifact is retained.
    try:
        review, truncated = await model_call(
            ctx,
            "Review the complete academic work. Reply with plain text beginning PASS or FAIL, followed by concise notes. Do not rewrite it.\n"
            + content,
            budget=POLICY["review_tokens"],
            purpose="S6",
        )
        await ctx.emit("executor_review", {"text": review, "truncated": truncated})
        if truncated or review.strip() != "PASS":
            await ctx.warn(
                (
                    "review_negative"
                    if review.lstrip().startswith("FAIL")
                    else "review_note"
                ),
                detail=review,
            )
    except ExecutionStop as error:
        if error.budget:
            raise
        await ctx.warn("review_note", detail=error.stop["message_uk"])
    async with database.AsyncSessionLocal() as db:
        totals, unknown = await journal_usage(db, ctx.job.document_id, ctx.job.id)
        from sqlalchemy import select

        from app.models.document import DocumentProvenance

        events = list(
            (
                await db.execute(
                    select(DocumentProvenance)
                    .where(
                        DocumentProvenance.document_id == ctx.job.document_id,
                        DocumentProvenance.event_type == "generation_provider_attempt",
                    )
                    .order_by(DocumentProvenance.id)
                )
            ).scalars()
        )
    calls = {
        e.payload["attempt_id"]: e.payload
        for e in events
        if e.payload.get("job_id") == ctx.job.id
        and e.payload.get("outcome") != "started"
    }
    accounting = []
    from app.services.cost_estimator import UsageTracker

    for call in calls.values():
        usage = call.get("usage") or {}
        tracker = UsageTracker()
        tracker.add(
            "anthropic",
            call["model"],
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )
        accounting.append(
            {
                "attempt_id": call["attempt_id"],
                "model": call["model"],
                "tokens": tracker.total_tokens if usage else None,
                "cost_cents": tracker.cost_usd_cents() if usage else None,
                "outcome": call["outcome"],
            }
        )
    return {
        "docx": docx,
        "sections": [
            {k: s[k] for k in ("title", "section_index", "word_count")}
            for s in sections
        ],
        "bibliography": bibliography,
        "sources": [{"key": r["key"], "origin": r["origin"]} for r in bibliography],
        "usage": {
            "calls": accounting,
            "tokens": totals.total_tokens,
            "cost_cents": totals.cost_usd_cents(),
            "unknown_attempts": unknown,
        },
        "recording_id": f"executor-v2:job:{ctx.job.id}",
        "warnings": list(ctx.warnings),
    }
