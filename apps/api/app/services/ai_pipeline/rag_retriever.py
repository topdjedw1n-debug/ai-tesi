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

from app.core.config import settings
from app.services.ai_pipeline.citation_formatter import SourceDocument

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
    ):
        """
        Initialize RAG retriever

        Args:
            cache_dir: Directory for local vector cache (optional)
            max_results: Maximum number of results to retrieve
            semantic_scholar_api_key: Semantic Scholar API key (optional but recommended)
        """
        self.api_key = (
            semantic_scholar_api_key
            or settings.SEMANTIC_SCHOLAR_API_KEY
            or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        )
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.max_results = max_results
        self.cache_dir = Path(cache_dir) if cache_dir else Path("/tmp/rag_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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
                    {"role": "user", "content": f"Search for academic papers about: {query}"}
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
                content = result["choices"][0].get("message", {}).get("content", "")
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
                        )
                        source_docs.append(source_doc)
                    elif isinstance(citation, str):
                        # Simple URL citation
                        source_doc = SourceDoc(
                            title="Source",
                            authors=[],
                            year=datetime.now().year,
                            url=citation,
                        )
                        source_docs.append(source_doc)
            
            logger.info(f"Retrieved {len(source_docs)} sources from Perplexity for query: {query}")
            return source_docs
            
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error retrieving from Perplexity: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error retrieving from Perplexity: {e}")
            return []

    async def search_tavily(self, query: str) -> list[SourceDoc]:
        """
        Search using Tavily API for academic and web sources
        
        Args:
            query: Search query
            
        Returns:
            List of SourceDoc instances
        """
        if not settings.TAVILY_API_KEY:
            logger.debug("Tavily API key not configured, skipping")
            return []
        
        try:
            headers = {
                "Content-Type": "application/json",
            }
            
            data = {
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "include_answer": False,
                "include_raw_content": False,
                "max_results": 10,
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    headers=headers,
                    json=data,
                )
                response.raise_for_status()
                result = response.json()
            
            # Parse Tavily response
            source_docs: list[SourceDoc] = []
            
            if "results" in result:
                for item in result["results"][:10]:  # Limit to 10 results
                    source_doc = SourceDoc(
                        title=item.get("title", "Unknown"),
                        authors=[item.get("author", "Unknown")] if item.get("author") else [],
                        year=self._extract_year_from_content(item.get("content", "")),
                        abstract=item.get("content", "")[:500] if item.get("content") else None,
                        url=item.get("url"),
                        venue=item.get("published_date"),
                    )
                    source_docs.append(source_doc)
            
            logger.info(f"Retrieved {len(source_docs)} sources from Tavily for query: {query}")
            return source_docs
            
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error retrieving from Tavily: {e}")
            return []
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
        seen: set[str] = set()
        deduplicated: list[SourceDoc] = []
        
        for source in sources:
            # Create unique key from title, URL, or DOI
            if source.doi:
                key = f"doi:{source.doi.lower()}"
            elif source.url:
                # Normalize URL
                key = f"url:{source.url.lower().rstrip('/')}"
            else:
                # Use title as key
                key = f"title:{source.title.lower().strip()}"
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(source)
        
        return deduplicated

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

        return hashlib.md5(query.encode()).hexdigest()
