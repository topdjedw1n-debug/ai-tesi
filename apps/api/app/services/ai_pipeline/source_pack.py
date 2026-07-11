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

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ai_pipeline.rag_retriever import RAGRetriever, SourceDoc
from app.services.ai_pipeline.source_identity import normalize_doi
from app.services.ai_pipeline.text_utils import ascii_fold, content_tokens

logger = logging.getLogger(__name__)

# Minimum sources we want before declaring the pack usable; below this we relax
# the topic threshold once rather than shipping an (almost) empty pack.
_UNDERFILL_FLOOR = 6

# Max alt (translated) section titles turned into queries in the bilingual
# pass. Keeps the HTTP volume bounded: ≤11 primary + ≤7 alt = ≤18 queries
# × 2 providers.
_ALT_TITLE_QUERY_CAP = 4

_BLOCKED_AUTOMATIC_TYPES = {
    "dissertation",
    "thesis",
    "doctoral thesis",
    "master thesis",
    "masters thesis",
    "bachelor thesis",
    "student thesis",
    "degree thesis",
}

_STUDENT_WORK_TEXT_RE = re.compile(
    r"\b(?:"
    r"doctoral\s+(?:thesis|dissertation)|"
    r"phd\s+(?:thesis|dissertation)|"
    r"master(?:s|\s+s)?\s+(?:thesis|dissertation)|"
    r"bachelor(?:s|\s+s)?\s+(?:thesis|dissertation)|"
    r"student\s+(?:thesis|dissertation)|"
    r"degree\s+(?:thesis|dissertation)|"
    r"electronic\s+theses?\s+and\s+dissertations?(?:\s+repository)?|"
    r"theses?\s+and\s+dissertations?\s+repository|"
    r"tesi\s+(?:di\s+laurea|magistrale|dottorale|di\s+dottorato)|"
    r"dissertazione\s+(?:di\s+laurea|dottorale)"
    r")\b"
)

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
    # Full-text passages from manager-uploaded PDFs (uploaded_sources.py).
    # None for API-built packs; when present, prompt_block(query=...) appends
    # the top page-anchored excerpts for the section being written.
    passages: list[Any] | None = None
    # Retrieval outages observed while building the candidate reserve.  An
    # underfilled pack with provider errors is retryable, not proof that too
    # few valid sources exist.
    provider_errors: list[str] = field(default_factory=list)

    def keys(self) -> list[str]:
        return [ps.citation_key for ps in self.sources]

    def by_key(self, key: str) -> PackedSource | None:
        target = (key or "").strip().lower()
        for ps in self.sources:
            if ps.citation_key.lower() == target:
                return ps
        return None

    @staticmethod
    def _canonical_source_sort_key(item: PackedSource) -> tuple[Any, ...]:
        """One stable order for persistence, digests and writer prompts.

        Relevance remains the primary product rule.  The remaining fields are
        deterministic tie-breakers so equal-scored uploaded files and restored
        database rows cannot silently swap places between attempts.
        """
        source = item.source
        return (
            -round(float(item.on_topic_score), 12),
            str(item.citation_key or "").casefold(),
            normalize_doi(source.doi) or "",
            str(source.title or "").strip().casefold(),
            int(source.year or 0),
            str(source.paper_id or ""),
        )

    def canonical_sources(self) -> list[PackedSource]:
        """Return the exact deterministic source order shown to the writer."""
        return sorted(self.sources, key=self._canonical_source_sort_key)

    @staticmethod
    def _canonical_passage_sort_key(passage: Any) -> tuple[Any, ...]:
        """Stable full-text order, including overlapping windows on one page."""
        return (
            str(getattr(passage, "citation_key", "") or "").casefold(),
            int(getattr(passage, "source_file_id", 0) or 0),
            int(getattr(passage, "page_number", 0) or 0),
            str(getattr(passage, "filename", "") or "").casefold(),
            str(getattr(passage, "text", "") or ""),
        )

    def canonical_passages(self) -> list[Any]:
        """Return deterministic PDF passages used by both digest and prompt."""
        return sorted(self.passages or [], key=self._canonical_passage_sort_key)

    def sha256(self) -> str:
        """Digest of every prompt-significant source-pack field.

        Sources and uploaded-PDF passages use the same canonical order as the
        writer prompt.  This makes a database reload stable while still
        detecting changes to source rank, passage identity, page, filename or
        excerpt content. Full uploaded file bytes remain covered by the
        separate task-contract digest.
        """
        rows: list[dict[str, Any]] = []
        for position, packed in enumerate(self.canonical_sources()):
            source = packed.source
            abstract = str(source.abstract or "")
            rows.append(
                {
                    "position": position,
                    "citation_key": packed.citation_key,
                    "on_topic_score": round(float(packed.on_topic_score), 6),
                    "title": str(source.title or "").strip(),
                    "authors": [str(author).strip() for author in source.authors or []],
                    "year": source.year,
                    "doi": normalize_doi(source.doi),
                    "venue": str(source.venue or "").strip() or None,
                    "paper_id": source.paper_id,
                    "provider": getattr(source, "provider", None),
                    "source_type": getattr(source, "source_type", None),
                    "abstract_sha256": hashlib.sha256(
                        abstract.encode("utf-8")
                    ).hexdigest(),
                }
            )
        passage_rows: list[dict[str, Any]] = []
        for position, passage in enumerate(self.canonical_passages()):
            passage_rows.append(
                {
                    "position": position,
                    "source_file_id": int(getattr(passage, "source_file_id", 0) or 0),
                    "citation_key": str(getattr(passage, "citation_key", "") or ""),
                    "filename": str(getattr(passage, "filename", "") or ""),
                    "page_number": int(getattr(passage, "page_number", 0) or 0),
                    "text_sha256": hashlib.sha256(
                        str(getattr(passage, "text", "") or "").encode("utf-8")
                    ).hexdigest(),
                }
            )
        canonical = json.dumps(
            {"sources": rows, "passages": passage_rows},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def prompt_block(
        self,
        limit: int | None = None,
        *,
        query: str | None = None,
        excerpt_limit: int = 6,
    ) -> str:
        """Deterministic, model-facing source list keyed for closed-book citing.

        Without ``query`` (or without full-text passages) the output is
        byte-identical to the pre-full-text format. With both, the top
        page-anchored excerpts for the section being written are appended —
        real page numbers, so downstream evidence can cite them.
        """
        ordered_sources = self.canonical_sources()
        rows = ordered_sources if limit is None else ordered_sources[:limit]
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
        block = "\n".join(lines)

        if query and self.passages:
            # Local import: uploaded_sources imports this module for the pack
            # types, so the excerpt selector must be imported lazily here.
            from app.services.uploaded_sources import select_passages

            excerpts = select_passages(
                self.canonical_passages(), query, limit=excerpt_limit
            )
            if excerpts:
                excerpt_lines = [
                    "",
                    "FULL-TEXT EXCERPTS from the sources above "
                    "(page numbers are real):",
                ]
                for passage in excerpts:
                    text = passage.text.strip().replace("\n", " ")
                    # Never cut an excerpt: passages are already bounded at
                    # ~900 chars, and truncating here would lose exactly the
                    # end-of-window sentences the retrieval selected them for.
                    if len(text) > 1000:
                        text = text[:1000].rstrip() + "…"
                    excerpt_lines.append(
                        f"[{passage.citation_key} | p. {passage.page_number}] "
                        f"«{text}»"
                    )
                block = block + "\n".join(excerpt_lines)
        return block


def is_blocked_automatic_source(source: SourceDoc) -> bool:
    """Return whether an automatically retrieved record is student work.

    Known degree-work provider types block immediately.  Provider taxonomies
    also contain vague non-empty values such as ``posted-content``; those are
    not proof that a record is a scholarly publication, so explicit degree-
    work signals in the bibliographic metadata are always checked as well.
    Manager-uploaded material is governed by the separate uploaded-source
    policy and does not pass through the automatic builder.
    """
    source_type = re.sub(
        r"[_-]+", " ", str(source.source_type or "").strip().casefold()
    )
    if source_type and (
        source_type in _BLOCKED_AUTOMATIC_TYPES
        or "dissertation" in source_type
        or source_type.endswith(" thesis")
    ):
        return True
    text = ascii_fold(
        " ".join(
            str(value or "")
            for value in (source.title, source.venue, source.url, source.paper_id)
        )
    ).casefold()
    text = re.sub(r"[^\w]+", " ", text)
    return bool(_STUDENT_WORK_TEXT_RE.search(text))


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
        allow_threshold_relaxation: bool = True,
        retrieval_page: int = 1,
        raise_on_provider_error: bool = False,
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
        provider_errors: list[str] = []
        for query in queries:
            for provider in (self.rag.search_crossref, self.rag.search_openalex):
                try:
                    if retrieval_page == 1 and not raise_on_provider_error:
                        raw.extend(await provider(query, limit=per_query))
                    else:
                        raw.extend(
                            await provider(
                                query,
                                limit=per_query,
                                page=retrieval_page,
                                raise_on_error=raise_on_provider_error,
                            )
                        )
                except Exception as e:  # provider hiccup must not kill the build
                    provider_errors.append(
                        f"{getattr(provider, '__name__', 'provider')}: {e}"
                    )
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

        # Apply suitability before the candidate-reserve cut. Otherwise a page
        # full of high-ranked dissertations can consume every reserve slot and
        # hide valid records retrieved on that same page.
        eligible = [src for src in deduped if not is_blocked_automatic_source(src)]
        if len(eligible) < len(deduped):
            logger.info(
                "Source pack dropped %s automatic student-work candidate(s) "
                "before reserve selection for document %s",
                len(deduped) - len(eligible),
                document_id,
            )
        deduped = eligible

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
        if len(kept) < _UNDERFILL_FLOOR and allow_threshold_relaxation:
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
            underfilled=underfilled or len(packed) < target_size,
            bilingual=bool(alt_terms),
            provider_errors=provider_errors,
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
        # Present in the same canonical order used by prompts and digests.
        packed.sort(key=SourcePack._canonical_source_sort_key)
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
