"""
Source verification stage (Academic Quality Engine).

Persists cited sources, runs batch citation verification between section
assembly and export, and enforces the citation integrity gate
(strict / mark_only).

Patch-sensitive collaborators (settings, CitationVerifier, websocket
progress) are injected by the caller — see the thin wrappers in
app.services.background_jobs, which pass its module globals at call time
so existing monkeypatches keep working. This module must NOT import the
settings instance or the websocket manager directly.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CitationIntegrityError
from app.models.document import Document, DocumentProvenance, DocumentSource
from app.services.citation_verifier import (
    FUZZY_MATCH_THRESHOLD,
    SourceInput,
    VerificationResult,
    VerificationStatus,
    normalize_doi,
    normalize_title,
)
from app.services.db_helpers import safe_scalars_all
from app.services.provenance_service import record_event

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.ai_pipeline.source_pack import SourcePack
    from app.services.citation_verifier import CitationVerifier

logger = logging.getLogger(__name__)

SendProgress = Callable[[int, dict[str, Any]], Awaitable[None]]


def map_verification_status(result: VerificationResult) -> str:
    """
    Map a CitationVerifier result to DocumentSource.verification_status.

    verified with low title similarity (< FUZZY_MATCH_THRESHOLD; only possible
    for DOI/arXiv identifier hits) -> 'mismatched'; not_found -> 'not_found';
    unresolvable (provider outage / insufficient metadata) -> 'failed'.
    """
    if result.status == VerificationStatus.VERIFIED:
        if (
            result.match_score is not None
            and result.match_score < FUZZY_MATCH_THRESHOLD
        ):
            return "mismatched"
        return "verified"
    if result.status == VerificationStatus.NOT_FOUND:
        return "not_found"
    return "failed"  # VerificationStatus.UNRESOLVABLE


async def persist_cited_sources(
    db: AsyncSession,
    document_id: int,
    section_id: int | None,
    cited_sources: list[dict[str, Any]],
) -> None:
    """
    Persist cited sources for a section as DocumentSource rows ('unverified').

    Deduplicates against existing rows by normalized DOI, and by
    (normalized title, year) for DOI-less sources, so the partial unique
    index uq_document_sources_document_id_doi is never violated.

    ⚠️ Non-critical: never raises. Failures are logged and rolled back so the
    shared session stays usable for the rest of the pipeline.
    """
    if not cited_sources:
        return

    try:
        existing_result = await db.execute(
            select(DocumentSource).where(DocumentSource.document_id == document_id)
        )
        existing_rows = safe_scalars_all(
            existing_result, f"existing_sources_doc_{document_id}"
        )
        seen_dois = {row.doi for row in existing_rows if row.doi}
        seen_title_year = {
            (normalize_title(row.title), row.year)
            for row in existing_rows
            if not row.doi
        }

        added = 0
        for source in cited_sources:
            title = (source.get("title") or "").strip()
            if not title:
                continue

            norm_doi = normalize_doi(source.get("doi"))
            if norm_doi:
                if norm_doi in seen_dois:
                    continue
                seen_dois.add(norm_doi)
            else:
                title_year_key = (normalize_title(title), source.get("year"))
                if title_year_key in seen_title_year:
                    continue
                seen_title_year.add(title_year_key)

            db.add(
                DocumentSource(
                    document_id=document_id,
                    section_id=section_id,
                    title=title[:1000],
                    authors=list(source.get("authors") or []),
                    year=source.get("year"),
                    abstract=source.get("abstract"),
                    paper_id=source.get("paper_id"),
                    venue=(source.get("venue") or "")[:500] or None,
                    citation_count=source.get("citation_count"),
                    url=(source.get("url") or "")[:1000] or None,
                    doi=norm_doi,
                    verification_status="unverified",
                )
            )
            added += 1

        if added:
            await db.commit()
            logger.info(
                f"✅ Persisted {added} cited source(s) for document {document_id} "
                f"(section {section_id})"
            )
    except Exception as e:
        # ⚠️ Non-critical: source persistence must never break generation
        logger.warning(
            f"⚠️ Failed to persist cited sources for document {document_id}: {e}"
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.warning(
                f"⚠️ Rollback after cited-source persistence failed: {rollback_error}"
            )


async def persist_source_pack(
    db: AsyncSession,
    document_id: int,
    pack: SourcePack,
) -> None:
    """
    Persist the upfront topic-locked source pack as DocumentSource rows.

    Idempotent upsert: existing rows (matched by normalized DOI, or by
    (normalized title, year) for DOI-less sources) are updated in place with
    citation_key / on_topic_score / is_in_upfront_pack; new sources are
    inserted. Previous pack membership for the document is reset first so
    citation keys stay unique per document and stale members drop out of the
    pack on rebuild.

    ⚠️ Non-critical: never raises. Failures are logged and rolled back so the
    shared session stays usable for the rest of the pipeline.
    """
    if pack is None or not getattr(pack, "sources", None):
        return

    try:
        # Reset prior pack membership so re-runs never collide on citation_key.
        await db.execute(
            update(DocumentSource)
            .where(DocumentSource.document_id == document_id)
            .values(is_in_upfront_pack=False, citation_key=None)
        )

        existing_result = await db.execute(
            select(DocumentSource).where(DocumentSource.document_id == document_id)
        )
        existing_rows = safe_scalars_all(
            existing_result, f"pack_sources_doc_{document_id}"
        )
        by_doi = {row.doi: row for row in existing_rows if row.doi}
        by_title_year = {
            (normalize_title(row.title), row.year): row
            for row in existing_rows
            if not row.doi
        }

        inserted = updated = 0
        for packed in pack.sources:
            src = packed.source
            title = (src.title or "").strip()
            if not title:
                continue

            norm_doi = normalize_doi(src.doi)
            if norm_doi:
                existing = by_doi.get(norm_doi)
            else:
                existing = by_title_year.get((normalize_title(title), src.year))

            if existing is not None:
                existing.citation_key = packed.citation_key
                existing.on_topic_score = packed.on_topic_score
                existing.is_in_upfront_pack = True
                # Backfill metadata that a cited-only row may have been missing.
                if not existing.abstract and src.abstract:
                    existing.abstract = src.abstract
                if not existing.venue and src.venue:
                    existing.venue = (src.venue or "")[:500] or None
                updated += 1
            else:
                row = DocumentSource(
                    document_id=document_id,
                    section_id=None,
                    title=title[:1000],
                    authors=list(src.authors or []),
                    year=src.year,
                    abstract=src.abstract,
                    paper_id=src.paper_id,
                    venue=(src.venue or "")[:500] or None,
                    citation_count=src.citation_count,
                    url=(src.url or "")[:1000] or None,
                    doi=norm_doi,
                    verification_status="unverified",
                    citation_key=packed.citation_key,
                    on_topic_score=packed.on_topic_score,
                    is_in_upfront_pack=True,
                )
                db.add(row)
                # Keep local maps in sync to avoid duplicate inserts within the pack.
                if norm_doi:
                    by_doi[norm_doi] = row
                else:
                    by_title_year[(normalize_title(title), src.year)] = row
                inserted += 1

        await db.commit()
        logger.info(
            f"✅ Persisted source pack for document {document_id}: "
            f"{inserted} inserted, {updated} updated"
        )
    except Exception as e:
        # ⚠️ Non-critical: pack persistence must never break generation.
        logger.warning(
            f"⚠️ Failed to persist source pack for document {document_id}: {e}"
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.warning(
                f"⚠️ Rollback after source-pack persistence failed: {rollback_error}"
            )


async def load_source_pack(
    db: AsyncSession,
    document_id: int,
) -> SourcePack | None:
    """
    Reconstruct the persisted upfront source pack (is_in_upfront_pack=True rows).

    Returns None when the document has no persisted pack, so callers can rebuild
    on resume rather than proceeding without grounding.

    ⚠️ Non-critical: never raises; returns None on error.
    """
    # Local imports avoid an import cycle and keep this module import-light.
    from app.services.ai_pipeline.rag_retriever import SourceDoc
    from app.services.ai_pipeline.source_pack import PackedSource, SourcePack

    try:
        doc = await db.get(Document, document_id)
        topic = doc.topic if doc is not None else ""

        result = await db.execute(
            select(DocumentSource).where(
                DocumentSource.document_id == document_id,
                DocumentSource.is_in_upfront_pack.is_(True),
            )
        )
        rows = safe_scalars_all(result, f"load_pack_doc_{document_id}")
        if not rows:
            return None

        packed = [
            PackedSource(
                source=SourceDoc(
                    title=row.title,
                    authors=list(row.authors or []),
                    year=row.year,
                    abstract=row.abstract,
                    paper_id=row.paper_id,
                    venue=row.venue,
                    citation_count=row.citation_count,
                    url=row.url,
                    doi=row.doi,
                ),
                citation_key=row.citation_key or "",
                on_topic_score=(
                    row.on_topic_score if row.on_topic_score is not None else 0.0
                ),
            )
            for row in rows
        ]
        packed.sort(key=lambda p: p.on_topic_score, reverse=True)
        return SourcePack(document_id=document_id, topic=topic, sources=packed)
    except Exception as e:
        logger.warning(f"⚠️ Failed to load source pack for document {document_id}: {e}")
        return None


async def run_citation_verification_stage(
    db: AsyncSession,
    document_id: int,
    user_id: int,
    *,
    config: Settings,
    verifier_factory: Callable[[], CitationVerifier],
    send_progress: SendProgress,
) -> None:
    """
    Verify persisted cited sources in ONE batch (between assembly and export).

    Re-verifies ALL DocumentSource rows of the document (not only
    'unverified') so transient 'failed' rows self-heal on re-runs; the
    verifier's Redis cache makes repeats cheap. Updates verification_status
    + canonical_metadata, writes a DocumentProvenance summary event, then
    enforces the integrity gate:
    - strict: any not_found source -> Document.status='failed_quality'
      + CitationIntegrityError (blocks export)
    - mark_only: write integrity report and continue

    Unexpected internal errors degrade gracefully (logged + provenance
    'verification_error' event, gate skipped = fail-open). The ONLY exception
    this function raises is CitationIntegrityError.
    """
    summary: dict[str, Any] | None = None

    try:
        sources_result = await db.execute(
            select(DocumentSource).where(DocumentSource.document_id == document_id)
        )
        all_sources = safe_scalars_all(
            sources_result, f"verification_sources_doc_{document_id}"
        )

        if not all_sources:
            logger.info(
                f"Citation verification: no cited sources persisted "
                f"for document {document_id}"
            )
            db.add(
                DocumentProvenance(
                    document_id=document_id,
                    stage="verification",
                    event_type="verification_summary",
                    payload={
                        "total": 0,
                        "counts": {},
                        "policy": config.CITATION_VERIFICATION_POLICY,
                        "sources": [],
                        "providers": [],
                    },
                )
            )
            await db.commit()
            if config.PROVENANCE_LEDGER_ENABLED:
                await record_event(
                    db,
                    document_id,
                    stage="verification",
                    event_type="citation_gate",
                    payload={
                        "passed": True,
                        "status": "passed",
                        "policy": config.CITATION_VERIFICATION_POLICY,
                        "total": 0,
                        "counts": {},
                    },
                )
            return

        await send_progress(
            user_id,
            {
                "stage": "verifying_citations",
                "progress": 96,
                "message": f"Verifying {len(all_sources)} cited source(s)...",
                "document_id": document_id,
            },
        )

        # One verifier instance per call: the pipeline runs in its own event
        # loop and CitationVerifier binds asyncio primitives/Redis to it.
        verifier = verifier_factory()
        inputs = [
            SourceInput(
                title=source.title or "",
                authors=list(source.authors or []),
                year=source.year,
                doi=source.doi,
            )
            for source in all_sources
        ]
        # Order-preserving and never raises (contract of verify_sources)
        results = await verifier.verify_sources(inputs)

        status_counts: dict[str, int] = {}
        not_found_titles: list[str] = []
        source_records: list[dict[str, Any]] = []
        providers_used: set[str] = set()
        for source, result in zip(all_sources, results, strict=True):
            mapped_status = map_verification_status(result)
            source.verification_status = mapped_status
            # Assign a NEW dict: plain JSON columns don't track mutations
            source.canonical_metadata = result.to_dict()
            status_counts[mapped_status] = status_counts.get(mapped_status, 0) + 1
            if mapped_status == "not_found":
                not_found_titles.append(source.title)
            # Per-source record for the frontend "sources certificate"
            source_records.append(
                {
                    "title": (source.title or "")[:300],
                    "authors": list(source.authors or [])[:5],
                    "year": source.year,
                    "doi": source.doi,
                    "status": mapped_status,
                }
            )
            if result.provider:
                providers_used.add(result.provider)

        db.add(
            DocumentProvenance(
                document_id=document_id,
                stage="verification",
                event_type="verification_summary",
                payload={
                    "total": len(all_sources),
                    "counts": status_counts,
                    "policy": config.CITATION_VERIFICATION_POLICY,
                    "not_found_titles": not_found_titles[:20],
                    "sources": source_records[:100],
                    "providers": sorted(providers_used),
                },
            )
        )
        await db.commit()

        logger.info(
            f"✅ Citation verification for document {document_id}: "
            f"{len(all_sources)} source(s), counts={status_counts}"
        )

        await send_progress(
            user_id,
            {
                "stage": "citations_verified",
                "progress": 97,
                "message": "Citation verification finished",
                "document_id": document_id,
                "counts": status_counts,
            },
        )

        summary = {
            "counts": status_counts,
            "not_found_titles": not_found_titles,
        }
    except Exception as e:
        # ⚠️ Fail-open: infrastructure errors in OUR stage must not block the
        # user's document. Only confirmed not_found sources may block (below).
        logger.error(
            f"Citation verification stage failed for document {document_id}: {e}",
            exc_info=True,
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.warning(
                f"⚠️ Rollback after verification stage failure: {rollback_error}"
            )
        try:
            db.add(
                DocumentProvenance(
                    document_id=document_id,
                    stage="verification",
                    event_type="verification_error",
                    payload={"error": str(e)[:500]},
                )
            )
            await db.commit()
        except Exception:
            logger.warning(
                f"⚠️ Failed to record verification_error event "
                f"for document {document_id}"
            )
        return

    # Integrity gate — deliberately OUTSIDE the try above so it can never be
    # swallowed by the stage's graceful-degradation handler.
    not_found_count = summary["counts"].get("not_found", 0)
    if not_found_count == 0:
        # "0 not_found" is only a pass if something was actually verified.
        # When every provider errored, all sources land in "failed"
        # (UNRESOLVABLE) and nothing was checked — that is an unchecked
        # gate, not a green one (same fail-open the quality gates had).
        failed_count = summary["counts"].get("failed", 0)
        total_sources = sum(summary["counts"].values())
        nothing_verified = total_sources > 0 and failed_count == total_sources
        if config.PROVENANCE_LEDGER_ENABLED:
            await record_event(
                db,
                document_id,
                stage="verification",
                event_type="citation_gate",
                payload={
                    "passed": not nothing_verified,
                    "status": "unchecked" if nothing_verified else "passed",
                    "policy": config.CITATION_VERIFICATION_POLICY,
                    "counts": summary["counts"],
                },
            )
        return

    if config.CITATION_VERIFICATION_POLICY == "strict":
        titles_preview = "; ".join(summary["not_found_titles"][:5])
        detail = (
            f"Citation verification failed: {not_found_count} cited source(s) "
            f"could not be found in any bibliographic database "
            f"(Crossref, OpenAlex, Semantic Scholar, arXiv): {titles_preview}"
        )
        # Best-effort persistence of the failure state; the raise below is
        # unconditional even if these writes fail (export still blocked).
        try:
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status="failed_quality")
            )
            db.add(
                DocumentProvenance(
                    document_id=document_id,
                    stage="verification",
                    event_type="integrity_gate_failed",
                    payload={
                        "policy": "strict",
                        "not_found_count": not_found_count,
                        "not_found_titles": summary["not_found_titles"][:20],
                    },
                )
            )
            await db.commit()
        except Exception as gate_error:
            logger.error(
                f"Failed to persist integrity gate state "
                f"for document {document_id}: {gate_error}"
            )
            try:
                await db.rollback()
            except Exception:
                pass
        if config.PROVENANCE_LEDGER_ENABLED:
            await record_event(
                db,
                document_id,
                stage="verification",
                event_type="citation_gate",
                payload={
                    "passed": False,
                    "status": "failed",
                    "policy": "strict",
                    "counts": summary["counts"],
                    "not_found_count": not_found_count,
                    "not_found_titles": summary["not_found_titles"][:20],
                },
            )
        await send_progress(
            user_id,
            {
                "stage": "citation_gate_failed",
                "progress": 97,
                "message": detail,
                "document_id": document_id,
            },
        )
        raise CitationIntegrityError(detail=detail)

    # mark_only: record the report and let the pipeline continue
    try:
        db.add(
            DocumentProvenance(
                document_id=document_id,
                stage="verification",
                event_type="integrity_report",
                payload={
                    "policy": "mark_only",
                    "not_found_count": not_found_count,
                    "not_found_titles": summary["not_found_titles"][:20],
                },
            )
        )
        await db.commit()
        logger.warning(
            f"⚠️ Citation integrity report for document {document_id}: "
            f"{not_found_count} not_found source(s) (policy=mark_only, continuing)"
        )
    except Exception as report_error:
        logger.warning(
            f"⚠️ Failed to record integrity report "
            f"for document {document_id}: {report_error}"
        )
        try:
            await db.rollback()
        except Exception:
            pass
    if config.PROVENANCE_LEDGER_ENABLED:
        await record_event(
            db,
            document_id,
            stage="verification",
            event_type="citation_gate",
            payload={
                # mark_only did not block the pipeline, but not_found sources
                # exist — "warning" so release gates and the UI never show
                # this as a clean pass.
                "passed": True,
                "status": "warning",
                "policy": "mark_only",
                "counts": summary["counts"],
                "not_found_count": not_found_count,
                "not_found_titles": summary["not_found_titles"][:20],
            },
        )
