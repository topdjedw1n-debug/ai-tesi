"""Verify and curate a source pack before the first section is written."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_identity import sources_equivalent
from app.services.ai_pipeline.source_pack import (
    PackedSource,
    SourcePack,
    SourcePackBuilder,
    is_blocked_automatic_source,
)
from app.services.citation_verifier import (
    FUZZY_MATCH_THRESHOLD,
    CitationVerifier,
    SourceInput,
    VerificationStatus,
)


@dataclass(frozen=True)
class SourceRejection:
    title: str
    reason: str


@dataclass
class SourcePreflightOutcome:
    pack: SourcePack
    candidate_count: int
    verified_count: int
    target_size: int
    minimum_required: int
    rejected: list[SourceRejection] = field(default_factory=list)
    transient_count: int = 0
    unknown_type_count: int = 0

    @property
    def meets_minimum(self) -> bool:
        return self.verified_count >= self.minimum_required

    @property
    def needs_top_up(self) -> bool:
        return self.verified_count < self.target_size

    def provenance_payload(self, *, top_up_attempted: bool) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for rejection in self.rejected:
            counts[rejection.reason] = counts.get(rejection.reason, 0) + 1
        return {
            "status": "passed" if self.meets_minimum else "failed",
            "candidates": self.candidate_count,
            "verified": self.verified_count,
            "final_size": len(self.pack.sources),
            "target": self.target_size,
            "min_required": self.minimum_required,
            "rejected_by_reason": counts,
            "rejected": [
                {"title": item.title[:300], "reason": item.reason}
                for item in self.rejected[:30]
            ],
            "transient_count": self.transient_count,
            "unknown_type_count": self.unknown_type_count,
            "top_up_attempted": top_up_attempted,
            "sha256": self.pack.sha256() if self.pack.sources else None,
        }


def _is_uploaded(source: SourceDoc) -> bool:
    return bool(
        str(source.paper_id or "").startswith("uploaded:")
        or source.provider == "uploaded"
    )


def source_has_preflight_proof(source: SourceDoc) -> bool:
    """Return whether a restored source carries the proof required to reuse it."""
    if source.verification_status != "verified":
        return False
    metadata = source.canonical_metadata
    if not isinstance(metadata, dict) or metadata.get("status") != "verified":
        return False
    if _is_uploaded(source):
        return metadata.get("provider") == "uploaded_file"
    return True


def invalid_preverified_source_keys(pack: SourcePack) -> list[str]:
    """List persisted pack keys that are unsafe to hand to a resumed writer."""
    return [
        packed.citation_key
        for packed in pack.sources
        if not source_has_preflight_proof(packed.source)
    ]


def _canonical_source(source: SourceDoc, result: Any) -> SourceDoc:
    canonical = result.to_dict()
    return SourceDoc(
        title=result.title or source.title,
        authors=list(result.authors or source.authors or []),
        year=result.year or source.year,
        abstract=result.abstract or source.abstract,
        paper_id=source.paper_id,
        venue=result.venue or source.venue,
        citation_count=source.citation_count,
        url=source.url,
        doi=result.doi or source.doi,
        provider=source.provider or result.provider,
        source_type=source.source_type,
        verification_status="verified",
        canonical_metadata=canonical,
    )


def _uploaded_verified_source(source: SourceDoc) -> SourceDoc:
    metadata = {
        "status": "verified",
        "provider": "uploaded_file",
        "reason": "manager-uploaded source PDF",
        "title": source.title,
        "authors": list(source.authors or []),
        "year": source.year,
        "doi": source.doi,
        "abstract": source.abstract,
    }
    return SourceDoc(
        title=source.title,
        authors=list(source.authors or []),
        year=source.year,
        abstract=source.abstract,
        paper_id=source.paper_id,
        venue=source.venue,
        citation_count=source.citation_count,
        url=source.url,
        doi=source.doi,
        provider="uploaded",
        source_type=source.source_type or "uploaded_pdf",
        verification_status="verified",
        canonical_metadata=metadata,
    )


def _deduplicate_verified(
    values: list[tuple[float, SourceDoc, str, bool]],
) -> list[tuple[float, SourceDoc, str, bool]]:
    # Uploaded material wins over automatic retrieval; then relevance wins.
    ordered = sorted(values, key=lambda item: (not item[3], -item[0]))
    deduped: list[tuple[float, SourceDoc, str, bool]] = []
    for item in ordered:
        if any(sources_equivalent(existing[1], item[1]) for existing in deduped):
            continue
        deduped.append(item)
    return deduped


def _assign_final_keys(
    document_id: int,
    topic: str,
    values: list[tuple[float, SourceDoc, str, bool]],
    *,
    target_size: int,
    passages: list[Any] | None,
    bilingual: bool,
) -> SourcePack:
    uploaded = [item for item in values if item[3]]
    automatic = [item for item in values if not item[3]]
    automatic.sort(
        key=lambda item: (
            -item[0],
            -(item[1].citation_count or 0),
            -(item[1].year or 0),
            item[1].title.casefold(),
        )
    )
    automatic_limit = max(0, target_size - len(uploaded))
    automatic = automatic[:automatic_limit]

    packed: list[PackedSource] = [
        PackedSource(source, original_key, score)
        for score, source, original_key, _ in uploaded
    ]
    taken = {item.citation_key.casefold() for item in packed}
    for generated in SourcePackBuilder._assign_keys(
        [(score, source) for score, source, _, _ in automatic]
    ):
        key = generated.citation_key
        if key.casefold() in taken:
            base = key
            index = 0
            while key.casefold() in taken:
                key = f"{base}{SourcePackBuilder._alpha_suffix(index)}"
                index += 1
        taken.add(key.casefold())
        packed.append(PackedSource(generated.source, key, generated.on_topic_score))

    packed.sort(key=SourcePack._canonical_source_sort_key)
    return SourcePack(
        document_id=document_id,
        topic=topic,
        sources=packed,
        underfilled=len(packed) < target_size,
        bilingual=bilingual,
        passages=passages,
    )


async def preverify_source_pack(
    pack: SourcePack,
    verifier: CitationVerifier,
    *,
    target_size: int,
    minimum_verified: int,
) -> SourcePreflightOutcome:
    """Return the final verified pack; never let an unsuitable source through."""
    accepted: list[tuple[float, SourceDoc, str, bool]] = []
    external: list[PackedSource] = []
    rejected: list[SourceRejection] = []
    unknown_type_count = 0

    for packed in pack.sources:
        source = packed.source
        if _is_uploaded(source):
            accepted.append(
                (
                    packed.on_topic_score,
                    _uploaded_verified_source(source),
                    packed.citation_key,
                    True,
                )
            )
            continue
        if is_blocked_automatic_source(source):
            rejected.append(SourceRejection(source.title, "student_work"))
            continue
        if not source.source_type:
            unknown_type_count += 1
        if not source.authors or not source.year:
            rejected.append(SourceRejection(source.title, "incomplete_metadata"))
            continue
        external.append(packed)

    results = await verifier.verify_sources(
        [
            SourceInput(
                title=packed.source.title,
                authors=list(packed.source.authors or []),
                year=packed.source.year,
                doi=packed.source.doi,
            )
            for packed in external
        ]
    )

    transient_count = 0
    for packed, result in zip(external, results, strict=True):
        source = packed.source
        if result.status == VerificationStatus.VERIFIED and (
            result.match_score is None or result.match_score >= FUZZY_MATCH_THRESHOLD
        ):
            accepted.append(
                (
                    packed.on_topic_score,
                    _canonical_source(source, result),
                    packed.citation_key,
                    False,
                )
            )
            continue
        if result.status == VerificationStatus.UNRESOLVABLE:
            transient_count += 1
            reason = "verification_unavailable"
        elif result.status == VerificationStatus.VERIFIED:
            reason = "metadata_mismatch"
        else:
            reason = "not_found"
        rejected.append(SourceRejection(source.title, reason))

    deduped = _deduplicate_verified(accepted)
    final_pack = _assign_final_keys(
        pack.document_id,
        pack.topic,
        deduped,
        target_size=target_size,
        passages=pack.passages,
        bilingual=pack.bilingual,
    )
    return SourcePreflightOutcome(
        pack=final_pack,
        candidate_count=len(pack.sources),
        verified_count=len(final_pack.sources),
        target_size=target_size,
        minimum_required=minimum_verified,
        rejected=rejected,
        transient_count=transient_count + len(pack.provider_errors),
        unknown_type_count=unknown_type_count,
    )


__all__ = [
    "SourcePreflightOutcome",
    "SourceRejection",
    "invalid_preverified_source_keys",
    "preverify_source_pack",
    "source_has_preflight_proof",
]
