"""Does a document carry the words of a plan node or of a section's question?

16.09.2026, economics E2: a record was credited to a plan node because the
node's query had returned it, and a document led a section because it had a
readable PDF; a 348-page book on cyber-risk regulation therefore fed the
crowdfunding, minibond and P2P sections while 27 verified records about
crowdfunding and minibond never got a seat. The test here is the same for
every path a document can take to the writer: its title or abstract carries
the node's own bilingual terms (generic words aside), or at least
``MIN_SHARED_TERMS`` distinct content words of the section's own wording
(title, purpose, main points, question). Deterministic, no model call.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

from app.services.search_queries import (
    GENERIC,
    content_tokens,
    is_structural,
    tokens,
)

PREFIX = 6
# Calibrated on the recorded runs of 16.09.2026: one own term of a node in the
# title or abstract, or three distinct words of the section's bilingual
# wording. Same-field full texts on another question (an HIV-integrase thesis
# in a run on antibiotic resistance) are kept off by the document-level topic
# share below, not by this test.
MIN_SHARED_TERMS = 3


def normalize(text: str) -> str:
    """Lower-case, accent-stripped, hyphen-tolerant text for term matching."""
    decomposed = unicodedata.normalize("NFKD", str(text or "")).casefold()
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[\s\-–—_/]+", " ", plain)


@lru_cache(maxsize=4096)
def term_pattern(term: str) -> re.Pattern[str] | None:
    """One pattern per own term: every content word of the term, in any order
    (a word of six letters or more matches by its first six letters:
    "crowdfunding" and "crowdfund", "minibond" and "minibonds")."""
    words = [w for w in tokens(normalize(term)) if len(w) >= 3 and w not in GENERIC]
    if not words:
        return None
    parts = [
        (
            rf"(?=.*\b{re.escape(w[:PREFIX])})"
            if len(w) >= PREFIX
            else rf"(?=.*\b{re.escape(w)}\b)"
        )
        for w in dict.fromkeys(words)
    ]
    return re.compile("".join(parts), re.S)


def node_terms(node: dict[str, Any]) -> list[str]:
    """The node's bilingual terms, each once (S1 often repeats a term)."""
    return list(
        dict.fromkeys(
            t.strip().casefold()
            for t in list(node.get("terms_local") or [])
            + list(node.get("terms_en") or [])
            if isinstance(t, str) and t.strip()
        )
    )


def covers(node: dict[str, Any], text: str) -> int:
    """How many own terms of the node the (normalized) text carries."""
    if is_structural(node):
        return 0
    plain = normalize(text)
    patterns = {
        pattern.pattern: pattern
        for term in node_terms(node)
        if (pattern := term_pattern(term)) is not None
    }  # "minibond" and "minibonds" are one term
    return sum(1 for pattern in patterns.values() if pattern.search(plain))


def document_text(source: Any) -> str:
    """Title and abstract of a source (dict or SourceDoc)."""
    if isinstance(source, dict):
        title, abstract = source.get("title"), source.get("abstract")
    else:
        title, abstract = getattr(source, "title", ""), getattr(source, "abstract", "")
    return f"{title or ''} {abstract or ''}"


def section_fit(
    section: dict[str, Any], nodes: list[dict[str, Any]], text: str, topic: str = ""
) -> tuple[int, int]:
    """(own terms of the section's nodes found, shared content words of the
    section's wording found) for a document's title and abstract. Words of
    the topic itself do not count as shared: every record of the pack carries
    them (psychology, 17.09: a review on healthcare workers reached the FoMO
    section on "social", "media", "psychological" alone)."""
    by_id = {n.get("scope_id"): n for n in nodes}
    own = sum(
        covers(by_id[s], text) for s in section.get("scope_ids") or [] if s in by_id
    )
    # The wording is bilingual: the plan text plus the nodes' own terms in
    # both languages, so an English review fits an Italian section on the
    # same question (biology, 16.09: the AMR-mechanisms review was refused
    # by the Italian wording of "Meccanismi molecolari di resistenza").
    wording = " ".join(
        str(part)
        for part in [
            section.get("title"),
            section.get("purpose"),
            section.get("question"),
            *(section.get("main_points") or []),
            *(
                term
                for s in section.get("scope_ids") or []
                if s in by_id
                for term in node_terms(by_id[s])
            ),
        ]
        if part
    )
    shared = (
        set(content_tokens(wording)) & set(content_tokens(normalize(text)))
    ) - set(content_tokens(normalize(topic)))
    return own, len(shared)


# A full text may hand a section its pages only when at least this share of
# its windows carries a topic anchor. Recorded 16.09.2026: the two off-topic
# theses of the biology run 35 %, the book on cyber-risk regulation 48 %, the
# migration report 30 %; every full text on topic 57-99 %.
MIN_DOCUMENT_TOPIC_SHARE = 0.5


def document_topic_share(texts: list[str], pattern: re.Pattern[str] | None) -> float:
    """Share of the texts (windows) carrying at least one topic anchor."""
    if not texts:
        return 0.0
    if pattern is None:
        return 1.0
    return sum(1 for t in texts if pattern.search(t.casefold())) / len(texts)


def about_section(
    section: dict[str, Any],
    nodes: list[dict[str, Any]],
    source: Any,
    topic: str = "",
) -> bool:
    """The document is about the section: its title or abstract carries an
    own term of the section's nodes, or at least MIN_SHARED_TERMS distinct
    content words of the section's bilingual wording beyond the topic's."""
    own, shared = section_fit(section, nodes, document_text(source), topic)
    return own >= 1 or shared >= MIN_SHARED_TERMS
