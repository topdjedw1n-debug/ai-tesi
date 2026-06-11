"""
Claim verification stage (Academic Quality Engine).

Advisory claim-faithfulness audit: checks that cited sources actually
support the sentences citing them. Never blocks the pipeline.

Patch-sensitive collaborators (settings, AIService, websocket progress)
are injected by the caller — see the thin wrapper in
app.services.background_jobs, which passes its module globals at call
time so existing monkeypatches keep working. This module must NOT import
the settings instance or the websocket manager directly.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentSection, DocumentSource
from app.services.claim_verifier import ClaimVerifier, summarize_verdicts
from app.services.db_helpers import safe_scalars_all
from app.services.provenance_service import record_event

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

SendProgress = Callable[[int, dict[str, Any]], Awaitable[None]]


async def run_claim_verification_stage(
    db: AsyncSession,
    document_id: int,
    user_id: int,
    *,
    config: Settings,
    ai_service_factory: Callable[[AsyncSession], Any],
    send_progress: SendProgress,
) -> None:
    """
    Advisory claim-faithfulness pass (after citation verification, before
    export).

    For each completed section: extract sentences carrying [Author, Year]
    citations, match them to persisted DocumentSource rows and ask the LLM
    (AIService fallback chain) whether the cited abstract supports each
    sentence. Verdicts go to DocumentSection.claim_verification and the
    provenance ledger.

    ⚠️ Advisory only: NEVER raises and never blocks the pipeline -
    unsupported claims are recorded as flags. LLM spend is capped at
    CLAIM_VERIFICATION_MAX_CHECKS claims per document.
    """
    try:
        sections_result = await db.execute(
            select(DocumentSection)
            .where(
                DocumentSection.document_id == document_id,
                DocumentSection.status == "completed",
            )
            .order_by(DocumentSection.section_index.asc())
        )
        sections = safe_scalars_all(
            sections_result, f"claim_check_sections_doc_{document_id}"
        )
        sources_result = await db.execute(
            select(DocumentSource).where(DocumentSource.document_id == document_id)
        )
        sources = safe_scalars_all(
            sources_result, f"claim_check_sources_doc_{document_id}"
        )

        if not sections:
            return

        await send_progress(
            user_id,
            {
                "stage": "verifying_claims",
                "progress": 98,
                "message": "Checking that cited sources support the claims...",
                "document_id": document_id,
            },
        )

        verifier = ClaimVerifier(
            ai_service_factory(db),
            batch_size=config.CLAIM_VERIFICATION_BATCH_SIZE,
            abstract_max_chars=config.CLAIM_ABSTRACT_MAX_CHARS,
        )
        budget_remaining = max(0, config.CLAIM_VERIFICATION_MAX_CHECKS)
        total_claims = 0
        total_checked = 0
        total_counts: dict[str, int] = {}

        for section in sections:
            claims = verifier.extract_claims(section.content or "", sources)
            if not claims:
                continue

            verdicts, llm_used = await verifier.verify_claims(claims, budget_remaining)
            budget_remaining -= llm_used

            summary = summarize_verdicts(verdicts)
            # Assign a NEW dict: plain JSON columns don't track mutations
            section.claim_verification = summary

            total_claims += summary["total"]
            total_checked += summary["checked"]
            for verdict_name, count in summary["counts"].items():
                total_counts[verdict_name] = total_counts.get(verdict_name, 0) + count

            if config.PROVENANCE_LEDGER_ENABLED:
                unsupported_claims = [
                    {
                        "sentence": v.sentence[:300],
                        "citation": v.citation_text,
                        "source_title": v.source_title,
                        "explanation": v.explanation[:300],
                    }
                    for v in verdicts
                    if v.verdict == "unsupported"
                ]
                await record_event(
                    db,
                    document_id,
                    stage="verification",
                    event_type="claims_verified",
                    payload={
                        "section_index": section.section_index,
                        "total": summary["total"],
                        "checked": summary["checked"],
                        "counts": summary["counts"],
                        "unsupported": unsupported_claims[:10],
                    },
                )

        await db.commit()  # persist claim_verification on sections

        if total_claims and config.PROVENANCE_LEDGER_ENABLED:
            await record_event(
                db,
                document_id,
                stage="verification",
                event_type="claim_check_summary",
                payload={
                    "total_claims": total_claims,
                    "checked": total_checked,
                    "counts": total_counts,
                    "budget": config.CLAIM_VERIFICATION_MAX_CHECKS,
                    "budget_exhausted": budget_remaining <= 0,
                },
            )

        logger.info(
            f"✅ Claim faithfulness audit for document {document_id}: "
            f"{total_claims} claim(s), {total_checked} LLM-checked, "
            f"counts={total_counts}"
        )
    except Exception as e:
        # ⚠️ Advisory pass: any internal error degrades gracefully
        logger.error(
            f"Claim verification stage failed for document {document_id}: {e}",
            exc_info=True,
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.warning(
                f"⚠️ Rollback after claim verification failure: {rollback_error}"
            )
        if config.PROVENANCE_LEDGER_ENABLED:
            await record_event(
                db,
                document_id,
                stage="verification",
                event_type="claim_verification_error",
                payload={"error": str(e)[:500]},
            )
