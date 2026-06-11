"""
Claim-faithfulness verifier (advisory pass) for the Academic Quality Engine.

After sections are generated and cited sources verified, checks via an LLM
whether each sentence carrying an [Author, Year] citation is actually
supported by the cited source's abstract. Verdict per claim:
supported / unsupported / uncertain + a one-sentence explanation.

Key properties:
- Abstract comes from DocumentSource.canonical_metadata (written by
  citation_verifier) with a fallback to the RAG-retrieved
  DocumentSource.abstract; without an abstract the claim is marked
  'uncertain' WITHOUT spending an LLM call.
- Budget-capped: at most CLAIM_VERIFICATION_MAX_CHECKS claims per document
  are sent to the LLM; the rest are marked 'uncertain'.
- Batched: multiple claims share one prompt (CLAIM_VERIFICATION_BATCH_SIZE),
  abstracts are deduplicated inside the prompt.
- Advisory only: verdicts are recorded (provenance ledger +
  DocumentSection.claim_verification) and never block the pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.ai_pipeline.citation_formatter import CitationFormatter

logger = logging.getLogger(__name__)

VERDICT_SUPPORTED = "supported"
VERDICT_UNSUPPORTED = "unsupported"
VERDICT_UNCERTAIN = "uncertain"
VALID_VERDICTS = {VERDICT_SUPPORTED, VERDICT_UNSUPPORTED, VERDICT_UNCERTAIN}

# Reasons for uncertain verdicts that skip the LLM entirely
REASON_NO_ABSTRACT = "No abstract available for the cited source"
REASON_NO_SOURCE = "Citation could not be matched to a verified source"
REASON_BUDGET = "Per-document claim check budget exhausted"
REASON_LLM_FAILED = "LLM claim check failed"
REASON_NO_VERDICT = "LLM did not return a verdict for this claim"

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_HEADING_LINE = re.compile(r"^\s*#{1,6}\s")


@dataclass
class CitedClaim:
    """One sentence + one citation it carries, matched to a persisted source"""

    sentence: str
    citation_text: str  # original marker, e.g. "[Vaswani, 2017]"
    source_id: int | None
    source_title: str | None
    abstract: str | None


@dataclass
class ClaimVerdict:
    """Verdict for one cited claim"""

    sentence: str
    citation_text: str
    source_id: int | None
    source_title: str | None
    verdict: str  # supported / unsupported / uncertain
    explanation: str
    checked_by_llm: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentence": self.sentence[:300],
            "citation": self.citation_text,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "verdict": self.verdict,
            "explanation": self.explanation[:300],
            "checked_by_llm": self.checked_by_llm,
        }


def split_sentences(text: str) -> list[str]:
    """Split section content into sentences (markdown headings dropped)"""
    sentences: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph or _HEADING_LINE.match(paragraph):
            continue
        for sentence in _SENTENCE_BOUNDARY.split(paragraph):
            sentence = sentence.strip()
            if sentence:
                sentences.append(sentence)
    return sentences


def summarize_verdicts(verdicts: list[ClaimVerdict]) -> dict[str, Any]:
    """Build the JSON summary stored in DocumentSection.claim_verification"""
    counts: dict[str, int] = {}
    for verdict in verdicts:
        counts[verdict.verdict] = counts.get(verdict.verdict, 0) + 1
    return {
        "total": len(verdicts),
        "checked": sum(1 for v in verdicts if v.checked_by_llm),
        "counts": counts,
        "claims": [v.to_dict() for v in verdicts[:50]],
    }


def _source_abstract(source: Any) -> str | None:
    """
    Abstract for a persisted source: canonical_metadata first (written by
    citation_verifier), falling back to the RAG-retrieved abstract.
    """
    canonical = getattr(source, "canonical_metadata", None) or {}
    abstract = canonical.get("abstract") if isinstance(canonical, dict) else None
    if not abstract:
        abstract = getattr(source, "abstract", None)
    if not abstract or not str(abstract).strip():
        return None
    return str(abstract).strip()


def _match_source(citation: dict[str, Any], sources: list[Any]) -> Any | None:
    """
    Match an extracted citation to a persisted DocumentSource.

    Same idea as SectionGenerator's citation matching: exact year +50,
    author last-name overlap +30 per citation author. Best score > 0 wins.
    """
    best = None
    best_score = 0.0
    for source in sources:
        score = 0.0
        if citation.get("year") and source.year:
            try:
                if int(citation["year"]) == int(source.year):
                    score += 50.0
            except (TypeError, ValueError):
                pass

        source_last_names = [
            author.strip().split()[-1].lower()
            for author in (source.authors or [])
            if author and author.strip()
        ]
        for cited_author in citation.get("authors") or []:
            cited_author = (cited_author or "").strip()
            if not cited_author:
                continue
            cited_last = cited_author.split()[-1].lower()
            if any(
                cited_last in source_last or source_last in cited_last
                for source_last in source_last_names
            ):
                score += 30.0

        if score > best_score:
            best_score = score
            best = source
    return best if best_score > 0 else None


class ClaimVerifier:
    """LLM-backed claim-faithfulness checker (see module docstring)"""

    def __init__(
        self,
        ai_service: Any,
        *,
        batch_size: int | None = None,
        abstract_max_chars: int | None = None,
    ):
        """
        Args:
            ai_service: object exposing async call_with_fallback(prompt, purpose)
                (app.services.ai_service.AIService)
            batch_size: Claims per LLM prompt. Defaults to Settings.
            abstract_max_chars: Max abstract chars per source in prompts.
                Defaults to Settings.
        """
        self.ai_service = ai_service
        self.batch_size = max(
            1,
            int(
                batch_size
                if batch_size is not None
                else settings.CLAIM_VERIFICATION_BATCH_SIZE
            ),
        )
        self.abstract_max_chars = max(
            1,
            int(
                abstract_max_chars
                if abstract_max_chars is not None
                else settings.CLAIM_ABSTRACT_MAX_CHARS
            ),
        )

    # ------------------------------------------------------------------
    # Claim extraction (pure, no LLM)
    # ------------------------------------------------------------------

    def extract_claims(self, content: str, sources: list[Any]) -> list[CitedClaim]:
        """
        Extract sentences carrying [Author, Year] citations and match each
        citation to a persisted source (one claim per sentence-citation pair).
        """
        claims: list[CitedClaim] = []
        for sentence in split_sentences(content):
            citations = CitationFormatter.extract_citations_from_text(sentence)
            for citation in citations:
                source = _match_source(citation, sources)
                claims.append(
                    CitedClaim(
                        sentence=sentence,
                        citation_text=citation["original"],
                        source_id=getattr(source, "id", None) if source else None,
                        source_title=source.title if source else None,
                        abstract=_source_abstract(source) if source else None,
                    )
                )
        return claims

    # ------------------------------------------------------------------
    # Verification (LLM, budget-capped, batched)
    # ------------------------------------------------------------------

    async def verify_claims(
        self, claims: list[CitedClaim], budget: int
    ) -> tuple[list[ClaimVerdict], int]:
        """
        Verify claims against their source abstracts.

        Args:
            claims: extracted claims (order preserved in the result)
            budget: how many claims may still be sent to the LLM
                (document-level budget remainder)

        Returns:
            (verdicts in claim order, number of claims that consumed budget)

        Never raises: LLM failures degrade to 'uncertain' verdicts.
        """
        verdicts: dict[int, ClaimVerdict] = {}
        eligible: list[tuple[int, CitedClaim]] = []

        for index, claim in enumerate(claims):
            if claim.source_id is None and claim.source_title is None:
                verdicts[index] = self._uncertain(claim, REASON_NO_SOURCE)
            elif not claim.abstract:
                # Task contract: no abstract -> uncertain WITHOUT an LLM call
                verdicts[index] = self._uncertain(claim, REASON_NO_ABSTRACT)
            else:
                eligible.append((index, claim))

        budget = max(0, budget)
        within_budget = eligible[:budget]
        for index, claim in eligible[budget:]:
            verdicts[index] = self._uncertain(claim, REASON_BUDGET)

        llm_used = 0
        for start in range(0, len(within_budget), self.batch_size):
            batch = within_budget[start : start + self.batch_size]
            # Budget counts claims SENT to the LLM (even on failure) so a
            # flaky provider cannot turn the cap into a retry storm.
            llm_used += len(batch)

            parsed: dict[int, tuple[str, str]] = {}
            try:
                response = await self.ai_service.call_with_fallback(
                    self._build_batch_prompt([claim for _, claim in batch]),
                    purpose="claim_verification",
                )
                parsed = self._parse_batch_response(response)
            except Exception as e:
                logger.warning(
                    f"⚠️ Claim verification LLM call failed "
                    f"({len(batch)} claim(s)): {e}"
                )

            for position, (index, claim) in enumerate(batch, start=1):
                if position in parsed:
                    verdict, explanation = parsed[position]
                    verdicts[index] = ClaimVerdict(
                        sentence=claim.sentence,
                        citation_text=claim.citation_text,
                        source_id=claim.source_id,
                        source_title=claim.source_title,
                        verdict=verdict,
                        explanation=explanation,
                        checked_by_llm=True,
                    )
                else:
                    reason = REASON_LLM_FAILED if not parsed else REASON_NO_VERDICT
                    verdicts[index] = self._uncertain(claim, reason)

        return [verdicts[index] for index in range(len(claims))], llm_used

    # ------------------------------------------------------------------
    # Prompt building / response parsing
    # ------------------------------------------------------------------

    def _build_batch_prompt(self, batch: list[CitedClaim]) -> str:
        """One prompt for a batch of claims; abstracts deduplicated as S1..Sn"""
        labels: dict[Any, str] = {}
        source_blocks: list[str] = []
        claim_lines: list[str] = []

        for position, claim in enumerate(batch, start=1):
            key = claim.source_id if claim.source_id is not None else claim.source_title
            if key not in labels:
                labels[key] = f"S{len(labels) + 1}"
                abstract = (claim.abstract or "")[: self.abstract_max_chars]
                source_blocks.append(
                    f"[{labels[key]}] {claim.source_title or 'Unknown source'}\n"
                    f"Abstract: {abstract}"
                )
            claim_lines.append(
                f"{position}. (source {labels[key]}: "
                f'"{claim.source_title or "Unknown source"}") "{claim.sentence}"'
            )

        sources_text = "\n\n".join(source_blocks)
        claims_text = "\n".join(claim_lines)
        return f"""You are an academic fact-checking assistant. For each numbered claim below, decide whether the claim is supported by the abstract of the ONE source it cites.

Rules:
- Judge each claim ONLY against the abstract of its named source. Each claim names exactly one source (e.g. "source S2"); abstracts of OTHER sources in this prompt and your own background knowledge are irrelevant. If your explanation refers to content from a different source than the named one, your verdict is invalid.
- Apply these steps IN ORDER and stop at the first that fits:
  1. The named source's abstract is about a different subject or has no meaningful connection to the claim -> "unsupported".
  2. The abstract states the opposite of the claim -> "unsupported".
  3. The abstract directly states or clearly entails the claim -> "supported".
  4. The abstract is on the same topic but does not state the specific information the claim asserts (exact numbers, other populations or domains, predictions, outcomes it never measured) -> "uncertain".
- Consistency check: if your explanation says the abstract "does not state/specify/mention/provide" the claimed detail while being on the same topic, the verdict MUST be "uncertain", not "unsupported".

Calibration examples:
- Claim: "The drug reduced mortality by 30%" / abstract only says it reduced mortality -> "uncertain" (specific number never stated).
- Claim: "The drug reduced mortality" / abstract says it had no effect on mortality -> "unsupported" (contradiction).
- Claim: "The drug reduced mortality" / abstract is about crop irrigation -> "unsupported" (unrelated topic, NOT uncertain).

SOURCES:
{sources_text}

CLAIMS:
{claims_text}

Respond with ONLY valid JSON (no markdown, no extra text), one entry per claim. In each entry repeat the named source label, then give the verdict and a one-sentence explanation based on that source's abstract only:
{{"verdicts": [{{"id": 1, "source": "S1", "verdict": "supported", "explanation": "<one sentence>"}}]}}"""

    @staticmethod
    def _parse_batch_response(response: Any) -> dict[int, tuple[str, str]]:
        """
        Parse the LLM response into {claim position -> (verdict, explanation)}.

        AIService returns either the parsed JSON keys directly (model emitted
        valid JSON) or {"content": "<raw text>"}; both shapes are handled.
        Invalid entries are dropped (callers mark those claims 'uncertain').
        """
        verdicts_raw: list[Any] | None = None
        if isinstance(response, dict):
            if isinstance(response.get("verdicts"), list):
                verdicts_raw = response["verdicts"]
            elif isinstance(response.get("content"), str):
                match = re.search(r"\{.*\}", response["content"], re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                        if isinstance(parsed, dict) and isinstance(
                            parsed.get("verdicts"), list
                        ):
                            verdicts_raw = parsed["verdicts"]
                    except json.JSONDecodeError:
                        pass

        result: dict[int, tuple[str, str]] = {}
        for item in verdicts_raw or []:
            if not isinstance(item, dict):
                continue
            try:
                position = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            verdict = str(item.get("verdict", "")).strip().lower()
            if verdict not in VALID_VERDICTS:
                verdict = VERDICT_UNCERTAIN
            explanation = str(item.get("explanation") or "").strip()[:300]
            result[position] = (verdict, explanation)
        return result

    @staticmethod
    def _uncertain(claim: CitedClaim, reason: str) -> ClaimVerdict:
        return ClaimVerdict(
            sentence=claim.sentence,
            citation_text=claim.citation_text,
            source_id=claim.source_id,
            source_title=claim.source_title,
            verdict=VERDICT_UNCERTAIN,
            explanation=reason,
            checked_by_llm=False,
        )
