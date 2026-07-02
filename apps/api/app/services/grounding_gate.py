"""
In-loop grounding gate (Academic Quality Engine).

Runs inside the per-section regeneration loop, AFTER a section is generated and
BEFORE it is humanized, so ungrounded or off-topic citations trigger bounded
regeneration instead of being polished and shipped. All checks are local (no
LLM, no external call): a section's in-text citations are scored against the
upfront topic-locked source pack.

This module is pure/stateless; the orchestrator (background_jobs) owns the
regenerate-vs-accept decision and the config flags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.services.ai_pipeline.text_utils import contains_concrete_evidence

if TYPE_CHECKING:
    from app.services.ai_pipeline.source_pack import SourcePack

# Bracketed citation groups, e.g. "[Rossi2021, 2021]" or "[Smith2020; Lee2019]".
_BRACKET_RE = re.compile(r"\[([^\[\]]{1,160})\]")


@dataclass
class GroundingResult:
    """Outcome of scoring a section's citations against the source pack."""

    passed: bool
    grounding_rate: float
    total_citations: int
    grounded_citations: int
    offending_keys: list[str] = field(default_factory=list)
    reason: str = ""


def _citation_candidates(content: str) -> list[str]:
    """Extract citation-key candidates from in-text bracketed citations.

    A bracket may hold several keys (comma/semicolon separated). Pure-year
    tokens (no letter) are ignored; each remaining part yields one candidate.
    """
    candidates: list[str] = []
    for group in _BRACKET_RE.findall(content or ""):
        for part in re.split(r"[;,]", group):
            token_match = re.match(r"\s*(\S+)", part)
            if not token_match:
                continue
            token = token_match.group(1)
            # Drop surrounding punctuation; require at least one letter so we
            # skip bare years like "[2021]" and non-citation brackets.
            cleaned = re.sub(r"^[^0-9A-Za-z]+|[^0-9A-Za-z]+$", "", token)
            if cleaned and re.search(r"[A-Za-z]", cleaned):
                candidates.append(cleaned)
    return candidates


def evaluate_grounding(
    section_result: dict[str, Any],
    pack: SourcePack,
    *,
    min_grounding_rate: float = 0.8,
    require_evidence: bool = True,
    min_on_topic_score: float = 0.35,
) -> GroundingResult:
    """
    Score a generated section's citations against the topic-locked source pack.

    A citation is *grounded* when its key resolves to a pack source whose
    on_topic_score >= min_on_topic_score. Any citation whose key is absent from
    the pack (invented) or resolves to a below-threshold source (off-topic) is
    counted as ungrounded and reported in offending_keys.

    passed = grounding_rate >= min_grounding_rate AND (evidence satisfied), where
    evidence (when require_evidence is set) means BOTH at least one grounded
    citation AND a concrete detail in the prose: a numeric fact (percentages,
    decimals, multi-digit numbers — citation years and section numbering
    excluded) OR a named system/technology/case (see
    text_utils.contains_concrete_evidence). The reason string distinguishes the
    failure modes so regeneration feedback can be targeted.
    """
    content = section_result.get("content", "") or ""
    pack_scores = {ps.citation_key.lower(): ps.on_topic_score for ps in pack.sources}

    candidates = _citation_candidates(content)
    total = len(candidates)
    grounded = 0
    offending: list[str] = []

    for cand in candidates:
        score = pack_scores.get(cand.lower())
        if score is not None and score >= min_on_topic_score:
            grounded += 1
        else:
            offending.append(cand)

    # Rate over zero citations is vacuously 1.0; the evidence check (below)
    # still fails an uncited section when require_evidence is set.
    grounding_rate = 1.0 if total == 0 else grounded / total

    passed = grounding_rate >= min_grounding_rate
    reason = ""
    if not passed:
        reason = (
            f"grounding rate {grounding_rate:.2f} < {min_grounding_rate:.2f}; "
            f"ungrounded: {sorted(set(offending))[:10]}"
        )
    elif require_evidence:
        if grounded < 1:
            passed = False
            reason = "no grounded citation in section"
        elif not contains_concrete_evidence(content):
            passed = False
            reason = (
                "no concrete evidence in section (no statistic, numeric "
                "finding, specific figure, or named system/case outside "
                "citations/numbering)"
            )

    return GroundingResult(
        passed=passed,
        grounding_rate=grounding_rate,
        total_citations=total,
        grounded_citations=grounded,
        offending_keys=sorted(set(offending)),
        reason=reason,
    )
