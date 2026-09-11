"""S6: persist complete DOCX before the advisory whole-document review."""

import math
import re
from datetime import datetime

from sqlalchemy import select

from app.core import database
from app.models.document import DocumentProvenance
from app.services.ai_pipeline.citation_formatter import bibliography_heading
from app.services.cost_estimator import UsageTracker
from app.services.document_service import DocumentService
from app.services.docx_export import assemble_section
from app.services.generation_operations import journal_usage
from app.services.generation_policy import RecordingPersistenceError
from app.services.generation_worker import (
    persist_generation_artifact,
    update_generation_document,
)

from .budgets import POLICY, json_call
from .warnings import ExecutionStop, unusable


async def assemble(ctx, sections, bibliography, pack):
    placeholders = re.compile(
        r"(?<!\w)(?:"
        + "|".join(
            re.escape(p).replace(r"\ ", r"\s+") for p in POLICY["placeholder_phrases"]
        )
        + r")(?!\w)",
        re.I,
    )
    for section in sections:
        # Raw text also retains placeholders removed as unknown citation markers.
        matches = placeholders.findall(
            section["content"] + "\n" + section["raw_content"]
        )
        if matches:
            await ctx.warn(
                "placeholder_text",
                section_index=section["section_index"],
                detail="; ".join(sorted({m.casefold() for m in matches})),
            )
    content = "\n\n".join(assemble_section(s["title"], s["content"]) for s in sections)
    if bibliography:
        content += "\n\n" + assemble_section(
            bibliography_heading(ctx.inputs["brief"]["language"]),
            "\n\n".join(r["formatted"] for r in bibliography),
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
    words = sum(s["word_count"] for s in sections)
    docx = {
        "sha256": artifact["artifact_sha256"],
        "size": artifact["file_size"],
        "estimated_pages": max(1, math.ceil(words / POLICY["words_per_page"])),
        "storage_path": artifact["storage_path"],
    }
    await ctx.emit("executor_artifact", docx)
    # Invalid review JSON stops the job but retains the already persisted DOCX.
    try:
        review = await json_call(
            ctx,
            'Review the complete academic work. Reply only with JSON {"verdict":"PASS" or "FAIL","notes":"concise notes"}. Do not rewrite it.\n'
            + content,
            budget=POLICY["review_tokens"],
            purpose="S6",
        )
        verdict, notes = review.get("verdict"), review.get("notes")
        if verdict not in ("PASS", "FAIL") or not isinstance(notes, str):
            raise unusable("Хибний формат огляду.")
        text = verdict + "\n" + notes
        await ctx.emit("executor_review", {"text": text, "truncated": False})
        if verdict == "FAIL" or notes.strip():
            code = "review_negative" if verdict == "FAIL" else "review_note"
            await ctx.warn(code, detail=text)
    except ExecutionStop as error:
        if error.budget or error.stop["code"] == "provider_unusable_response":
            raise
        await ctx.warn("review_note", detail=error.stop["message_uk"])
    async with database.AsyncSessionLocal() as db:
        totals, unknown = await journal_usage(db, ctx.job.document_id, ctx.job.id)
        events = await db.scalars(
            select(DocumentProvenance)
            .where(
                DocumentProvenance.document_id == ctx.job.document_id,
                DocumentProvenance.event_type == "generation_provider_attempt",
            )
            .order_by(DocumentProvenance.id)
        )
    calls = {
        e.payload["attempt_id"]: e.payload
        for e in events
        if e.payload.get("job_id") == ctx.job.id
        and e.payload.get("outcome") != "started"
    }
    accounting = []
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
