"""
Claim verification stage (Academic Quality Engine).

Advisory claim-faithfulness audit: checks that cited sources actually
support the sentences citing them. Advisory by default; when
CLAIM_VERIFICATION_BLOCKING is set, unsupported cited claims block export.

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

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CitationIntegrityError
from app.models.document import AIGenerationJob, Document, DocumentSection
from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.claim_verifier import (
    TECHNICAL_UNCERTAIN_REASONS,
    CitedClaim,
    ClaimVerdict,
    ClaimVerifier,
    summarize_verdicts,
)
from app.services.db_helpers import safe_scalars_all
from app.services.provenance_service import record_event

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

SendProgress = Callable[[int, dict[str, Any]], Awaitable[None]]


async def verify_section_claims(
    verifier: ClaimVerifier,
    *,
    content: str,
    canonical_marker_content: str | None = None,
    sources: list[Any],
    budget_remaining: int,
    citation_style: CitationStyle,
    claims: list[CitedClaim] | None = None,
) -> tuple[dict[str, Any], list[ClaimVerdict], int]:
    """Check the exact candidate text that may be persisted for one section."""
    if claims is None:
        claims = verifier.extract_claims(
            canonical_marker_content
            if canonical_marker_content is not None
            else content,
            sources,
            citation_style=citation_style,
        )
    verdicts, llm_used = await verifier.verify_claims(claims, budget_remaining)
    return summarize_verdicts(verdicts), verdicts, llm_used


def technical_uncertain_claims(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Unchecked infrastructure/budget outcomes are not semantic uncertainty."""
    return [
        claim
        for claim in (summary or {}).get("claims") or []
        if claim.get("verdict") == "uncertain"
        and claim.get("explanation") in TECHNICAL_UNCERTAIN_REASONS
    ]


def _claims_for_provenance(
    summary: dict[str, Any], verdict_name: str
) -> list[dict[str, Any]]:
    return [
        {
            "sentence": str(claim.get("sentence") or "")[:300],
            "citation": str(claim.get("citation") or ""),
            "source_title": claim.get("source_title"),
            "explanation": str(claim.get("explanation") or "")[:300],
        }
        for claim in summary.get("claims") or []
        if claim.get("verdict") == verdict_name
    ]


async def run_claim_verification_stage(
    db: AsyncSession,
    document_id: int,
    user_id: int,
    *,
    config: Settings,
    ai_service_factory: Callable[[AsyncSession], Any],
    send_progress: SendProgress,
    job_id: int | None = None,
) -> None:
    """Aggregate already accepted per-section verdicts without a second LLM pass."""
    del ai_service_factory  # kept in the injected API for compatibility

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

        total_claims = 0
        total_checked = 0
        total_counts: dict[str, int] = {}
        budget_exhausted = False
        total_incomplete = 0
        missing_sections: list[int] = []
        reserved_checks: int | None = None
        if job_id is not None:
            reserved_checks = (
                await db.execute(
                    select(AIGenerationJob.claim_checks_used).where(
                        AIGenerationJob.id == job_id,
                        AIGenerationJob.document_id == document_id,
                    )
                )
            ).scalar_one_or_none()

        for section in sections:
            summary = section.claim_verification
            if not isinstance(summary, dict):
                missing_sections.append(int(section.section_index))
                continue

            total_claims += int(summary.get("total") or 0)
            total_checked += int(summary.get("checked") or 0)
            for verdict_name, count in (summary.get("counts") or {}).items():
                total_counts[verdict_name] = total_counts.get(verdict_name, 0) + count
            budget_exhausted = budget_exhausted or any(
                claim.get("explanation") == "Per-document claim check budget exhausted"
                for claim in summary.get("claims") or []
            )
            total_incomplete += len(technical_uncertain_claims(summary))

            if config.PROVENANCE_LEDGER_ENABLED:
                await record_event(
                    db,
                    document_id,
                    stage="verification",
                    event_type="claims_verified",
                    payload={
                        "section_index": section.section_index,
                        "total": int(summary.get("total") or 0),
                        "checked": int(summary.get("checked") or 0),
                        "counts": dict(summary.get("counts") or {}),
                        "unsupported": _claims_for_provenance(summary, "unsupported"),
                        "uncertain": _claims_for_provenance(summary, "uncertain"),
                    },
                )

        if missing_sections:
            raise RuntimeError(
                "Missing accepted claim evidence for completed section(s): "
                + ", ".join(str(index) for index in missing_sections)
            )

        if config.PROVENANCE_LEDGER_ENABLED:
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
                    "budget_exhausted": budget_exhausted,
                    "reserved_checks": (
                        int(reserved_checks)
                        if reserved_checks is not None
                        else total_checked
                    ),
                    "incomplete": total_incomplete,
                },
            )

        logger.info(
            f"✅ Claim faithfulness evidence aggregated for document {document_id}: "
            f"{total_claims} claim(s), {total_checked} LLM-checked, "
            f"counts={total_counts}"
        )

        unsupported = total_counts.get("unsupported", 0)
        if config.CLAIM_VERIFICATION_BLOCKING and (
            unsupported > 0 or total_incomplete > 0
        ):
            detail = (
                f"{unsupported} cited claim(s) are not supported and "
                f"{total_incomplete} cited claim(s) were not technically checked "
                "(claim faithfulness gate)."
            )
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status="failed_quality")
            )
            await db.commit()
            if config.PROVENANCE_LEDGER_ENABLED:
                await record_event(
                    db,
                    document_id,
                    stage="verification",
                    event_type="claim_integrity_gate_failed",
                    payload={
                        "unsupported": unsupported,
                        "incomplete": total_incomplete,
                        "counts": total_counts,
                    },
                )
            raise CitationIntegrityError(detail=detail)
    except Exception as e:
        if isinstance(e, CitationIntegrityError):
            raise
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
        if config.CLAIM_VERIFICATION_BLOCKING:
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status="failed_quality")
            )
            await db.commit()
            raise CitationIntegrityError(
                detail="Claim verification evidence could not be completed safely"
            ) from e
