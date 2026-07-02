"""
Shared text helpers for the source-grounding pipeline.

Pure, dependency-free utilities used by source_pack.py (topic scoring),
grounding_gate.py, and quality_metrics.py so tokenization / stop-word handling
stays consistent across them.
"""

from __future__ import annotations

import re
import unicodedata

# Multilingual stop words (EN + IT — the two languages that dominate current
# generation). Kept deliberately small: only high-frequency function words that
# add noise to topic-overlap scoring.
STOP_WORDS: frozenset[str] = frozenset(
    {
        # English
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "be",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "into",
        "about",
        "over",
        "between",
        "their",
        "there",
        "which",
        "who",
        "whom",
        "what",
        "how",
        "why",
        "not",
        "but",
        # Italian
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "un",
        "uno",
        "una",
        "di",
        "del",
        "della",
        "dei",
        "delle",
        "degli",
        "dal",
        "dalla",
        "e",
        "ed",
        "o",
        "od",
        "che",
        "chi",
        "con",
        "per",
        "tra",
        "fra",
        "su",
        "sul",
        "sulla",
        "nel",
        "nella",
        "nei",
        "nelle",
        "come",
        "non",
        "ma",
        "si",
        "sono",
        "essere",
        "questo",
        "questa",
        "questi",
        "queste",
        "suo",
        "sua",
        "loro",
        "anche",
        # Elided Italian articles/prepositions: the tokenizer splits
        # "dell'intelligenza" into "dell" + "intelligenza" — the stub carries
        # no content and dilutes topic-coverage scoring.
        "dell",
        "sull",
        "nell",
        "all",
        "dall",
        "quest",
        "senz",
    }
)


def ascii_fold(text: str) -> str:
    """Fold accented characters to ASCII (e.g. 'Pérez' -> 'Perez')."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str | None) -> list[str]:
    """Lowercase, unicode-aware word tokens (length >= 2), order preserved."""
    if not text:
        return []
    # \w is unicode-aware under Python 3 re; keep letters/digits, split the rest.
    return [
        t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if len(t) >= 2
    ]


def content_tokens(text: str | None) -> set[str]:
    """Distinct content tokens (stop words and pure-digit tokens removed)."""
    return {
        t
        for t in tokenize(text)
        if t not in STOP_WORDS and not t.isdigit() and len(t) > 2
    }


# Bracketed in-text citations ("[Rossi2021, 2021]") and per-line leading
# enumeration ("1. Introduzione") — digits that must NOT count as evidence.
_CITATION_RE = re.compile(r"\[[^\]]*\]")
_ENUMERATION_RE = re.compile(r"^\s*\d+[.)]\s", flags=re.MULTILINE)


def contains_concrete_evidence(text: str | None) -> bool:
    """True if the text carries a concrete numeric detail.

    Counts percentages ("30%"), decimals ("2,5" / "3.7") and multi-digit
    numbers ("1200") — AFTER stripping bracketed citations and per-line
    section enumeration, which is what fooled the previous naive `\\d` check
    (citation years and "1." headings are not evidence).

    Known limitation: a bare year in prose ("nel 2023") still counts — it is a
    concrete, checkable fact, and excluding years would also drop real data
    like "nel 2023 il 40% ...". Shared by quality_metrics.evidence_presence
    and grounding_gate.evaluate_grounding — keep them consistent.
    """
    if not text:
        return False
    cleaned = _CITATION_RE.sub(" ", text)
    cleaned = _ENUMERATION_RE.sub(" ", cleaned)
    return bool(
        re.search(r"\d+\s*%", cleaned)
        or re.search(r"\b\d+[.,]\d+\b", cleaned)
        or re.search(r"\b\d{2,}\b", cleaned)
    )
