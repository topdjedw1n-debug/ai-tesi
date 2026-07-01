"""
Upfront topic-locked source pack (Academic Quality Engine).

Builds ONE document-level, on-topic set of real academic sources before the
outline, so the outline and every section are grounded in the same curated,
keyed evidence instead of ad-hoc per-section retrieval or the model's
parametric memory. This is the fix for the failure where a thesis on "AI in
education" cited real-but-off-topic corporate-training articles.

Retrieval reuses the free, key-less providers on RAGRetriever (Crossref +
OpenAlex) and its deduper; topic-relevance scoring is fully local (no LLM, no
extra API calls). Persistence lives in source_verification_stage.py
(persist_source_pack / load_source_pack).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.ai_pipeline.rag_retriever import RAGRetriever, SourceDoc
from app.services.ai_pipeline.text_utils import ascii_fold, content_tokens

logger = logging.getLogger(__name__)

# Minimum sources we want before declaring the pack usable; below this we relax
# the topic threshold once rather than shipping an (almost) empty pack.
_UNDERFILL_FLOOR = 6

# Coarse domain detection → anchor terms (reward) + off-topic markers (penalize).
# Small, curated constants (YAGNI); make configurable later only if needed. The
# "education" entry is what rejects corporate-training sources for school/uni
# topics — the concrete failure case.
_DOMAIN_ANCHORS: dict[str, dict[str, set[str]]] = {
    "education": {
        "detect": {
            "education",
            "educational",
            "educazione",
            "istruzione",
            "scuola",
            "school",
            "schools",
            "teaching",
            "teacher",
            "teachers",
            "student",
            "students",
            "learning",
            "classroom",
            "pedagog",
            "didattica",
            "apprendimento",
            "insegnamento",
            "docenti",
            "studenti",
            "scolastic",
            "university",
            "universita",
            "higher education",
        },
        "anchor": {
            "education",
            "educational",
            "educazione",
            "istruzione",
            "scuola",
            "school",
            "classroom",
            "teacher",
            "teachers",
            "student",
            "students",
            "learning",
            "pedagogy",
            "pedagogical",
            "didattica",
            "apprendimento",
            "insegnamento",
            "curriculum",
            "tutoring",
            "e-learning",
            "scolastic",
            "docenti",
            "studenti",
            "university",
            "universita",
        },
        "off_topic": {
            "corporate",
            "workplace",
            "employee",
            "employees",
            "onboarding",
            "aziendale",
            "azienda",
            "hr",
            "marketing",
            "sales",
            "logistics",
            "manufacturing",
            "supply",
            "enterprise",
            "b2b",
            "recruitment",
        },
    },
}


@dataclass
class PackedSource:
    """A retrieved source plus its pack-scoped key and topic-relevance score."""

    source: SourceDoc
    citation_key: str
    on_topic_score: float


@dataclass
class SourcePack:
    """The document-level, topic-locked pack of sources shared across stages."""

    document_id: int
    topic: str
    sources: list[PackedSource] = field(default_factory=list)
    underfilled: bool = False

    def keys(self) -> list[str]:
        return [ps.citation_key for ps in self.sources]

    def by_key(self, key: str) -> PackedSource | None:
        target = (key or "").strip().lower()
        for ps in self.sources:
            if ps.citation_key.lower() == target:
                return ps
        return None

    def prompt_block(self, limit: int | None = None) -> str:
        """Deterministic, model-facing source list keyed for closed-book citing."""
        rows = self.sources if limit is None else self.sources[:limit]
        if not rows:
            return ""
        lines = []
        for ps in rows:
            src = ps.source
            authors = ", ".join(src.authors[:3]) if src.authors else "n.a."
            if src.authors and len(src.authors) > 3:
                authors += " et al."
            year = src.year or "n.d."
            venue = f" {src.venue}." if src.venue else ""
            abstract = (src.abstract or "").strip().replace("\n", " ")
            if len(abstract) > 300:
                abstract = abstract[:300].rstrip() + "…"
            snippet = f" {abstract}" if abstract else ""
            lines.append(
                f"[{ps.citation_key}] {src.title} ({authors}, {year}).{venue}{snippet}"
            )
        return "\n".join(lines)


class SourcePackBuilder:
    """Builds a topic-locked SourcePack from the free scholarly providers."""

    def __init__(self, rag_retriever: RAGRetriever | None = None) -> None:
        self.rag = rag_retriever or RAGRetriever()

    async def build(
        self,
        *,
        topic: str,
        language: str,
        document_id: int,
        target_size: int = 24,
        min_on_topic_score: float = 0.35,
        section_titles: list[str] | None = None,
    ) -> SourcePack:
        """
        Retrieve, topic-score, filter, rank and key a source pack.

        Never raises: provider errors degrade to whatever sources were gathered
        (possibly an empty, underfilled pack) so generation is never harder-
        failed than today.
        """
        topic = (topic or "").strip()
        queries = self._build_queries(topic, section_titles)
        per_query = max(10, target_size)

        raw: list[SourceDoc] = []
        for query in queries:
            for provider in (self.rag.search_crossref, self.rag.search_openalex):
                try:
                    raw.extend(await provider(query, limit=per_query))
                except Exception as e:  # provider hiccup must not kill the build
                    logger.warning(f"Source pack provider failed for '{query}': {e}")

        deduped = self.rag._deduplicate_sources(raw)

        topic_terms = content_tokens(topic)
        for t in section_titles or []:
            topic_terms |= content_tokens(t)
        domain = self._detect_domain(topic_terms)

        scored: list[tuple[float, SourceDoc]] = [
            (self._on_topic_score(src, topic_terms, domain), src) for src in deduped
        ]

        underfilled = False
        kept = [(s, src) for s, src in scored if s >= min_on_topic_score]
        if len(kept) < _UNDERFILL_FLOOR:
            # Relax the threshold once rather than ship an (almost) empty pack.
            relaxed = max(0.0, min_on_topic_score / 2)
            kept = [(s, src) for s, src in scored if s >= relaxed]
            underfilled = True
            logger.warning(
                f"Source pack underfilled for document {document_id}: "
                f"{len(kept)} sources at relaxed threshold {relaxed:.2f} "
                f"(wanted >= {_UNDERFILL_FLOOR})"
            )

        # Rank for selection: relevance, then impact, then recency, then title.
        kept.sort(
            key=lambda item: (
                -item[0],
                -(item[1].citation_count or 0),
                -(item[1].year or 0),
                (item[1].title or "").lower(),
            )
        )
        selected = kept[:target_size]

        packed = self._assign_keys(selected)
        pack = SourcePack(
            document_id=document_id,
            topic=topic,
            sources=packed,
            underfilled=underfilled or not packed,
        )
        logger.info(
            f"Built source pack for document {document_id}: {len(packed)} sources "
            f"from {len(deduped)} candidates (domain={domain or 'generic'})"
        )
        return pack

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _build_queries(topic: str, section_titles: list[str] | None) -> list[str]:
        """Deterministic, deduped query set: topic + topic×section-title."""
        queries: list[str] = []
        if topic:
            queries.append(topic)
        for title in (section_titles or [])[:8]:
            title = (title or "").strip()
            if title:
                queries.append(f"{topic} {title}".strip())
        # Dedup preserving order.
        seen: set[str] = set()
        out: list[str] = []
        for q in queries:
            key = q.lower()
            if q and key not in seen:
                seen.add(key)
                out.append(q)
        return out

    @staticmethod
    def _detect_domain(topic_terms: set[str]) -> str | None:
        for domain, cfg in _DOMAIN_ANCHORS.items():
            if any(
                term == d or term.startswith(d) or d in term
                for term in topic_terms
                for d in cfg["detect"]
            ):
                return domain
        return None

    @staticmethod
    def _on_topic_score(
        src: SourceDoc, topic_terms: set[str], domain: str | None
    ) -> float:
        """Local topic-relevance score in [0,1] (no LLM / external call)."""
        if not topic_terms:
            return 0.0

        source_terms = content_tokens(src.title) | content_tokens(src.abstract)
        if not source_terms:
            return 0.0

        # Topic coverage: fraction of topic terms present in the source.
        coverage = len(topic_terms & source_terms) / len(topic_terms)
        score = coverage

        if domain is not None:
            cfg = _DOMAIN_ANCHORS[domain]
            has_anchor = bool(source_terms & cfg["anchor"])
            has_off_topic = bool(source_terms & cfg["off_topic"])
            if has_anchor:
                score += 0.15
            if has_off_topic and not has_anchor:
                # Real-but-off-topic (e.g. corporate-training for a school topic).
                score -= 0.4

        return max(0.0, min(1.0, score))

    @staticmethod
    def _assign_keys(
        selected: list[tuple[float, SourceDoc]],
    ) -> list[PackedSource]:
        """Assign stable, collision-safe citation keys deterministically.

        Order: score desc, then normalized title asc (independent of the
        selection tie-breakers) so keys are reproducible across runs.
        """
        ordered = sorted(
            selected, key=lambda item: (-item[0], (item[1].title or "").lower())
        )
        used: set[str] = set()
        packed: list[PackedSource] = []
        for score, src in ordered:
            base = SourcePackBuilder._base_key(src)
            key = base
            suffix = ord("b")
            while key.lower() in used:
                key = f"{base}{chr(suffix)}"
                suffix += 1
            used.add(key.lower())
            packed.append(
                PackedSource(source=src, citation_key=key, on_topic_score=score)
            )
        # Present most-relevant first for prompts.
        packed.sort(key=lambda ps: ps.on_topic_score, reverse=True)
        return packed

    @staticmethod
    def _base_key(src: SourceDoc) -> str:
        """AuthorYear key, e.g. 'Rossi2021' (fallbacks: title word, 'nd')."""
        name = ""
        if src.authors:
            last = ascii_fold(src.authors[0]).strip().split()
            if last:
                name = "".join(c for c in last[-1] if c.isalnum())
        if not name:
            for tok in ascii_fold(src.title or "").split():
                cleaned = "".join(c for c in tok if c.isalnum())
                if len(cleaned) > 2:
                    name = cleaned.capitalize()
                    break
        if not name:
            name = "Source"
        year = str(src.year) if src.year else "nd"
        return f"{name}{year}"
