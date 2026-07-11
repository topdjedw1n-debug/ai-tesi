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
from app.models.document import (
    Document,
    DocumentProvenance,
    DocumentSection,
    DocumentSource,
)
from app.services.ai_pipeline.source_identity import sources_equivalent
from app.services.ai_pipeline.source_pack import SourcePack
from app.services.citation_verifier import (
    FUZZY_MATCH_THRESHOLD,
    SourceInput,
    VerificationResult,
    VerificationStatus,
    normalize_doi,
)
from app.services.db_helpers import safe_scalars_all
from app.services.provenance_service import record_event

if TYPE_CHECKING:
    from app.core.config import Settings
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

    Deduplicates against existing rows using the shared source-identity rule:
    uploaded-file identity, normalized DOI, or title/year/author evidence.

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
        added = 0
        for source in cited_sources:
            title = (source.get("title") or "").strip()
            if not title:
                continue

            if any(sources_equivalent(row, source) for row in existing_rows):
                continue
            norm_doi = normalize_doi(source.get("doi"))

            row = DocumentSource(
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
                retrieval_provider=source.get("provider"),
                source_type=source.get("source_type"),
                verification_status="unverified",
            )
            db.add(row)
            existing_rows.append(row)
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

    Idempotent upsert: existing rows matched by the shared source-identity
    rule are updated in place with
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
        inserted, updated = await apply_source_pack_rows(db, document_id, pack)
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


async def apply_source_pack_rows(
    db: AsyncSession,
    document_id: int,
    pack: SourcePack,
) -> tuple[int, int]:
    """Apply a complete pack without committing; raises on any inconsistency.

    This is the transactional core used by durable job fencing.  One existing
    database row can satisfy at most one incoming source, preventing a DOI-less
    title/year collision from silently overwriting another citation key.
    """
    existing_result = await db.execute(
        select(DocumentSource).where(DocumentSource.document_id == document_id)
    )
    existing_rows = safe_scalars_all(existing_result, f"pack_sources_doc_{document_id}")
    for row in existing_rows:
        row.is_in_upfront_pack = False
        row.citation_key = None

    claimed_rows: set[int] = set()
    incoming: list[Any] = []
    inserted = updated = 0

    for packed in pack.canonical_sources():
        src = packed.source
        title = (src.title or "").strip()
        if not title:
            raise ValueError("Source pack contains a source without a title")
        norm_doi = normalize_doi(src.doi)
        for previous in incoming:
            if sources_equivalent(previous, src):
                raise ValueError(f"Source pack contains duplicate publication: {title}")
            if norm_doi and normalize_doi(previous.doi) == norm_doi:
                raise ValueError(
                    "Source pack assigns the same DOI to conflicting source "
                    f"identities: {norm_doi}"
                )
        incoming.append(src)

        candidates = [row for row in existing_rows if id(row) not in claimed_rows]
        existing = next(
            (
                row
                for row in candidates
                if norm_doi and normalize_doi(row.doi) == norm_doi
            ),
            None,
        )
        if existing is not None and not sources_equivalent(existing, src):
            raise ValueError(
                "Persisted source and incoming pack source share DOI but have "
                f"conflicting identities: {norm_doi}"
            )
        if existing is None:
            existing = next(
                (row for row in candidates if sources_equivalent(row, src)),
                None,
            )

        values = {
            "title": title[:1000],
            "authors": list(src.authors or []),
            "year": src.year,
            "abstract": src.abstract,
            "paper_id": src.paper_id,
            "venue": (src.venue or "")[:500] or None,
            "citation_count": src.citation_count,
            "url": (src.url or "")[:1000] or None,
            "doi": norm_doi,
            "retrieval_provider": getattr(src, "provider", None),
            "source_type": getattr(src, "source_type", None),
            "verification_status": getattr(src, "verification_status", "unverified"),
            "canonical_metadata": getattr(src, "canonical_metadata", None),
            "citation_key": packed.citation_key,
            "on_topic_score": packed.on_topic_score,
            "is_in_upfront_pack": True,
        }
        if existing is None:
            row = DocumentSource(document_id=document_id, section_id=None, **values)
            db.add(row)
            existing_rows.append(row)
            inserted += 1
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            claimed_rows.add(id(existing))
            updated += 1

    await db.flush()
    return inserted, updated


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
            select(DocumentSource)
            .where(
                DocumentSource.document_id == document_id,
                DocumentSource.is_in_upfront_pack.is_(True),
            )
            .order_by(
                DocumentSource.on_topic_score.desc(),
                DocumentSource.citation_key.asc(),
                DocumentSource.id.asc(),
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
                    provider=row.retrieval_provider,
                    source_type=row.source_type,
                    verification_status=row.verification_status or "unverified",
                    canonical_metadata=row.canonical_metadata,
                ),
                citation_key=row.citation_key or "",
                on_topic_score=(
                    row.on_topic_score if row.on_topic_score is not None else 0.0
                ),
            )
            for row in rows
        ]
        packed.sort(key=SourcePack._canonical_source_sort_key)
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

    On the grounded path, re-verifies exactly the canonical pack keys used by
    completed sections. The legacy path re-verifies section-linked sources.
    Transient 'failed' rows can therefore self-heal on re-runs, while the
    verifier's Redis cache makes repeats cheap. Updates verification_status +
    canonical_metadata, writes a DocumentProvenance summary event, then
    enforces the integrity gate:
    - strict: no persisted sources, any not_found source, or any mismatched
      source -> Document.status='failed_quality' + CitationIntegrityError
      (blocks export)
    - mark_only: record a visible warning and continue

    Unexpected internal errors are recorded.  Under strict policy they fail
    closed because an unavailable verifier is not evidence that citations are
    valid; under mark_only they remain a visible warning.
    """
    summary: dict[str, Any] | None = None

    try:
        used_keys_result = await db.execute(
            select(DocumentSection.pack_keys_used).where(
                DocumentSection.document_id == document_id
            )
        )
        used_pack_keys = {
            str(key)
            for keys in used_keys_result.scalars().all()
            for key in (keys or [])
            if key
        }
        if used_pack_keys:
            # The grounded path has a stronger invariant than the legacy
            # section-linked path: every canonical key used by the writer must
            # resolve to exactly one persisted pack row.  Selecting with OR
            # hid missing keys by inflating the batch with unrelated rows.
            cited_filter = DocumentSource.citation_key.in_(used_pack_keys)
        else:
            cited_filter = DocumentSource.section_id.is_not(None)
        sources_result = await db.execute(
            select(DocumentSource).where(
                DocumentSource.document_id == document_id,
                cited_filter,
            )
        )
        all_sources = safe_scalars_all(
            sources_result, f"verification_sources_doc_{document_id}"
        )
        present_used_keys = {
            str(source.citation_key) for source in all_sources if source.citation_key
        }
        missing_used_keys = sorted(used_pack_keys - present_used_keys)

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
            if used_pack_keys and config.PROVENANCE_LEDGER_ENABLED:
                await record_event(
                    db,
                    document_id,
                    stage="verification",
                    event_type="citation_closure",
                    payload={
                        "passed": False,
                        "used_keys": sorted(used_pack_keys),
                        "verified_keys": [],
                        "missing_keys": sorted(used_pack_keys),
                        "unverified_keys": sorted(used_pack_keys),
                        "used_total": len(used_pack_keys),
                        "verified_total": 0,
                    },
                )
            is_strict = config.CITATION_VERIFICATION_POLICY == "strict"
            gate_payload: dict[str, Any] = {
                "passed": False,
                "status": "failed" if is_strict else "warning",
                "policy": config.CITATION_VERIFICATION_POLICY,
                "total": 0,
                "counts": {},
            }
            if is_strict:
                try:
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed_quality")
                    )
                    await db.commit()
                except Exception as gate_error:
                    logger.error(
                        f"Failed to persist empty citation gate state for "
                        f"document {document_id}: {gate_error}"
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass
            if config.PROVENANCE_LEDGER_ENABLED:
                try:
                    await record_event(
                        db,
                        document_id,
                        stage="verification",
                        event_type="citation_gate",
                        payload=gate_payload,
                    )
                except Exception as ledger_error:
                    logger.error(
                        f"Failed to record empty citation gate for document "
                        f"{document_id}: {ledger_error}"
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass
            if is_strict:
                detail = (
                    "Citation verification failed: no cited sources were "
                    "persisted for this document"
                )
                try:
                    await send_progress(
                        user_id,
                        {
                            "stage": "citation_gate_failed",
                            "progress": 97,
                            "message": detail,
                            "document_id": document_id,
                        },
                    )
                except Exception as progress_error:
                    logger.warning(
                        f"Failed to send empty citation gate progress for "
                        f"document {document_id}: {progress_error}"
                    )
                raise CitationIntegrityError(detail=detail)
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

        # Manager-uploaded PDFs are their own existence proof: resolving a
        # course reader or book chapter against Crossref/OpenAlex would
        # honestly return NOT_FOUND and strict policy would kill the run for
        # having exactly the sources the professor mandated. Claim-support
        # against their page text is a separate stage; THIS stage only asks
        # "does the source exist" — the file answers that.
        uploaded_sources = [
            source
            for source in all_sources
            if str(source.paper_id or "").startswith("uploaded:")
        ]
        external_sources = [
            source
            for source in all_sources
            if not str(source.paper_id or "").startswith("uploaded:")
        ]

        status_counts: dict[str, int] = {}
        not_found_titles: list[str] = []
        mismatched_titles: list[str] = []
        failed_titles: list[str] = []
        source_records: list[dict[str, Any]] = []
        providers_used: set[str] = set()

        for source in uploaded_sources:
            source.verification_status = "verified"
            source.canonical_metadata = {
                "status": "verified",
                "provider": "uploaded_file",
                "reason": "manager-uploaded source PDF",
            }
            status_counts["verified"] = status_counts.get("verified", 0) + 1
            source_records.append(
                {
                    "title": (source.title or "")[:300],
                    "authors": list(source.authors or [])[:5],
                    "year": source.year,
                    "doi": source.doi,
                    "status": "verified",
                    "provider": "uploaded_file",
                }
            )
        if uploaded_sources:
            providers_used.add("uploaded_file")

        results: list[Any] = []
        if external_sources:
            # One verifier instance per call: the pipeline runs in its own
            # event loop and CitationVerifier binds asyncio primitives/Redis
            # to it.
            verifier = verifier_factory()
            inputs = [
                SourceInput(
                    title=source.title or "",
                    authors=list(source.authors or []),
                    year=source.year,
                    doi=source.doi,
                )
                for source in external_sources
            ]
            # Order-preserving and never raises (contract of verify_sources)
            results = await verifier.verify_sources(inputs)

        for source, result in zip(external_sources, results, strict=True):
            mapped_status = map_verification_status(result)
            source.verification_status = mapped_status
            # Assign a NEW dict: plain JSON columns don't track mutations
            source.canonical_metadata = result.to_dict()
            status_counts[mapped_status] = status_counts.get(mapped_status, 0) + 1
            if mapped_status == "not_found":
                not_found_titles.append(source.title)
            elif mapped_status == "mismatched":
                mismatched_titles.append(source.title)
            elif mapped_status == "failed":
                failed_titles.append(source.title)
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

        verified_used_keys = {
            str(source.citation_key)
            for source in all_sources
            if source.citation_key and source.verification_status == "verified"
        }
        unverified_used_keys = sorted(used_pack_keys - verified_used_keys)
        closure_payload = {
            "passed": not missing_used_keys and not unverified_used_keys,
            "used_keys": sorted(used_pack_keys),
            "verified_keys": sorted(verified_used_keys),
            "missing_keys": missing_used_keys,
            "unverified_keys": unverified_used_keys,
            "used_total": len(used_pack_keys),
            "verified_total": len(verified_used_keys),
        }
        if config.PROVENANCE_LEDGER_ENABLED:
            await record_event(
                db,
                document_id,
                stage="verification",
                event_type="citation_closure",
                payload=closure_payload,
            )

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
            "mismatched_titles": mismatched_titles,
            "failed_titles": failed_titles,
            "closure": closure_payload,
        }
    except CitationIntegrityError:
        raise
    except Exception as e:
        # Strict mode is deliberately fail-closed: an interrupted verifier is
        # an unchecked gate, never a green one. mark_only remains non-blocking.
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
        if config.CITATION_VERIFICATION_POLICY == "strict":
            try:
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(status="failed_quality")
                )
                await db.commit()
            except Exception:
                try:
                    await db.rollback()
                except Exception:
                    pass
            raise CitationIntegrityError(
                detail="Citation verification could not be completed safely"
            ) from e
        return

    # Integrity gate — deliberately OUTSIDE the try above so it can never be
    # swallowed by the stage's graceful-degradation handler.
    not_found_count = summary["counts"].get("not_found", 0)
    mismatched_count = summary["counts"].get("mismatched", 0)
    failed_count = summary["counts"].get("failed", 0)
    closure_failed = not summary["closure"]["passed"]
    if (
        not_found_count == 0
        and mismatched_count == 0
        and failed_count == 0
        and not closure_failed
    ):
        # "0 findings" is only a pass if something was actually verified.
        # When every provider errored, all sources land in "failed"
        # (UNRESOLVABLE) and nothing was checked — that is an unchecked
        # gate, not a green one (the old fail-open behaviour was unsafe).
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
                    "counts": summary["counts"],
                },
            )
        return

    if config.CITATION_VERIFICATION_POLICY == "strict":
        detail_parts: list[str] = []
        if not_found_count:
            titles_preview = "; ".join(summary["not_found_titles"][:5])
            detail_parts.append(
                f"{not_found_count} cited source(s) could not be found in any "
                f"bibliographic database: {titles_preview}"
            )
        if mismatched_count:
            titles_preview = "; ".join(summary["mismatched_titles"][:5])
            detail_parts.append(
                f"{mismatched_count} cited source(s) did not match the canonical "
                f"bibliographic record: {titles_preview}"
            )
        if failed_count:
            titles_preview = "; ".join(summary["failed_titles"][:5])
            detail_parts.append(
                f"{failed_count} cited source(s) could not be checked because "
                f"verification was unavailable: {titles_preview}"
            )
        if closure_failed:
            missing_preview = ", ".join(summary["closure"]["missing_keys"][:10])
            unverified_preview = ", ".join(summary["closure"]["unverified_keys"][:10])
            detail_parts.append(
                "citation closure failed"
                + (f"; missing keys: {missing_preview}" if missing_preview else "")
                + (
                    f"; unverified keys: {unverified_preview}"
                    if unverified_preview
                    else ""
                )
            )
        detail = "Citation verification failed: " + "; ".join(detail_parts)
        finding_payload = {
            "policy": "strict",
            "not_found_count": not_found_count,
            "not_found_titles": summary["not_found_titles"][:20],
        }
        if mismatched_count:
            finding_payload.update(
                {
                    "mismatched_count": mismatched_count,
                    "mismatched_titles": summary["mismatched_titles"][:20],
                }
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
                    payload=finding_payload,
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
                    "counts": summary["counts"],
                    **finding_payload,
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
    finding_payload = {
        "policy": "mark_only",
        "not_found_count": not_found_count,
        "not_found_titles": summary["not_found_titles"][:20],
    }
    if mismatched_count:
        finding_payload.update(
            {
                "mismatched_count": mismatched_count,
                "mismatched_titles": summary["mismatched_titles"][:20],
            }
        )
    try:
        db.add(
            DocumentProvenance(
                document_id=document_id,
                stage="verification",
                event_type="integrity_report",
                payload=finding_payload,
            )
        )
        await db.commit()
        logger.warning(
            f"⚠️ Citation integrity report for document {document_id}: "
            f"{not_found_count} not_found, {mismatched_count} mismatched "
            f"source(s) (policy=mark_only, continuing)"
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
                # mark_only did not block the pipeline, but integrity findings
                # exist — "warning" so release gates and the UI never show
                # this as a clean pass.
                "passed": True,
                "status": "warning",
                "counts": summary["counts"],
                **finding_payload,
            },
        )
