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
