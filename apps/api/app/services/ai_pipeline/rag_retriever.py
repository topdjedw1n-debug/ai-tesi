"""
RAG (Retrieval-Augmented Generation) retriever using Semantic Scholar API
Retrieves relevant academic papers for context in generation
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

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
            url=self.url
        )


class RAGRetriever:
    """Retrieve relevant academic papers from Semantic Scholar"""

    def __init__(
        self,
        cache_dir: str | None = None,
        max_results: int = 10,
        semantic_scholar_api_key: str | None = None
    ):
        """
        Initialize RAG retriever

        Args:
            cache_dir: Directory for local vector cache (optional)
            max_results: Maximum number of results to retrieve
            semantic_scholar_api_key: Semantic Scholar API key (optional but recommended)
        """
        self.api_key = semantic_scholar_api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
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
        limit: int | None = None
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
                logger.info(f"Retrieved {len(cached_results)} sources from cache for query: {query}")
                return cached_results[:limit or self.max_results]

            # Build API request
            params: dict[str, Any] = {
                "query": query,
                "limit": limit or self.max_results,
                "fields": fields or [
                    "title",
                    "authors",
                    "year",
                    "abstract",
                    "paperId",
                    "venue",
                    "citationCount",
                    "url",
                    "doi"
                ]
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
                    f"{self.base_url}/paper/search",
                    params=params,
                    headers=headers
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
                    doi=paper.get("doi")
                )
                source_docs.append(source_doc)

            # Cache results
            await self._save_to_cache(query, source_docs)

            logger.info(f"Retrieved {len(source_docs)} sources from Semantic Scholar for query: {query}")
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
                        "doi": doc.doi
                    }
                    for doc in source_docs
                ]
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
                    doi=s.get("doi")
                )
                for s in cache_data.get("sources", [])
            ]

            return source_docs

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    @staticmethod
    def _query_to_cache_key(query: str) -> str:
        """Convert query to cache key (filename-safe)"""
        import hashlib
        return hashlib.md5(query.encode()).hexdigest()

