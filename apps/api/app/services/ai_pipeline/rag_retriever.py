"""
RAG (Retrieval-Augmented Generation) retriever using multiple search APIs
Retrieves relevant academic papers and sources for context in generation
Supports: Semantic Scholar, Perplexity, Tavily
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from tavily import TavilyClient

from app.core.config import settings
from app.services.ai_pipeline.citation_formatter import SourceDocument
from app.services.ai_pipeline.source_identity import (
    normalize_doi,
    normalize_title,
    sources_equivalent,
)

logger = logging.getLogger(__name__)


@dataclass
class SourceDoc:
    """Source document retrieved from Semantic Scholar"""

    title: str
    authors: list[str]
    year: int
    abstract: str | None = None
    paper_id: str | None = None
    venue: str | None = None
    citation_count: int | None = None
    url: str | None = None
    doi: str | None = None
    # Retrieval provenance is intentionally carried with the in-memory source
    # so later quality gates can distinguish automatic database results from
    # manager-uploaded material without guessing from URLs or titles.
    provider: str | None = None
    source_type: str | None = None
    verification_status: str = "unverified"
    canonical_metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Backfill metadata for the existing uploaded-source identifier.

        Uploaded PDF packs pre-date the explicit provider/type fields and use
        a stable ``uploaded:<id>`` paper identifier.  Inferring only this
        already-established identifier keeps old callers and cached objects
        compatible while preserving their origin for the preflight gate.
        """
        if self.provider is None and (self.paper_id or "").startswith("uploaded:"):
            self.provider = "uploaded"
        if self.source_type is None and self.provider == "uploaded":
            self.source_type = "uploaded_pdf"

    def to_source_document(self) -> SourceDocument:
        """Convert to SourceDocument for citation formatting"""
        return SourceDocument(
            title=self.title,
            authors=self.authors,
            year=self.year,
            journal=self.venue,
            doi=self.doi,
            url=self.url,
        )


class RAGRetriever:
    """Retrieve relevant academic papers from multiple search APIs"""

    def __init__(
        self,
        cache_dir: str | None = None,
        max_results: int = 10,
        semantic_scholar_api_key: str | None = None,
        tavily_api_key: str | None = None,
    ):
        """
        Initialize RAG retriever

        Args:
            cache_dir: Directory for local vector cache (optional)
            max_results: Maximum number of results to retrieve
            semantic_scholar_api_key: Semantic Scholar API key (optional but recommended)
            tavily_api_key: Tavily API key for web search (optional)
        """
        # Semantic Scholar setup
        self.api_key = (
            semantic_scholar_api_key
            or settings.SEMANTIC_SCHOLAR_API_KEY
            or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        )
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.max_results = max_results
        self.cache_dir = Path(cache_dir) if cache_dir else Path("/tmp/rag_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Tavily setup
        self.tavily_key = (
            tavily_api_key or settings.TAVILY_API_KEY or os.getenv("TAVILY_API_KEY")
        )
        self.tavily_client = None
        if self.tavily_key:
            try:
                self.tavily_client = TavilyClient(api_key=self.tavily_key)
                logger.info("Tavily client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Tavily client: {e}")

    async def retrieve(
        self,
        query: str,
        fields: list[str] | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        min_citation_count: int | None = None,
        limit: int | None = None,
    ) -> list[SourceDoc]:
        """
        Retrieve relevant academic papers from Semantic Scholar

        Args:
            query: Search query (topic, keywords)
            fields: Fields to retrieve (default: comprehensive)
            year_min: Minimum publication year filter
            year_max: Maximum publication year filter
            min_citation_count: Minimum citation count filter
            limit: Maximum number of results (overrides max_results)

        Returns:
            List of SourceDoc instances
        """
        try:
            # Check cache first
            cached_results = await self._load_from_cache(query)
            if cached_results:
                logger.info(
                    f"Retrieved {len(cached_results)} sources from cache for query: {query}"
                )
                return cached_results[: limit or self.max_results]

            # Build API request
            params: dict[str, Any] = {
                "query": query,
                "limit": limit or self.max_results,
                "fields": fields
                or [
                    "title",
                    "authors",
                    "year",
                    "abstract",
                    "paperId",
                    "venue",
                    "citationCount",
                    "url",
                    "doi",
                    "publicationTypes",
                ],
            }

            # Add filters
            if year_min:
                params["year"] = f"{year_min}-"
            if year_max and year_min:
                params["year"] = f"{year_min}-{year_max}"
            elif year_max:
                params["year"] = f"-{year_max}"

            # Make API request
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/paper/search", params=params, headers=headers
                )
                response.raise_for_status()
                data = response.json()

            # Parse results
            papers = data.get("data", [])
            source_docs: list[SourceDoc] = []

            for paper in papers:
                # Apply citation count filter if specified
                if min_citation_count:
                    citation_count = paper.get("citationCount", 0)
                    if citation_count < min_citation_count:
                        continue

                # Extract authors
                authors = []
                for author in paper.get("authors", []):
                    author_name = author.get("name", "")
                    if author_name:
                        authors.append(author_name)

                publication_types = paper.get("publicationTypes")
                if isinstance(publication_types, list):
                    source_type = publication_types[0] if publication_types else None
                elif isinstance(publication_types, str):
                    source_type = publication_types
                else:
                    source_type = None

                # Create SourceDoc
                source_doc = SourceDoc(
                    title=paper.get("title", ""),
                    authors=authors,
                    year=paper.get("year", 0),
                    abstract=paper.get("abstract", ""),
                    paper_id=paper.get("paperId"),
                    venue=paper.get("venue"),
                    citation_count=paper.get("citationCount"),
                    url=paper.get("url"),
                    doi=paper.get("doi"),
                    provider="semantic_scholar",
                    source_type=source_type,
                )
                source_docs.append(source_doc)

            # Cache results
            await self._save_to_cache(query, source_docs)

            logger.info(
                f"Retrieved {len(source_docs)} sources from Semantic Scholar for query: {query}"
            )
            return source_docs

        except httpx.HTTPError as e:
            logger.error(f"HTTP error retrieving sources: {e}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving sources: {e}")
            return []

    async def _save_to_cache(self, query: str, source_docs: list[SourceDoc]) -> None:
        """Save retrieved sources to local cache"""
        try:
            # Create cache key from query
            cache_key = self._query_to_cache_key(query)
            cache_file = self.cache_dir / f"{cache_key}.json"

            # Serialize SourceDocs
            cache_data = {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "sources": [
                    {
                        "title": doc.title,
                        "authors": doc.authors,
                        "year": doc.year,
                        "abstract": doc.abstract,
                        "paper_id": doc.paper_id,
                        "venue": doc.venue,
                        "citation_count": doc.citation_count,
                        "url": doc.url,
                        "doi": doc.doi,
                        "provider": doc.provider,
                        "source_type": doc.source_type,
                    }
                    for doc in source_docs
                ],
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    async def _load_from_cache(self, query: str) -> list[SourceDoc] | None:
        """Load sources from local cache if available"""
        try:
            cache_key = self._query_to_cache_key(query)
            cache_file = self.cache_dir / f"{cache_key}.json"

            if not cache_file.exists():
                return None

            # Check cache age (expire after 7 days)
            cache_age = datetime.utcnow().timestamp() - cache_file.stat().st_mtime
            if cache_age > 7 * 24 * 60 * 60:  # 7 days
                return None

            with open(cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)

            # Deserialize SourceDocs
            source_docs = [
                SourceDoc(
                    title=s["title"],
                    authors=s["authors"],
                    year=s["year"],
                    abstract=s.get("abstract"),
                    paper_id=s.get("paper_id"),
                    venue=s.get("venue"),
                    citation_count=s.get("citation_count"),
                    url=s.get("url"),
                    doi=s.get("doi"),
                    provider=s.get("provider"),
                    source_type=s.get("source_type"),
                )
                for s in cache_data.get("sources", [])
            ]

            return source_docs

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    async def search_perplexity(self, query: str) -> list[SourceDoc]:
        """
        Search using Perplexity API for real-time search results

        Args:
            query: Search query

        Returns:
            List of SourceDoc instances
        """
        if not settings.PERPLEXITY_API_KEY:
            logger.debug("Perplexity API key not configured, skipping")
            return []

        try:
            headers = {
                "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            }

            data = {
                "model": "pplx-7b-online",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Search for academic papers about: {query}",
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json=data,
                )
                response.raise_for_status()
                result = response.json()

            # Parse Perplexity response
            # Perplexity returns chat completion with citations in content
            source_docs: list[SourceDoc] = []

            if "choices" in result and len(result["choices"]) > 0:
                # Content is included for context but not parsed here
                # Citations are the primary data source
                citations = result.get("citations", [])

                # Extract source information from citations
                for citation in citations[:10]:  # Limit to 10 results
                    # Perplexity citations may have different formats
                    # Try to extract title, url, and other info
                    if isinstance(citation, dict):
                        source_doc = SourceDoc(
                            title=citation.get("title", "Unknown"),
                            authors=citation.get("authors", []),
                            year=citation.get("year", datetime.now().year),
                            abstract=citation.get("abstract"),
                            url=citation.get("url"),
                            venue=citation.get("source", citation.get("venue")),
                            provider="perplexity",
                            source_type=citation.get("type"),
                        )
                        source_docs.append(source_doc)
                    elif isinstance(citation, str):
                        # Simple URL citation
                        source_doc = SourceDoc(
                            title="Source",
                            authors=[],
                            year=datetime.now().year,
                            url=citation,
                            provider="perplexity",
                        )
                        source_docs.append(source_doc)

            logger.info(
                f"Retrieved {len(source_docs)} sources from Perplexity for query: {query}"
            )
            return source_docs

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error retrieving from Perplexity: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error retrieving from Perplexity: {e}")
            return []

    async def search_tavily(self, query: str, max_results: int = 10) -> list[SourceDoc]:
        """
        Search using Tavily API for academic and web sources

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of SourceDoc instances
        """
        if not self.tavily_client:
            logger.debug("Tavily client not initialized, skipping")
            return []

        try:
            # Use Tavily Python SDK
            response = self.tavily_client.search(
                query=query,
                search_depth="advanced",  # More thorough search
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
                include_domains=[
                    "scholar.google.com",
                    "arxiv.org",
                    "pubmed.ncbi.nlm.nih.gov",
                    ".edu",
                ],
            )

            # Parse Tavily response
            source_docs: list[SourceDoc] = []

            results = response.get("results", [])
            for item in results:
                # Extract year from content or published_date
                year = self._extract_year_from_content(
                    item.get("content", "") + " " + item.get("published_date", "")
                )

                source_doc = SourceDoc(
                    title=item.get("title", "Unknown"),
                    authors=[item.get("author")] if item.get("author") else [],
                    year=year or datetime.now().year,
                    abstract=(
                        item.get("content", "")[:500] if item.get("content") else None
                    ),
                    url=item.get("url"),
                    venue=item.get("published_date"),
                    citation_count=item.get("score", 0),  # Use relevance score as proxy
                    provider="tavily",
                    source_type=item.get("type"),
                )
                source_docs.append(source_doc)

            logger.info(
                f"Retrieved {len(source_docs)} sources from Tavily for query: {query}"
            )
            return source_docs

        except Exception as e:
            logger.warning(f"Error retrieving from Tavily: {e}")
            return []

    async def search_semantic_scholar(self, query: str) -> list[SourceDoc]:
        """
        Search using Semantic Scholar API (wraps existing retrieve method)

        Args:
            query: Search query

        Returns:
            List of SourceDoc instances
        """
        if not settings.SEMANTIC_SCHOLAR_ENABLED:
            logger.debug("Semantic Scholar disabled, skipping")
            return []

        # Use existing retrieve method
        return await self.retrieve(query, limit=10)

    async def search_serper(self, query: str) -> list[SourceDoc]:
        """
        Search using Serper API for Google search results

        Args:
            query: Search query

        Returns:
            List of SourceDoc instances
        """
        if not settings.SERPER_API_KEY:
            logger.debug("Serper API key not configured, skipping")
            return []

        try:
            headers = {
                "X-API-KEY": settings.SERPER_API_KEY,
                "Content-Type": "application/json",
            }

            data = {
                "q": query,
                "num": 10,  # Number of results
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers=headers,
                    json=data,
                )
                response.raise_for_status()
                result = response.json()

            # Parse Serper response
            source_docs: list[SourceDoc] = []

            # Serper returns results in 'organic' array
            if "organic" in result:
                for item in result["organic"][:10]:  # Limit to 10 results
                    # Extract title, snippet (as abstract), and link (as url)
                    title = item.get("title", "Unknown")
                    snippet = item.get("snippet", "")
                    url = item.get("link", "")

                    # Try to extract year from snippet or date
                    year = self._extract_year_from_content(snippet)

                    # Try to extract author from snippet or title
                    authors: list[str] = []
                    if snippet:
                        # Simple heuristic: first part of snippet might contain author info
                        # This is a basic implementation - could be improved
                        pass

                    source_doc = SourceDoc(
                        title=title,
                        authors=authors,
                        year=year,
                        abstract=snippet[:500] if snippet else None,
                        url=url,
                        venue=None,  # Serper doesn't provide venue info
                        provider="serper",
                    )
                    source_docs.append(source_doc)

            logger.info(
                f"Retrieved {len(source_docs)} sources from Serper for query: {query}"
            )
            return source_docs

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error retrieving from Serper: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error retrieving from Serper: {e}")
            return []

    # ------------------------------------------------------------------
    # Free academic providers (no API key required): Crossref & OpenAlex.
    # These give real, verifiable scholarly sources (title/authors/year/DOI/
    # abstract) so generated sections are grounded instead of hallucinated.
    # ------------------------------------------------------------------

    _POLITE_MAILTO = "research@thesica.ai"

    @staticmethod
    def _clean_abstract(text: str | None) -> str | None:
        """Strip JATS/HTML tags Crossref embeds in abstracts."""
        if not text:
            return None
        import re

        cleaned = re.sub(r"<[^>]+>", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or None

    @staticmethod
    def _reconstruct_openalex_abstract(inverted_index: dict | None) -> str | None:
        """Rebuild an abstract from OpenAlex's inverted-index representation."""
        if not inverted_index:
            return None
        positions: list[tuple[int, str]] = []
        for word, idxs in inverted_index.items():
            for i in idxs:
                positions.append((i, word))
        positions.sort(key=lambda p: p[0])
        return " ".join(w for _, w in positions).strip() or None

    async def search_crossref(
        self,
        query: str,
        limit: int = 10,
        *,
        page: int = 1,
        raise_on_error: bool = False,
    ) -> list[SourceDoc]:
        """Search Crossref for academic works (free, no API key)."""
        base = getattr(settings, "CROSSREF_API_URL", "https://api.crossref.org").rstrip(
            "/"
        )
        params = {
            "query": query,
            "rows": limit,
            "offset": max(0, page - 1) * limit,
            "select": "title,author,issued,DOI,abstract,container-title,URL,type,"
            "is-referenced-by-count",
            "mailto": self._POLITE_MAILTO,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{base}/works", params=params)
                response.raise_for_status()
                items = response.json().get("message", {}).get("items", [])

            source_docs: list[SourceDoc] = []
            for item in items:
                title_list = item.get("title") or []
                title = title_list[0] if title_list else ""
                if not title:
                    continue

                authors = []
                for a in item.get("author", []) or []:
                    name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                    if name:
                        authors.append(name)

                year = 0
                date_parts = (item.get("issued") or {}).get("date-parts") or []
                if date_parts and date_parts[0]:
                    year = date_parts[0][0] or 0

                venue_list = item.get("container-title") or []
                doi = item.get("DOI")
                source_docs.append(
                    SourceDoc(
                        title=title,
                        authors=authors,
                        year=year,
                        abstract=self._clean_abstract(item.get("abstract")),
                        paper_id=doi,
                        venue=venue_list[0] if venue_list else None,
                        citation_count=item.get("is-referenced-by-count"),
                        url=item.get("URL")
                        or (f"https://doi.org/{doi}" if doi else None),
                        doi=doi,
                        provider="crossref",
                        source_type=item.get("type"),
                    )
                )

            logger.info(
                f"Retrieved {len(source_docs)} sources from Crossref for query: {query}"
            )
            return source_docs

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error retrieving from Crossref: {e}")
            if raise_on_error:
                raise
            return []
        except Exception as e:
            logger.warning(f"Error retrieving from Crossref: {e}")
            if raise_on_error:
                raise
            return []

    async def search_openalex(
        self,
        query: str,
        limit: int = 10,
        *,
        page: int = 1,
        raise_on_error: bool = False,
    ) -> list[SourceDoc]:
        """Search OpenAlex for academic works (free, no API key)."""
        base = getattr(settings, "OPENALEX_API_URL", "https://api.openalex.org").rstrip(
            "/"
        )
        params = {
            "search": query,
            "per_page": limit,
            "page": max(1, page),
            "mailto": self._POLITE_MAILTO,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{base}/works", params=params)
                response.raise_for_status()
                works = response.json().get("results", [])

            source_docs: list[SourceDoc] = []
            for w in works:
                title = w.get("title") or w.get("display_name") or ""
                if not title:
                    continue

                authors = []
                for a in w.get("authorships", []) or []:
                    name = (a.get("author") or {}).get("display_name")
                    if name:
                        authors.append(name)

                doi = w.get("doi")
                if doi and doi.startswith("https://doi.org/"):
                    doi = doi[len("https://doi.org/") :]

                venue = ((w.get("primary_location") or {}).get("source") or {}).get(
                    "display_name"
                )

                source_docs.append(
                    SourceDoc(
                        title=title,
                        authors=authors,
                        year=w.get("publication_year") or 0,
                        abstract=self._reconstruct_openalex_abstract(
                            w.get("abstract_inverted_index")
                        ),
                        paper_id=w.get("id"),
                        venue=venue,
                        citation_count=w.get("cited_by_count"),
                        url=w.get("doi") or w.get("id"),
                        doi=doi,
                        provider="openalex",
                        source_type=w.get("type"),
                    )
                )

            logger.info(
                f"Retrieved {len(source_docs)} sources from OpenAlex for query: {query}"
            )
            return source_docs

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error retrieving from OpenAlex: {e}")
            if raise_on_error:
                raise
            return []
        except Exception as e:
            logger.warning(f"Error retrieving from OpenAlex: {e}")
            if raise_on_error:
                raise
            return []

    async def retrieve_sources(self, query: str, limit: int = 20) -> list[SourceDoc]:
        """
        Retrieve sources from all enabled search APIs and combine results

        Args:
            query: Search query
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of SourceDoc instances (deduplicated, top results)
        """
        results: list[SourceDoc] = []

        # Free academic providers first (no API key, reliable scholarly sources).
        # These ground generation in real, verifiable works instead of leaving
        # the model to hallucinate citations.
        if getattr(settings, "ACADEMIC_FREE_RAG_ENABLED", True):
            for provider_name, search_fn in (
                ("Crossref", self.search_crossref),
                ("OpenAlex", self.search_openalex),
            ):
                try:
                    results.extend(await search_fn(query))
                except Exception as e:
                    logger.warning(f"Failed to retrieve from {provider_name}: {e}")

        # Search Semantic Scholar
        if settings.SEMANTIC_SCHOLAR_ENABLED:
            try:
                semantic_results = await self.search_semantic_scholar(query)
                results.extend(semantic_results)
            except Exception as e:
                logger.warning(f"Failed to retrieve from Semantic Scholar: {e}")

        # Search Perplexity
        if settings.PERPLEXITY_API_KEY:
            try:
                perplexity_results = await self.search_perplexity(query)
                results.extend(perplexity_results)
            except Exception as e:
                logger.warning(f"Failed to retrieve from Perplexity: {e}")

        # Search Tavily
        if settings.TAVILY_API_KEY:
            try:
                tavily_results = await self.search_tavily(query)
                results.extend(tavily_results)
            except Exception as e:
                logger.warning(f"Failed to retrieve from Tavily: {e}")

        # Search Serper
        if settings.SERPER_API_KEY:
            try:
                serper_results = await self.search_serper(query)
                results.extend(serper_results)
            except Exception as e:
                logger.warning(f"Failed to retrieve from Serper: {e}")

        # Deduplicate sources
        deduplicated = self._deduplicate_sources(results)

        # Return top results
        top_results = deduplicated[:limit]

        logger.info(
            f"Retrieved {len(top_results)} total sources (after deduplication) "
            f"from {len(results)} raw results for query: {query}"
        )

        return top_results

    def _deduplicate_sources(self, sources: list[SourceDoc]) -> list[SourceDoc]:
        """
        Remove duplicate sources based on title, URL, or DOI

        Args:
            sources: List of SourceDoc instances

        Returns:
            Deduplicated list of SourceDoc instances
        """
        deduplicated: list[SourceDoc] = []

        for source in sources:
            duplicate_index = next(
                (
                    index
                    for index, existing in enumerate(deduplicated)
                    if self._retrieval_records_equivalent(existing, source)
                ),
                None,
            )
            if duplicate_index is None:
                deduplicated.append(source)
                continue
            deduplicated[duplicate_index] = self._merge_source_docs(
                deduplicated[duplicate_index], source
            )

        return deduplicated

    @staticmethod
    def _retrieval_records_equivalent(left: SourceDoc, right: SourceDoc) -> bool:
        if sources_equivalent(left, right):
            return True
        left_doi = normalize_doi(left.doi)
        right_doi = normalize_doi(right.doi)
        if left_doi and right_doi and left_doi != right_doi:
            return False
        left_url = str(left.url or "").strip().casefold().rstrip("/")
        right_url = str(right.url or "").strip().casefold().rstrip("/")
        if left_url and left_url == right_url:
            return True
        # Exact sparse provider records can lack authors entirely. Preserve the
        # old exact-title dedupe only for that narrow case; rich records use the
        # stricter shared title/year/author identity contract.
        return bool(
            not left.authors
            and not right.authors
            and left.year == right.year
            and normalize_title(left.title) == normalize_title(right.title)
        )

    @staticmethod
    def _merge_source_docs(left: SourceDoc, right: SourceDoc) -> SourceDoc:
        """Keep the richest metadata for two records of the same publication."""

        def longer(first: str | None, second: str | None) -> str | None:
            values = [value for value in (first, second) if value]
            return max(values, key=len) if values else None

        authors = list(left.authors or [])
        seen_authors = {author.casefold() for author in authors}
        for author in right.authors or []:
            if author.casefold() not in seen_authors:
                authors.append(author)
                seen_authors.add(author.casefold())
        years = [year for year in (left.year, right.year) if year]
        return SourceDoc(
            title=longer(left.title, right.title) or left.title,
            authors=authors,
            year=min(years) if years else 0,
            abstract=longer(left.abstract, right.abstract),
            paper_id=left.paper_id or right.paper_id,
            venue=longer(left.venue, right.venue),
            citation_count=max(
                left.citation_count or 0,
                right.citation_count or 0,
            ),
            url=left.url or right.url,
            doi=left.doi or right.doi,
            provider=left.provider or right.provider,
            source_type=left.source_type or right.source_type,
        )

    @staticmethod
    def _extract_year_from_content(content: str) -> int:
        """Extract year from content string"""
        import re

        # Try to find 4-digit year (1900-2099)
        # Use non-capturing group to get full year match
        year_matches = re.findall(r"\b(?:19|20)\d{2}\b", content)
        if year_matches:
            try:
                # Get the first valid year
                year = int(year_matches[0])
                # Validate it's in reasonable range
                if 1900 <= year <= 2099:
                    return year
            except (ValueError, IndexError):
                pass

        # Default to current year
        return datetime.now().year

    @staticmethod
    def _query_to_cache_key(query: str) -> str:
        """Convert query to cache key (filename-safe)"""
        import hashlib

        return hashlib.sha256(query.encode()).hexdigest()
