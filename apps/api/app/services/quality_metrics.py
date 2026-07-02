"""
Local quality-proxy metrics (Academic Quality Engine).

Pure, dependency-free signals used to judge grounding-run output WITHOUT an
external AI detector (Compilatio is not integrated; GPTZero/Originality may be
unavailable locally). These are proxies — they do NOT claim a detector score;
they measure the properties that correlate with the "water" + AI-style failure:
citation grounding, outline adherence, per-section evidence, sentence-length
variance (burstiness), and connector/cliché density.

Used by scripts/grounding_report.py and covered by tests/test_quality_metrics.py.
"""

from __future__ import annotations

import re
import statistics
from typing import TYPE_CHECKING, Any

from app.services.ai_pipeline.text_utils import contains_concrete_evidence
from app.services.grounding_gate import evaluate_grounding

if TYPE_CHECKING:
    from app.services.ai_pipeline.source_pack import SourcePack

# Connector / cliché n-grams whose overuse is a hallmark of generic AI text
# (EN + IT — the two dominant generation languages).
_CLICHE_PHRASES: tuple[str, ...] = (
    # English
    "moreover",
    "furthermore",
    "in conclusion",
    "on the other hand",
    "it is important to note",
    "double-edged sword",
    "balanced approach",
    "in today's world",
    "plays a crucial role",
    "when it comes to",
    "in summary",
    "last but not least",
    # Italian
    "tuttavia",
    "inoltre",
    "pertanto",
    "infine",
    "in conclusione",
    "d'altra parte",
    "è importante notare",
    "approccio equilibrato",
    "approccio bilanciato",
    "gioca un ruolo",
    "al giorno d'oggi",
    "a doppio taglio",
    "in sintesi",
)


def _sentences(text: str) -> list[str]:
    """Naive sentence split on ., !, ? (good enough for length variance)."""
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in (s.strip() for s in parts) if p]


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or "", flags=re.UNICODE))


def sentence_length_stats(text: str) -> dict[str, float]:
    """Sentence-count and word-per-sentence mean/stdev/min/max."""
    sents = _sentences(text)
    lengths = [_word_count(s) for s in sents]
    if not lengths:
        return {"sentences": 0, "mean": 0.0, "stdev": 0.0, "min": 0, "max": 0}
    return {
        "sentences": len(lengths),
        "mean": round(statistics.fmean(lengths), 2),
        "stdev": round(statistics.pstdev(lengths), 2) if len(lengths) > 1 else 0.0,
        "min": min(lengths),
        "max": max(lengths),
    }


def burstiness(text: str) -> float:
    """Stdev of sentence lengths (higher = more human-like rhythm)."""
    return sentence_length_stats(text)["stdev"]


def connector_cliche_density(text: str, language: str = "en") -> dict[str, float]:
    """Cliché/connector phrase hits per 1000 words (lower = better)."""
    low = (text or "").lower()
    hits = 0
    found: dict[str, int] = {}
    for phrase in _CLICHE_PHRASES:
        # Word-ish boundaries so 'in summary' etc. match as phrases.
        n = len(re.findall(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", low))
        if n:
            hits += n
            found[phrase] = n
    words = _word_count(text)
    per_1000 = (hits / words * 1000) if words else 0.0
    return {"hits": hits, "per_1000_words": round(per_1000, 2), "phrases": found}


# Hedging markers (IT + EN): overuse ("può/potrebbe" stacking) reads as
# noncommittal AI prose. Matched as whole words/phrases, case-insensitive.
_HEDGE_PHRASES: tuple[str, ...] = (
    # Italian
    "può",
    "potrebbe",
    "potrebbero",
    "possono",
    "forse",
    "in qualche modo",
    "probabilmente",
    # English
    "may",
    "might",
    "could",
    "perhaps",
    "possibly",
)


def hedging_density(text: str, language: str = "en") -> dict[str, Any]:
    """Hedge-word hits per 1000 words (lower = more assertive prose).

    Report-only this wave — feeds tuning with data before any gating.
    Same shape as connector_cliche_density.
    """
    low = (text or "").lower()
    hits = 0
    found: dict[str, int] = {}
    for phrase in _HEDGE_PHRASES:
        n = len(re.findall(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", low))
        if n:
            hits += n
            found[phrase] = n
    words = _word_count(text)
    per_1000 = (hits / words * 1000) if words else 0.0
    return {"hits": hits, "per_1000_words": round(per_1000, 2), "phrases": found}


def evidence_presence(text: str, pack: SourcePack | None = None) -> bool:
    """True if the section carries a concrete numeric detail.

    Delegates to text_utils.contains_concrete_evidence (shared with the
    grounding gate): citation years and section numbering do NOT count —
    the previous naive `\\d` check was satisfied by "1. Introduzione".
    When a pack is given, it is not required here — grounding is measured
    separately.
    """
    return contains_concrete_evidence(text)


def citation_grounding_rate(
    section_result: dict[str, Any],
    pack: SourcePack,
    *,
    min_on_topic_score: float = 0.35,
) -> float:
    """Fraction of a section's citations that resolve to on-topic pack sources."""
    result = evaluate_grounding(
        section_result,
        pack,
        min_grounding_rate=0.0,  # scoring only; no pass/fail here
        require_evidence=False,
        min_on_topic_score=min_on_topic_score,
    )
    return round(result.grounding_rate, 3)


def outline_adherence(
    promised: list[dict[str, Any]],
    delivered: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare promised outline sections vs delivered sections.

    promised: outline["sections"] dicts (title, estimated_words).
    delivered: dicts with 'title' and 'word_count' (or 'content').

    Returns counts, adherence ratio, and per-section word deltas.
    """
    promised_count = len(promised)
    delivered_count = len(delivered)
    adherence = 1.0 if promised_count == 0 else delivered_count / promised_count

    deltas = []
    for i, p in enumerate(promised):
        d = delivered[i] if i < len(delivered) else None
        est = int(p.get("estimated_words") or 0)
        got = 0
        if d is not None:
            got = int(d.get("word_count") or _word_count(d.get("content", "")))
        deltas.append(
            {
                "title": p.get("title"),
                "estimated_words": est,
                "delivered_words": got,
                "delivered": d is not None,
            }
        )

    return {
        "promised_sections": promised_count,
        "delivered_sections": delivered_count,
        "adherence": round(adherence, 3),
        "fully_delivered": delivered_count >= promised_count and promised_count > 0,
        "sections": deltas,
    }
