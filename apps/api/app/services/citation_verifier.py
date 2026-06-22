"""
Deterministic citation/source existence verification (Academic Quality Engine).

Verifies that cited sources actually exist by querying free bibliographic
REST APIs in a cascade: Crossref (DOI lookup first when a DOI is present),
then title search across Crossref -> OpenAlex -> Semantic Scholar -> arXiv.
Rule-based matching only (no LLM): normalized-title comparison via
difflib.SequenceMatcher plus a publication-year gate.

Self-contained service: NOT wired into the generation pipeline yet.
CITATION_VERIFICATION_ENABLED / CITATION_VERIFICATION_POLICY are read by the
integration layer (next step), not here.

Status vocabulary {verified, not_found, unresolvable} is intentionally
narrower than DocumentSource.verification_status; mapping (e.g.
unresolvable -> failed, low match_score -> mismatched) happens at
integration time using the match_score and canonical doi fields.

Note on shared utilities: RetryStrategy (app/services/retry_strategy.py) is
not reused because it retries on bare Exception (a definitive HTTP 404 would
be retried) and raises after exhaustion, while this service must never
raise. CircuitBreaker holds its lock across the awaited call, serializing
requests beyond what the per-provider rate limits require.

Concurrency contract: create one CitationVerifier instance per event loop
(asyncio primitives and the lazily created Redis client bind to the loop
they are first used on).

Original implementation. Ideas (deterministic verification via free
bibliographic APIs) follow public API documentation; no code, prompts or
text copied from CC BY-NC licensed sources.
"""

import asyncio
import hashlib
import html
import json
import logging
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum

import httpx
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

CACHE_PREFIX = "citation_verify"
CACHE_SCHEMA_VERSION = 1
CACHE_TTL_SECONDS = 90 * 24 * 3600  # 90 days
FUZZY_MATCH_THRESHOLD = 0.90
YEAR_TOLERANCE = 1
MAX_ABSTRACT_LENGTH = 2000  # cap stored in cache + canonical_metadata
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_RETRY_DELAYS = [1.0, 2.0, 4.0]
USER_AGENT = "Thesica-CitationVerifier/1.0"

PROVIDER_CROSSREF = "crossref"
PROVIDER_OPENALEX = "openalex"
PROVIDER_SEMANTIC_SCHOLAR = "semantic_scholar"
PROVIDER_ARXIV = "arxiv"
PROVIDERS = (
    PROVIDER_CROSSREF,
    PROVIDER_OPENALEX,
    PROVIDER_SEMANTIC_SCHOLAR,
    PROVIDER_ARXIV,
)

ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

_DOI_URL_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    UNRESOLVABLE = "unresolvable"


@dataclass
class SourceInput:
    """A cited source to verify. Identifiers (doi/arxiv_id) are optional."""

    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None


@dataclass
class VerificationResult:
    """Outcome of verifying one source. Canonical metadata set when VERIFIED."""

    status: VerificationStatus
    doi: str | None = None
    title: str | None = None
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    venue: str | None = None
    abstract: str | None = None  # capped at MAX_ABSTRACT_LENGTH
    provider: str | None = None  # crossref, openalex, semantic_scholar, arxiv
    match_score: float | None = None  # 1.0 exact/identifier; ratio for fuzzy
    from_cache: bool = False
    reason: str | None = None  # insufficient_metadata, provider_errors, ...

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "doi": self.doi,
            "title": self.title,
            "year": self.year,
            "authors": list(self.authors),
            "venue": self.venue,
            "abstract": self.abstract,
            "provider": self.provider,
            "match_score": self.match_score,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationResult":
        return cls(
            status=VerificationStatus(data["status"]),
            doi=data.get("doi"),
            title=data.get("title"),
            year=data.get("year"),
            authors=list(data.get("authors") or []),
            venue=data.get("venue"),
            # .get(): cache entries written before the abstract field existed
            abstract=data.get("abstract"),
            provider=data.get("provider"),
            match_score=data.get("match_score"),
            reason=data.get("reason"),
        )


def normalize_title(title: str | None) -> str:
    """Normalize a title for deterministic comparison.

    NFKD + strip combining marks (diacritics), lowercase, punctuation to
    spaces. Uses [^\\w\\s] (not [^a-z0-9]) so non-Latin titles survive.
    """
    if not title:
        return ""
    normalized = unicodedata.normalize("NFKD", title)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_doi(doi: str | None) -> str | None:
    """Lowercase, strip doi.org/dx.doi.org/doi: prefixes; None if not a DOI."""
    if not doi:
        return None
    normalized = doi.strip().lower()
    for prefix in _DOI_URL_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    normalized = normalized.strip()
    return normalized if normalized.startswith("10.") else None


def normalize_arxiv_id(arxiv_id: str | None) -> str | None:
    """Strip the arXiv: prefix and surrounding whitespace."""
    if not arxiv_id:
        return None
    normalized = arxiv_id.strip()
    if normalized.lower().startswith("arxiv:"):
        normalized = normalized[len("arxiv:") :].strip()
    return normalized or None


def _coerce_year(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _clean_abstract(text) -> str | None:
    """Collapse whitespace and cap at MAX_ABSTRACT_LENGTH; None if empty."""
    if not text or not isinstance(text, str):
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:MAX_ABSTRACT_LENGTH] if cleaned else None


def _strip_jats(value) -> str | None:
    """Crossref abstracts are JATS XML fragments: strip tags, unescape entities."""
    if not value or not isinstance(value, str):
        return None
    return html.unescape(re.sub(r"<[^>]+>", " ", value))


def _reconstruct_inverted_index(inverted) -> str | None:
    """Rebuild abstract text from OpenAlex's abstract_inverted_index
    ({word: [positions...]}); None for missing/malformed input."""
    if not inverted or not isinstance(inverted, dict):
        return None
    positions: list[tuple[int, str]] = []
    for word, indexes in inverted.items():
        if not isinstance(indexes, list | tuple):
            continue
        for index in indexes:
            if isinstance(index, int) and index >= 0:
                positions.append((index, word))
    if not positions:
        return None
    positions.sort()
    return " ".join(word for _, word in positions)


class _MinIntervalLimiter:
    """Spaces call starts at least 1/rps apart (FIFO via the lock).

    Sleeping while holding the lock is intentional: waiters queue up and
    each call start is spaced; the HTTP request itself runs outside.
    """

    def __init__(self, rps: float):
        self._interval = 1.0 / rps if rps > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next_allowed > now:
                await asyncio.sleep(self._next_allowed - now)
                now = time.monotonic()
            self._next_allowed = max(now, self._next_allowed) + self._interval


@dataclass
class _ProviderOutcome:
    """matched: candidate passed matching rules; errored: transport/5xx
    failure after retries (False + matched=None = clean no-match)."""

    matched: VerificationResult | None = None
    errored: bool = False


class CitationVerifier:
    """Deterministic source-existence verification across bibliographic APIs."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_delays: list[float] | None = None,
        max_concurrency: int | None = None,
        rate_limits_rps: dict[str, float] | None = None,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ):
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.CITATION_API_TIMEOUT_SECONDS
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else settings.CITATION_VERIFICATION_MAX_RETRIES
        )
        if retry_delays is None:
            retry_delays = DEFAULT_RETRY_DELAYS[: self.max_retries] or [1.0]
        self.retry_delays = retry_delays
        self.max_concurrency = (
            max_concurrency
            if max_concurrency is not None
            else settings.CITATION_VERIFICATION_MAX_CONCURRENCY
        )
        rps = {
            PROVIDER_CROSSREF: settings.CROSSREF_RATE_LIMIT_RPS,
            PROVIDER_OPENALEX: settings.OPENALEX_RATE_LIMIT_RPS,
            PROVIDER_SEMANTIC_SCHOLAR: settings.SEMANTIC_SCHOLAR_RATE_LIMIT_RPS,
            PROVIDER_ARXIV: settings.ARXIV_RATE_LIMIT_RPS,
        }
        if rate_limits_rps:
            rps.update(rate_limits_rps)
        # Instance-level (not module-level): test isolation + loop safety
        self._limiters = {p: _MinIntervalLimiter(r) for p, r in rps.items()}
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        self.cache_enabled = cache_enabled
        self.cache_ttl_seconds = cache_ttl_seconds
        self._redis = redis_client
        self._redis_init_failed = False
        self._cache_warned = False

        self.crossref_url = settings.CROSSREF_API_URL.rstrip("/")
        self.openalex_url = settings.OPENALEX_API_URL.rstrip("/")
        self.s2_url = settings.SEMANTIC_SCHOLAR_API_URL.rstrip("/")
        self.arxiv_url = settings.ARXIV_API_URL
        self.s2_api_key = settings.SEMANTIC_SCHOLAR_API_KEY

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def verify_sources(
        self, sources: list[SourceInput]
    ) -> list[VerificationResult]:
        """Verify a batch of sources; results align index-wise with inputs."""
        return list(await asyncio.gather(*(self._bounded_verify(s) for s in sources)))

    async def verify_source(self, source: SourceInput) -> VerificationResult:
        norm_doi = normalize_doi(source.doi)
        norm_arxiv = normalize_arxiv_id(source.arxiv_id)
        norm_title = normalize_title(source.title)

        if not (norm_doi or norm_arxiv or norm_title):
            return VerificationResult(
                status=VerificationStatus.UNRESOLVABLE,
                reason="insufficient_metadata",
            )

        cache_key = self._cache_key(norm_doi, norm_arxiv, norm_title, source.year)
        cached = await self._cache_get(cache_key)
        if cached is not None:
            return cached

        any_error = False
        result: VerificationResult | None = None

        # Phase 1: identifier lookups (authoritative when they hit).
        # A 404 on the DOI does not prove the work doesn't exist (typo or
        # hallucinated DOI) - fall through to title search, which returns
        # the canonical DOI.
        if norm_doi:
            outcome = await self._query_crossref_by_doi(norm_doi, norm_title)
            if outcome.matched:
                result = outcome.matched
            any_error = any_error or outcome.errored

        if result is None and norm_arxiv:
            outcome = await self._query_arxiv_by_id(norm_arxiv, norm_title)
            if outcome.matched:
                result = outcome.matched
            any_error = any_error or outcome.errored

        # Phase 2: title search cascade; first verified hit stops
        if result is None and norm_title:
            for search in (
                self._search_crossref,
                self._search_openalex,
                self._search_semantic_scholar,
                self._search_arxiv,
            ):
                outcome = await search(source, norm_title)
                if outcome.matched:
                    result = outcome.matched
                    break
                any_error = any_error or outcome.errored

        if result is not None:
            await self._cache_set(cache_key, result)
            return result
        if any_error:
            # Never cached: a transient outage must not poison the cache
            return VerificationResult(
                status=VerificationStatus.UNRESOLVABLE, reason="provider_errors"
            )
        result = VerificationResult(status=VerificationStatus.NOT_FOUND)
        await self._cache_set(cache_key, result)
        return result

    async def _bounded_verify(self, source: SourceInput) -> VerificationResult:
        async with self._semaphore:
            try:
                return await self.verify_source(source)
            except Exception as e:
                logger.error(f"Citation verification internal error: {e}")
                return VerificationResult(
                    status=VerificationStatus.UNRESOLVABLE, reason="internal_error"
                )

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _match_candidate(
        self, norm_title: str, source_year: int | None, candidate: dict
    ) -> float | None:
        """Score a candidate against the source; None if it doesn't match."""
        candidate_title = normalize_title(candidate.get("title"))
        if not candidate_title or not norm_title:
            return None
        if candidate_title == norm_title:
            score = 1.0
        else:
            score = SequenceMatcher(None, norm_title, candidate_title).ratio()
            if score < FUZZY_MATCH_THRESHOLD:
                return None
        candidate_year = candidate.get("year")
        if (
            source_year is not None
            and candidate_year is not None
            and abs(source_year - candidate_year) > YEAR_TOLERANCE
        ):
            return None
        return score

    def _best_candidate(
        self, source: SourceInput, norm_title: str, candidates: list[dict]
    ) -> tuple[dict, float] | None:
        best: dict | None = None
        best_score = 0.0
        for candidate in candidates:
            score = self._match_candidate(norm_title, source.year, candidate)
            if score is not None and score > best_score:
                best, best_score = candidate, score
        return (best, best_score) if best is not None else None

    def _identifier_score(self, norm_title: str, candidate: dict) -> float:
        """Score for identifier (DOI/arXiv id) hits: the identifier is
        authoritative that the work exists; the title similarity is carried
        in match_score so the integration layer can flag mismatches."""
        if not norm_title:
            return 1.0
        candidate_title = normalize_title(candidate.get("title"))
        if not candidate_title:
            return 0.0
        if candidate_title == norm_title:
            return 1.0
        return SequenceMatcher(None, norm_title, candidate_title).ratio()

    def _result_from_candidate(
        self, candidate: dict, provider: str, score: float
    ) -> VerificationResult:
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            doi=candidate.get("doi"),
            title=candidate.get("title"),
            year=candidate.get("year"),
            authors=list(candidate.get("authors") or []),
            venue=candidate.get("venue"),
            abstract=candidate.get("abstract"),
            provider=provider,
            match_score=round(score, 3),
        )

    # ------------------------------------------------------------------
    # HTTP with retry/backoff
    # ------------------------------------------------------------------

    async def _fetch(
        self,
        provider: str,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> tuple[str, httpx.Response | None]:
        """GET with per-provider rate limiting and exponential backoff.

        Returns ("ok", response) | ("not_found", None) | ("error", None).
        Never raises. Retries only timeouts/network errors/429/5xx; 404 is
        a definitive answer and other 4xx are definitive provider errors.
        """
        attempt = 0
        merged_headers = {"User-Agent": USER_AGENT}
        if headers:
            merged_headers.update(headers)
        while True:
            await self._limiters[provider].acquire()
            error: str
            retryable: bool
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.get(
                        url, params=params, headers=merged_headers
                    )
                if response.status_code == 404:
                    return "not_found", None
                response.raise_for_status()
                return "ok", response
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                retryable = status_code in RETRYABLE_STATUS
                error = f"HTTP {status_code}"
            except httpx.HTTPError as e:  # timeouts, network, protocol errors
                retryable = True
                error = f"{type(e).__name__}: {e}"
            except Exception as e:  # defensive: never crash the cascade
                retryable = False
                error = f"{type(e).__name__}: {e}"

            if retryable and attempt < self.max_retries:
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                logger.warning(
                    f"Citation API {provider} attempt {attempt + 1} failed "
                    f"({error}), retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            logger.warning(f"Citation API {provider} failed ({error}): {url}")
            return "error", None

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    async def _query_crossref_by_doi(
        self, norm_doi: str, norm_title: str
    ) -> _ProviderOutcome:
        status, response = await self._fetch(
            PROVIDER_CROSSREF, f"{self.crossref_url}/works/{norm_doi}"
        )
        if status == "error":
            return _ProviderOutcome(errored=True)
        if status == "not_found":
            return _ProviderOutcome()
        try:
            item = response.json().get("message") or {}
        except ValueError:
            return _ProviderOutcome(errored=True)
        candidate = self._parse_crossref_item(item)
        if not candidate.get("title"):
            return _ProviderOutcome()
        candidate["doi"] = candidate.get("doi") or norm_doi
        score = self._identifier_score(norm_title, candidate)
        return _ProviderOutcome(
            matched=self._result_from_candidate(candidate, PROVIDER_CROSSREF, score)
        )

    async def _search_crossref(
        self, source: SourceInput, norm_title: str
    ) -> _ProviderOutcome:
        status, response = await self._fetch(
            PROVIDER_CROSSREF,
            f"{self.crossref_url}/works",
            params={"query.bibliographic": norm_title, "rows": 5},
        )
        if status != "ok":
            return _ProviderOutcome(errored=(status == "error"))
        try:
            items = response.json().get("message", {}).get("items") or []
        except ValueError:
            return _ProviderOutcome(errored=True)
        candidates = [self._parse_crossref_item(i) for i in items]
        best = self._best_candidate(source, norm_title, candidates)
        if best is None:
            return _ProviderOutcome()
        candidate, score = best
        return _ProviderOutcome(
            matched=self._result_from_candidate(candidate, PROVIDER_CROSSREF, score)
        )

    async def _search_openalex(
        self, source: SourceInput, norm_title: str
    ) -> _ProviderOutcome:
        status, response = await self._fetch(
            PROVIDER_OPENALEX,
            f"{self.openalex_url}/works",
            params={"filter": f"title.search:{norm_title}", "per-page": 5},
        )
        if status != "ok":
            return _ProviderOutcome(errored=(status == "error"))
        try:
            works = response.json().get("results") or []
        except ValueError:
            return _ProviderOutcome(errored=True)
        candidates = [self._parse_openalex_work(w) for w in works]
        best = self._best_candidate(source, norm_title, candidates)
        if best is None:
            return _ProviderOutcome()
        candidate, score = best
        return _ProviderOutcome(
            matched=self._result_from_candidate(candidate, PROVIDER_OPENALEX, score)
        )

    async def _search_semantic_scholar(
        self, source: SourceInput, norm_title: str
    ) -> _ProviderOutcome:
        headers = {"x-api-key": self.s2_api_key} if self.s2_api_key else None
        status, response = await self._fetch(
            PROVIDER_SEMANTIC_SCHOLAR,
            f"{self.s2_url}/paper/search",
            params={
                "query": norm_title,
                "fields": "title,year,authors,venue,externalIds,abstract",
                "limit": 5,
            },
            headers=headers,
        )
        if status != "ok":
            return _ProviderOutcome(errored=(status == "error"))
        try:
            papers = response.json().get("data") or []
        except ValueError:
            return _ProviderOutcome(errored=True)
        candidates = [self._parse_s2_paper(p) for p in papers]
        best = self._best_candidate(source, norm_title, candidates)
        if best is None:
            return _ProviderOutcome()
        candidate, score = best
        return _ProviderOutcome(
            matched=self._result_from_candidate(
                candidate, PROVIDER_SEMANTIC_SCHOLAR, score
            )
        )

    async def _query_arxiv_by_id(
        self, norm_arxiv: str, norm_title: str
    ) -> _ProviderOutcome:
        status, response = await self._fetch(
            PROVIDER_ARXIV,
            self.arxiv_url,
            params={"id_list": norm_arxiv, "max_results": 1},
        )
        if status != "ok":
            return _ProviderOutcome(errored=(status == "error"))
        entries = self._parse_arxiv_feed(response.text)
        if entries is None:
            return _ProviderOutcome(errored=True)
        for candidate in entries:
            # Invalid ids yield an entry without usable fields - skip
            title = candidate.get("title")
            if not title or title.strip().lower() == "error":
                continue
            score = self._identifier_score(norm_title, candidate)
            return _ProviderOutcome(
                matched=self._result_from_candidate(candidate, PROVIDER_ARXIV, score)
            )
        return _ProviderOutcome()

    async def _search_arxiv(
        self, source: SourceInput, norm_title: str
    ) -> _ProviderOutcome:
        status, response = await self._fetch(
            PROVIDER_ARXIV,
            self.arxiv_url,
            params={"search_query": f'ti:"{norm_title}"', "max_results": 5},
        )
        if status != "ok":
            return _ProviderOutcome(errored=(status == "error"))
        entries = self._parse_arxiv_feed(response.text)
        if entries is None:
            return _ProviderOutcome(errored=True)
        best = self._best_candidate(source, norm_title, entries)
        if best is None:
            return _ProviderOutcome()
        candidate, score = best
        return _ProviderOutcome(
            matched=self._result_from_candidate(candidate, PROVIDER_ARXIV, score)
        )

    # ------------------------------------------------------------------
    # Response parsers (defensive: malformed candidates are skipped)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_crossref_item(item: dict) -> dict:
        titles = item.get("title") or []  # Crossref title is a list
        year = None
        for date_field in ("issued", "published-print", "published-online"):
            date_parts = (item.get(date_field) or {}).get("date-parts") or [[]]
            if date_parts and date_parts[0]:
                year = _coerce_year(date_parts[0][0])
                if year is not None:
                    break
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in item.get("author") or []
        ]
        venues = item.get("container-title") or []
        return {
            "title": titles[0] if titles else None,
            "year": year,
            "authors": [a for a in authors if a],
            "venue": venues[0] if venues else None,
            "doi": normalize_doi(item.get("DOI")),
            "abstract": _clean_abstract(_strip_jats(item.get("abstract"))),
        }

    @staticmethod
    def _parse_openalex_work(work: dict) -> dict:
        location = work.get("primary_location") or {}
        source_info = location.get("source") or {}
        authors = [
            (a.get("author") or {}).get("display_name")
            for a in work.get("authorships") or []
        ]
        return {
            "title": work.get("title") or work.get("display_name"),
            "year": _coerce_year(work.get("publication_year")),
            "authors": [a for a in authors if a],
            "venue": source_info.get("display_name"),
            # OpenAlex returns the DOI as a full https://doi.org/... URL
            "doi": normalize_doi(work.get("doi")),
            "abstract": _clean_abstract(
                _reconstruct_inverted_index(work.get("abstract_inverted_index"))
            ),
        }

    @staticmethod
    def _parse_s2_paper(paper: dict) -> dict:
        external_ids = paper.get("externalIds") or {}
        authors = [a.get("name") for a in paper.get("authors") or []]
        return {
            "title": paper.get("title"),
            "year": _coerce_year(paper.get("year")),
            "authors": [a for a in authors if a],
            "venue": paper.get("venue"),
            "doi": normalize_doi(external_ids.get("DOI")),
            "abstract": _clean_abstract(paper.get("abstract")),
        }

    @staticmethod
    def _parse_arxiv_feed(xml_text: str) -> list[dict] | None:
        """Parse an arXiv Atom feed into candidate dicts; None on parse error."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None
        candidates = []
        for entry in root.findall("atom:entry", ARXIV_NS):
            title_el = entry.find("atom:title", ARXIV_NS)
            title = (
                re.sub(r"\s+", " ", title_el.text).strip()
                if title_el is not None and title_el.text
                else None
            )
            published_el = entry.find("atom:published", ARXIV_NS)
            year = (
                _coerce_year(published_el.text[:4])
                if published_el is not None and published_el.text
                else None
            )
            authors = [
                name.text.strip()
                for name in entry.findall("atom:author/atom:name", ARXIV_NS)
                if name.text
            ]
            doi_el = entry.find("arxiv:doi", ARXIV_NS)
            doi = normalize_doi(doi_el.text) if doi_el is not None else None
            summary_el = entry.find("atom:summary", ARXIV_NS)
            abstract = _clean_abstract(
                summary_el.text if summary_el is not None else None
            )
            candidates.append(
                {
                    "title": title,
                    "year": year,
                    "authors": authors,
                    "venue": "arXiv",
                    "doi": doi,
                    "abstract": abstract,
                }
            )
        return candidates

    # ------------------------------------------------------------------
    # Redis cache (read-through/write-through; failures never propagate)
    # ------------------------------------------------------------------

    def _cache_key(
        self,
        norm_doi: str | None,
        norm_arxiv: str | None,
        norm_title: str,
        year: int | None,
    ) -> str:
        if norm_doi:
            return f"{CACHE_PREFIX}:doi:{norm_doi}"
        if norm_arxiv:
            # Version-agnostic: 1706.03762v3 and v1 are the same work
            versionless = re.sub(r"v\d+$", "", norm_arxiv)
            return f"{CACHE_PREFIX}:arxiv:{versionless}"
        digest = hashlib.sha256(f"{norm_title}:{year or ''}".encode()).hexdigest()
        return f"{CACHE_PREFIX}:title:{digest}"

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis is not None:
            return self._redis
        if not self.cache_enabled or self._redis_init_failed:
            return None
        try:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            return self._redis
        except Exception as e:
            self._redis_init_failed = True
            self._warn_cache(f"Redis unavailable, caching disabled: {e}")
            return None

    async def _cache_get(self, key: str) -> VerificationResult | None:
        if not self.cache_enabled:
            return None
        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            raw = await redis.get(key)
        except Exception as e:
            self._warn_cache(f"Redis read failed: {e}")
            return None
        if not raw:
            return None
        try:
            result = VerificationResult.from_dict(json.loads(raw))
        except (ValueError, KeyError, TypeError):
            return None  # malformed cache entry = miss
        result.from_cache = True
        return result

    async def _cache_set(self, key: str, result: VerificationResult) -> None:
        # Only VERIFIED / NOT_FOUND are cached (callers ensure this)
        if not self.cache_enabled:
            return
        redis = await self._get_redis()
        if redis is None:
            return
        payload = json.dumps(
            {
                "v": CACHE_SCHEMA_VERSION,
                "cached_at": datetime.utcnow().isoformat(),
                **result.to_dict(),
            }
        )
        try:
            await redis.set(key, payload, ex=self.cache_ttl_seconds)
        except Exception as e:
            self._warn_cache(f"Redis write failed: {e}")

    def _warn_cache(self, message: str) -> None:
        if self._cache_warned:
            logger.debug(message)
        else:
            logger.warning(message)
            self._cache_warned = True
