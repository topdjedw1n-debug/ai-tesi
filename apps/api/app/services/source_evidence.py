"""The same immutable evidence text is used by writers and claim checkers."""

from __future__ import annotations

import hashlib
from typing import Any

EVIDENCE_KEY = "academic_evidence"
EVIDENCE_LIMIT = 2400


def frozen_evidence(source: Any) -> dict[str, Any] | None:
    return (getattr(source, "canonical_metadata", None) or {}).get(EVIDENCE_KEY)


def evidence_text(source: Any) -> str | None:
    evidence = frozen_evidence(source)
    if not isinstance(evidence, dict):
        return None
    text = evidence.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > EVIDENCE_LIMIT:
        return None
    if hashlib.sha256(text.encode()).hexdigest() != evidence.get("sha256"):
        return None
    return text


def freeze_evidence(
    source: Any, passages: list[Any], citation_key: str, *, query: str = ""
) -> bool:
    chunks: list[str] = []
    origins: list[dict[str, Any]] = []
    abstract = str(source.abstract or "").strip()
    uploaded = source.provider == "uploaded" or str(source.paper_id or "").startswith(
        "uploaded:"
    )
    if abstract and not uploaded:
        chunks.append(abstract)
        origins.append(
            {
                "kind": "abstract",
                "provider": (source.canonical_metadata or {}).get("evidence_provider")
                or source.provider,
                "doi": source.doi,
                "paper_id": source.paper_id,
            }
        )
    selected = [p for p in passages if p.citation_key == citation_key]
    selection = "provided_order"
    if uploaded:
        from app.services.uploaded_sources import select_passages

        relevant = select_passages(selected, query or source.title)
        # Token matching cannot align different languages. Keep actual page
        # text when it finds nothing, instead of silently dropping the file.
        selection = "lexical_relevance" if relevant else "page_order_fallback"
        selected = relevant or sorted(selected, key=lambda p: p.page_number)
    for passage in selected:
        if passage.citation_key != citation_key:
            continue
        chunks.append(f"[page {passage.page_number}] {passage.text}")
        origins.append(
            {
                "kind": "uploaded_excerpt",
                "source_file_id": passage.source_file_id,
                "page_number": passage.page_number,
                "selection": selection,
                "text_sha256": hashlib.sha256(passage.text.encode()).hexdigest(),
            }
        )
        if len("\n".join(chunks)) >= EVIDENCE_LIMIT:
            break
    joined = "\n".join(chunks)
    text = joined[:EVIDENCE_LIMIT]
    if not text.strip():
        return False
    source.canonical_metadata = {
        **(source.canonical_metadata or {}),
        EVIDENCE_KEY: {
            "version": "source-evidence-v1",
            "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "origins": origins,
            "truncated": len(joined) > EVIDENCE_LIMIT,
        },
    }
    return True


def preserve_evidence(source: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    frozen = frozen_evidence(source)
    return {**metadata, **({EVIDENCE_KEY: frozen} if frozen is not None else {})}
