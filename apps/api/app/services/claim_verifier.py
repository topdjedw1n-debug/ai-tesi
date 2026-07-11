"""
Claim-faithfulness verifier for the Academic Quality Engine.

Before a section is accepted, checks via an LLM whether each cited sentence is
actually supported by the cited source's abstract. Verdict per claim:
supported / unsupported / uncertain + a one-sentence explanation.

Key properties:
- Abstract comes from DocumentSource.canonical_metadata (written by
  citation_verifier) with a fallback to the RAG-retrieved
  DocumentSource.abstract; without an abstract the claim is marked
  'uncertain' WITHOUT spending an LLM call.
- Budget-capped across the whole document, including rejected drafts and
  repair attempts. Capacity is durably reserved before each LLM call so a
  restart cannot reset the ceiling. Overflow is marked 'uncertain' and is a
  blocking technical gap in strict mode.
- Batched: multiple claims share one prompt (CLAIM_VERIFICATION_BATCH_SIZE),
  abstracts are deduplicated inside the prompt.
- Verdicts are recorded in the provenance ledger and
  DocumentSection.claim_verification. The caller decides whether unsupported
  claims are advisory or must be repaired before export.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.ai_pipeline.citation_formatter import CitationFormatter, CitationStyle
from app.services.ai_pipeline.citation_keys import internal_marker_groups

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
TECHNICAL_UNCERTAIN_REASONS = {
    REASON_BUDGET,
    REASON_LLM_FAILED,
    REASON_NO_SOURCE,
    REASON_NO_VERDICT,
}

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_HEADING_LINE = re.compile(r"^\s*#{1,6}\s")


# Source-pack citation keys, e.g. "[Ciofalo2024]" / "[DeSimone2024a]".
# No comma inside — disjoint from the legacy "[Author, Year]" format that
# CitationFormatter.extract_citations_from_text handles. Multiple keys may
# share one bracket pair: "[Ciofalo2024; Corsi2025]".
def _normalize_rendered_citation(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


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
        # This is the manager's drill-down evidence.  Truncating it made the
        # aggregate count honest while hiding the later uncertain claims.
        "claims": [v.to_dict() for v in verdicts],
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

    Legacy markers contain author(s) and year but no title. A matching year is
    therefore only a disambiguator: at least one cited author must match, and
    an explicit citation year must also match. This prevents a same-year paper
    by a different author from being attached to the claim.
    """
    best = None
    best_score = 0.0

    def _surname(author: str) -> str:
        normalized = (author or "").strip()
        if not normalized:
            return ""
        surname = (
            normalized.split(",", 1)[0] if "," in normalized else normalized.split()[-1]
        )
        return re.sub(r"[^\w-]", "", surname, flags=re.UNICODE).casefold()

    for source in sources:
        cited_year = citation.get("year")
        if cited_year:
            try:
                if not source.year or int(cited_year) != int(source.year):
                    continue
            except (TypeError, ValueError):
                continue
        year_suffix = str(citation.get("year_suffix") or "")
        if year_suffix:
            citation_key = str(getattr(source, "citation_key", "") or "")
            if not citation_key.casefold().endswith(
                f"{cited_year}{year_suffix}".casefold()
            ):
                continue

        source_last_names = {
            surname
            for author in (source.authors or [])
            if (surname := _surname(author))
        }
        author_score = 0.0
        for cited_author in citation.get("authors") or []:
            cited_last = _surname(cited_author)
            if not cited_last:
                continue
            if cited_last in source_last_names:
                author_score += 30.0

        # A year by itself carries no identity evidence. Legacy citations do
        # not contain a title, so author overlap is mandatory.
        if author_score == 0:
            continue

        score = author_score + (50.0 if cited_year else 0.0)

        if score > best_score:
            best_score = score
            best = source
    return best


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

    def extract_claims(
        self,
        content: str,
        sources: list[Any],
        *,
        citation_style: CitationStyle = CitationStyle.APA,
    ) -> list[CitedClaim]:
        """
        Extract sentences carrying citations and match each citation to a
        persisted source (one claim per sentence-citation pair).

        Two citation formats are recognised:
        - source-pack keys "[Ciofalo2024]" (the grounded production path),
          matched exactly against DocumentSource.citation_key;
        - legacy "[Author, Year]", matched by author/year scoring.
        """
        claims: list[CitedClaim] = []
        key_index = {
            str(getattr(source, "citation_key", "") or "").casefold(): source
            for source in sources
            if getattr(source, "citation_key", None)
        }
        rendered_index: dict[str, list[Any]] = {}
        for source in sources:
            if not source.authors or not source.year:
                continue
            citation_key = str(getattr(source, "citation_key", "") or "")
            suffix_match = re.search(r"\d{1,4}([a-z]+)$", citation_key, re.IGNORECASE)
            rendered = CitationFormatter.format_intext(
                list(source.authors or []),
                int(source.year),
                style=citation_style,
                year_suffix=(suffix_match.group(1) if suffix_match else ""),
            )
            inner = rendered[1:-1] if rendered[:1] in "([" else rendered
            rendered_index.setdefault(_normalize_rendered_citation(inner), []).append(
                source
            )

        for sentence in split_sentences(content):
            seen_claims: set[tuple[int | None, str]] = set()

            def append_claim(
                citation_text: str,
                source: Any | None,
                *,
                sentence_text: str = sentence,
                seen: set[tuple[int | None, str]] = seen_claims,
            ) -> None:
                identity = (getattr(source, "id", None), citation_text.casefold())
                if identity in seen:
                    return
                seen.add(identity)
                claims.append(
                    CitedClaim(
                        sentence=sentence_text,
                        citation_text=citation_text,
                        source_id=getattr(source, "id", None) if source else None,
                        source_title=source.title if source else None,
                        abstract=_source_abstract(source) if source else None,
                    )
                )

            # Source-pack keys first: the production (grounded) format
            for _marker, marker_keys in internal_marker_groups(sentence):
                for key in marker_keys:
                    source = key_index.get(key.casefold())
                    append_claim(f"[{key}]", source)

            # Match the exact user-facing citation strings produced by the
            # selected style. This covers APA, MLA, Chicago and Harvard,
            # including multi-source parenthetical groups.
            for group in re.finditer(r"[\[(]([^\]\)\n]+)[\])]", sentence):
                for part in group.group(1).split(";"):
                    normalized = _normalize_rendered_citation(part)
                    matches = rendered_index.get(normalized, [])
                    if len(matches) == 1:
                        append_claim(
                            f"{group.group(0)[0]}{part.strip()}{group.group(0)[-1]}",
                            matches[0],
                        )

            # Legacy variations that are not byte-identical to the formatter.
            citations = CitationFormatter.extract_citations_from_text(sentence)
            for citation in citations:
                source = _match_source(citation, sources)
                append_claim(citation["original"], source)
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
            batch_claims = [claim for _, claim in batch]
            expected_sources = dict(
                enumerate(self._batch_source_labels(batch_claims), start=1)
            )
            # Budget counts claims SENT to the LLM (even on failure) so a
            # flaky provider cannot turn the cap into a retry storm.
            llm_used += len(batch)

            parsed: dict[int, tuple[str, str]] = {}
            llm_call_failed = False
            try:
                response = await self.ai_service.call_with_fallback(
                    self._build_batch_prompt(batch_claims),
                    purpose="claim_verification",
                )
                parsed = self._parse_batch_response(response, expected_sources)
            except Exception as e:
                llm_call_failed = True
                logger.warning(
                    f"⚠️ Claim verification LLM call failed ({len(batch)} claim(s)): {e}"
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
                    reason = REASON_LLM_FAILED if llm_call_failed else REASON_NO_VERDICT
                    verdicts[index] = self._uncertain(claim, reason)

        return [verdicts[index] for index in range(len(claims))], llm_used

    # ------------------------------------------------------------------
    # Prompt building / response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _batch_source_labels(batch: list[CitedClaim]) -> list[str]:
        """Return the exact S-label assigned to each claim in prompt order."""
        labels: dict[Any, str] = {}
        assigned: list[str] = []
        for claim in batch:
            key = claim.source_id if claim.source_id is not None else claim.source_title
            if key not in labels:
                labels[key] = f"S{len(labels) + 1}"
            assigned.append(labels[key])
        return assigned

    def _build_batch_prompt(self, batch: list[CitedClaim]) -> str:
        """One prompt for a batch of claims; abstracts deduplicated as S1..Sn"""
        assigned_labels = self._batch_source_labels(batch)
        source_blocks: list[str] = []
        claim_lines: list[str] = []
        emitted_sources: set[str] = set()

        for position, (claim, source_label) in enumerate(
            zip(batch, assigned_labels, strict=True), start=1
        ):
            if source_label not in emitted_sources:
                emitted_sources.add(source_label)
                abstract = (claim.abstract or "")[: self.abstract_max_chars]
                source_blocks.append(
                    f"[{source_label}] {claim.source_title or 'Unknown source'}\n"
                    f"Abstract: {abstract}"
                )
            claim_lines.append(
                f"{position}. (source {source_label}: "
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
    def _parse_batch_response(
        response: Any,
        expected_sources: dict[int, str],
    ) -> dict[int, tuple[str, str]]:
        """
        Parse the LLM response into {claim position -> (verdict, explanation)}.

        AIService returns either the parsed JSON keys directly (model emitted
        valid JSON) or {"content": "<raw text>"}; both shapes are handled.
        An entry is trusted only when its id is unique and in range, and its
        source label exactly matches the label assigned to that claim in the
        prompt. Invalid, duplicate, or missing entries are dropped so callers
        record a technical no-verdict rather than an LLM-checked judgement.
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
        seen_positions: set[int] = set()
        duplicate_positions: set[int] = set()
        for item in verdicts_raw or []:
            if not isinstance(item, dict):
                continue
            raw_position = item.get("id")
            if isinstance(raw_position, bool) or not isinstance(raw_position, int):
                continue
            position = raw_position
            if position not in expected_sources:
                continue
            if position in seen_positions:
                duplicate_positions.add(position)
                result.pop(position, None)
                continue
            seen_positions.add(position)

            if item.get("source") != expected_sources[position]:
                continue
            verdict = str(item.get("verdict", "")).strip().lower()
            if verdict not in VALID_VERDICTS:
                continue
            raw_explanation = item.get("explanation")
            if not isinstance(raw_explanation, str) or not raw_explanation.strip():
                continue
            explanation = raw_explanation.strip()[:300]
            result[position] = (verdict, explanation)
        for position in duplicate_positions:
            result.pop(position, None)
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
