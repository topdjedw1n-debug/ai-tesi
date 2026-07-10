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

# Max alt (translated) section titles turned into queries in the bilingual
# pass. Keeps the HTTP volume bounded: ≤11 primary + ≤7 alt = ≤18 queries
# × 2 providers.
_ALT_TITLE_QUERY_CAP = 4

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
            # NOTE: bare "learning" is deliberately NOT a detect marker — it
            # appears in "machine learning" / "deep learning" topics that have
            # nothing to do with education, and a false education detection
            # would hard-gate every source of a non-education pack to 0.0.
            # It stays in "anchor" below: once the domain IS education, a
            # source mentioning learning is legitimate domain signal.
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
        # Matched with fold+prefix semantics (_term_hit): stems cover the
        # inflected Italian forms (educativ- -> educativo/educativa/educative).
        "anchor": {
            "education",
            "educational",
            "educazione",
            "educativ",
            "istruzione",
            "scuola",
            "school",
            "classroom",
            "teacher",
            "teachers",
            "student",
            "students",
            "learning",
            "imparare",
            "pedagog",
            "didattic",
            "apprendimento",
            "insegnamento",
            "curriculum",
            "tutoring",
            "e-learning",
            "scolastic",
            "docenti",
            "studenti",
            "allievo",
            "allievi",
            "discenti",
            "formazione",
            "formativ",
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
            # Real-but-off-topic domains that slipped into the doc-3 pack:
            # healthcare, e-voting, psychotherapy papers that mention AI but
            # have nothing to do with education.
            "sanit",
            "clinic",
            "diagnos",
            "pazient",
            "voto",
            "elettoral",
            "psicoterap",
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
    # True when the pack was queried/scored against an alt-language (English)
    # topic translation as well — recorded in provenance for the QA panel.
    bilingual: bool = False

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
        alt_topic: str | None = None,
        alt_section_titles: list[str] | None = None,
    ) -> SourcePack:
        """
        Retrieve, topic-score, filter, rank and key a source pack.

        Never raises: provider errors degrade to whatever sources were gathered
        (possibly an empty, underfilled pack) so generation is never harder-
        failed than today.

        alt_topic / alt_section_titles are an OPTIONAL English translation of
        the topic and section titles (doc-8 fix: English-language scholarship
        is the norm in non-English theses, so the pack queries and scores
        against BOTH language versions). The builder never translates by
        itself — it stays pure (no LLM, no db) — callers pass the translation
        in; when alt_topic is None behavior is byte-identical to before.
        """
        topic = (topic or "").strip()
        alt_topic = (alt_topic or "").strip()

        # Domain first: anchored queries need it, and scoring reuses it.
        topic_terms = content_tokens(topic)
        for t in section_titles or []:
            topic_terms |= content_tokens(t)

        alt_terms: set[str] = set()
        if alt_topic:
            alt_terms = content_tokens(alt_topic)
            for t in alt_section_titles or []:
                alt_terms |= content_tokens(t)

        domain = self._detect_domain(topic_terms | alt_terms)

        queries = self._build_queries(topic, section_titles, language, domain)
        if alt_topic:
            queries += self._build_queries(
                alt_topic,
                (alt_section_titles or [])[:_ALT_TITLE_QUERY_CAP],
                "en",
                domain,
            )
            # Merge-dedup preserving order (same pattern as _build_queries).
            seen: set[str] = set()
            merged: list[str] = []
            for q in queries:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    merged.append(q)
            queries = merged
        per_query = max(10, target_size)

        raw: list[SourceDoc] = []
        for query in queries:
            for provider in (self.rag.search_crossref, self.rag.search_openalex):
                try:
                    raw.extend(await provider(query, limit=per_query))
                except Exception as e:  # provider hiccup must not kill the build
                    logger.warning(f"Source pack provider failed for '{query}': {e}")

        deduped = self.rag._deduplicate_sources(raw)

        # The pack is the citation universe for the whole document, and the
        # citation formatter hard-requires author(s) + year (SourceDocument
        # validates both in __post_init__): an uncitable source in the pack
        # crashes section generation mid-run (doc-9 failure: an authorless
        # Crossref row). Drop them here, before scoring.
        citable = [src for src in deduped if src.authors and src.year]
        if len(citable) < len(deduped):
            logger.info(
                f"Source pack dropped {len(deduped) - len(citable)} uncitable "
                f"candidate(s) (missing author/year) for document {document_id}"
            )
        deduped = citable

        # Bilingual scoring: max() of the two passes, so a good EN source is
        # not killed by comparison against Italian tokens (and max only ever
        # RAISES scores, so existing monolingual packs cannot degrade). The
        # anchor gate and off_topic penalties apply in both passes. A short
        # alt topic would inflate coverage via a small denominator — mitigated
        # by folding the alt section titles into alt_terms (mirrors
        # topic_terms).
        scored: list[tuple[float, SourceDoc]] = [
            (
                max(
                    self._on_topic_score(src, topic_terms, domain),
                    (
                        self._on_topic_score(src, alt_terms, domain)
                        if alt_terms
                        else 0.0
                    ),
                ),
                src,
            )
            for src in deduped
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
            bilingual=bool(alt_terms),
        )
        logger.info(
            f"Built source pack for document {document_id}: {len(packed)} sources "
            f"from {len(deduped)} candidates (domain={domain or 'generic'}, "
            f"bilingual={pack.bilingual})"
        )
        return pack

    # ------------------------------------------------------------------ helpers

    # Language-appropriate anchor terms appended to the topic as extra queries
    # when a domain is detected — they pull domain-specific candidates that the
    # bare topic query misses (the doc-3 pack was an "Italian AI" grab-bag
    # because only the bare topic was queried).
    _QUERY_ANCHORS: dict[str, dict[str, list[str]]] = {
        "education": {
            "it": ["istruzione scuola", "apprendimento studenti"],
            "en": ["education school", "student learning"],
        },
    }

    @staticmethod
    def _build_queries(
        topic: str,
        section_titles: list[str] | None,
        language: str = "en",
        domain: str | None = None,
    ) -> list[str]:
        """Deterministic, deduped query set: topic + topic×anchor + topic×title.

        Bounded: 1 bare topic + ≤2 anchored + ≤8 section-title queries ≤ 11.
        """
        queries: list[str] = []
        if topic:
            queries.append(topic)
        if domain is not None and topic:
            lang_anchors = SourcePackBuilder._QUERY_ANCHORS.get(domain, {})
            anchors = lang_anchors.get(language) or lang_anchors.get("en") or []
            for anchor in anchors[:2]:
                queries.append(f"{topic} {anchor}")
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
    def _term_hit(source_terms: set[str], markers: set[str]) -> bool:
        """True if any (accent-folded) source term equals or starts with a marker.

        Prefix-only (no substring) so stems like 'educativ' match 'educative'
        without 'voto' matching inside unrelated words.
        """
        for term in source_terms:
            folded = ascii_fold(term)
            for marker in markers:
                if folded == marker or folded.startswith(marker):
                    return True
        return False

    @staticmethod
    def _on_topic_score(
        src: SourceDoc, topic_terms: set[str], domain: str | None
    ) -> float:
        """Local topic-relevance score in [0,1] (no LLM / external call).

        When a domain is detected, its anchor vocabulary is a HARD GATE: a
        source with no anchor term in title+abstract scores 0.0 regardless of
        raw token overlap. This is what stops "any Italian AI paper" (e-voting,
        healthcare, psychotherapy) from riding in on the shared
        intelligenza/artificiale/impatto tokens — the doc-3 failure mode.
        """
        if not topic_terms:
            return 0.0

        source_terms = content_tokens(src.title) | content_tokens(src.abstract)
        if not source_terms:
            return 0.0

        if domain is not None:
            cfg = _DOMAIN_ANCHORS[domain]
            # Venue counts toward the gate (an education/formazione journal is
            # legitimate domain signal even when the abstract is missing) but
            # NOT toward coverage, so it can't inflate the score.
            gate_terms = source_terms | content_tokens(src.venue)
            if not SourcePackBuilder._term_hit(gate_terms, cfg["anchor"]):
                # Hard gate: a domain topic requires domain vocabulary.
                return 0.0

        # Topic coverage: fraction of topic terms present in the source.
        coverage = len(topic_terms & source_terms) / len(topic_terms)
        score = coverage

        if domain is not None:
            cfg = _DOMAIN_ANCHORS[domain]
            score += 0.15  # anchored (passed the gate above)
            if SourcePackBuilder._term_hit(source_terms, cfg["off_topic"]):
                # Anchored but tainted (e.g. "formazione aziendale").
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
        packed: list[PackedSource] = []
        groups: dict[str, list[tuple[float, SourceDoc, str]]] = {}
        for score, src in ordered:
            base = SourcePackBuilder._base_key(src)
            groups.setdefault(base.casefold(), []).append((score, src, base))

        for items in groups.values():
            collision = len(items) > 1
            for index, (score, src, base) in enumerate(items):
                # APA requires every same-author/same-year member to carry a
                # suffix (2021a, 2021b), including the first one. Using an
                # unsuffixed first source would make the in-text citation and
                # bibliography ambiguous.
                suffix = SourcePackBuilder._alpha_suffix(index) if collision else ""
                packed.append(
                    PackedSource(
                        source=src,
                        citation_key=f"{base}{suffix}",
                        on_topic_score=score,
                    )
                )
        # Present most-relevant first for prompts.
        packed.sort(key=lambda ps: ps.on_topic_score, reverse=True)
        return packed

    @staticmethod
    def _base_key(src: SourceDoc) -> str:
        """AuthorYear key, e.g. 'Rossi2021' (fallbacks: title word, 'nd')."""
        name = ""
        if src.authors:
            author = ascii_fold(src.authors[0]).strip()
            author_parts = author.split()
            if author_parts:
                surname = author.split(",", 1)[0] if "," in author else author_parts[-1]
                name = "".join(c for c in surname if c.isalnum())
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

    @staticmethod
    def _alpha_suffix(index: int) -> str:
        """Return deterministic a..z, aa.. suffixes for rare large collisions."""
        value = index + 1
        chars: list[str] = []
        while value:
            value, remainder = divmod(value - 1, 26)
            chars.append(chr(ord("a") + remainder))
        return "".join(reversed(chars))
