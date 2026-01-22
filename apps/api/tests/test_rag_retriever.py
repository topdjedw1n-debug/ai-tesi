"""
Tests for RAG Retriever service (Semantic Scholar, Perplexity, Tavily, Serper)
Testing: API mocking, error handling, caching, deduplication
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ai_pipeline.rag_retriever import RAGRetriever, SourceDoc

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary cache directory for tests"""
    cache_dir = tmp_path / "rag_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def retriever(temp_cache_dir: Path) -> RAGRetriever:
    """RAG retriever instance with test cache directory"""
    return RAGRetriever(
        cache_dir=str(temp_cache_dir),
        max_results=10,
        semantic_scholar_api_key="test-ss-key",
        tavily_api_key="test-tavily-key",
    )


@pytest.fixture
def mock_semantic_scholar_response() -> dict[str, Any]:
    """Mock Semantic Scholar API response"""
    return {
        "data": [
            {
                "paperId": "abc123",
                "title": "Machine Learning in Healthcare",
                "authors": [{"name": "John Doe"}, {"name": "Jane Smith"}],
                "year": 2023,
                "abstract": "This paper explores ML applications in healthcare...",
                "venue": "Journal of AI Research",
                "citationCount": 150,
                "url": "https://semanticscholar.org/paper/abc123",
                "doi": "10.1234/example.2023",
            },
            {
                "paperId": "def456",
                "title": "Deep Learning for Medical Imaging",
                "authors": [{"name": "Alice Johnson"}],
                "year": 2022,
                "abstract": "Deep learning techniques for medical image analysis...",
                "venue": "Medical AI Conference",
                "citationCount": 85,
                "url": "https://semanticscholar.org/paper/def456",
                "doi": "10.5678/imaging.2022",
            },
        ]
    }


@pytest.fixture
def mock_perplexity_response() -> dict[str, Any]:
    """Mock Perplexity API response"""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Here are academic papers about machine learning...",
                }
            }
        ],
        "citations": [
            {
                "title": "Neural Networks Fundamentals",
                "authors": ["Bob Brown"],
                "year": 2021,
                "url": "https://example.com/neural-networks",
                "abstract": "Introduction to neural networks...",
                "source": "AI Review",
            },
            "https://arxiv.org/abs/2301.12345",  # Simple URL citation
        ],
    }


@pytest.fixture
def mock_tavily_response() -> dict[str, Any]:
    """Mock Tavily API response"""
    return {
        "results": [
            {
                "title": "Transformers in NLP",
                "content": "Published in 2023. Transformers revolutionized natural language processing...",
                "url": "https://arxiv.org/abs/2303.54321",
                "author": "Carol White",
                "published_date": "2023-03-15",
                "score": 0.95,
            },
            {
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "content": "2018 paper on BERT model...",
                "url": "https://arxiv.org/abs/1810.04805",
                "published_date": "2018-10-11",
                "score": 0.92,
            },
        ]
    }


@pytest.fixture
def mock_serper_response() -> dict[str, Any]:
    """Mock Serper API response"""
    return {
        "organic": [
            {
                "title": "Introduction to Computer Vision - MIT",
                "snippet": "2022 comprehensive guide to computer vision techniques...",
                "link": "https://mit.edu/cv-intro",
            },
            {
                "title": "Object Detection Algorithms Survey",
                "snippet": "Recent survey (2023) of object detection methods...",
                "link": "https://scholar.google.com/citations?view=paper",
            },
        ]
    }


@pytest.fixture
def sample_source_docs() -> list[SourceDoc]:
    """Sample SourceDoc instances for testing"""
    return [
        SourceDoc(
            title="Machine Learning Basics",
            authors=["John Doe", "Jane Smith"],
            year=2023,
            abstract="Introduction to ML concepts...",
            paper_id="ml001",
            venue="AI Journal",
            citation_count=100,
            url="https://example.com/ml001",
            doi="10.1234/ml.2023.001",
        ),
        SourceDoc(
            title="Deep Learning Applications",
            authors=["Alice Johnson"],
            year=2022,
            abstract="DL applications in various domains...",
            paper_id="dl002",
            venue="NeurIPS",
            citation_count=50,
            url="https://example.com/dl002",
            doi="10.5678/dl.2022.002",
        ),
    ]


# ============================================================================
# SEMANTIC SCHOLAR TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_semantic_scholar_retrieve_success(
    retriever: RAGRetriever, mock_semantic_scholar_response: dict[str, Any]
):
    """Test successful Semantic Scholar paper retrieval"""
    # Arrange
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_semantic_scholar_response)
        mock_response.raise_for_status = MagicMock()

        async_client_instance = MagicMock()
        async_client_instance.get = AsyncMock(return_value=mock_response)
        async_client_instance.__aenter__ = AsyncMock(return_value=async_client_instance)
        async_client_instance.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = async_client_instance

        # Act
        results = await retriever.retrieve("machine learning")

        # Assert
        assert len(results) == 2
        assert results[0].title == "Machine Learning in Healthcare"
        assert results[0].year == 2023
        assert len(results[0].authors) == 2
        assert results[0].citation_count == 150
        assert results[0].doi == "10.1234/example.2023"


@pytest.mark.asyncio
async def test_semantic_scholar_retrieve_with_filters(retriever: RAGRetriever):
    """Test Semantic Scholar retrieval with year and citation filters"""
    # Arrange
    mock_response_data = {
        "data": [
            {
                "paperId": "p1",
                "title": "Recent AI Paper",
                "authors": [{"name": "Author One"}],
                "year": 2023,
                "citationCount": 200,
                "abstract": "Abstract text",
                "url": "https://example.com/p1",
            },
            {
                "paperId": "p2",
                "title": "Old Low-Cited Paper",
                "authors": [{"name": "Author Two"}],
                "year": 2015,
                "citationCount": 5,
                "abstract": "Old paper",
                "url": "https://example.com/p2",
            },
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=mock_response_data)
        mock_response.raise_for_status = MagicMock()

        async_client_instance = MagicMock()
        async_client_instance.get = AsyncMock(return_value=mock_response)
        async_client_instance.__aenter__ = AsyncMock(return_value=async_client_instance)
        async_client_instance.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = async_client_instance

        # Act - apply min_citation_count filter
        results = await retriever.retrieve(
            "AI research", year_min=2020, year_max=2024, min_citation_count=100
        )

        # Assert
        assert len(results) == 1  # Only high-cited paper
        assert results[0].title == "Recent AI Paper"
        assert results[0].citation_count == 200


@pytest.mark.asyncio
async def test_semantic_scholar_http_error_handling(retriever: RAGRetriever):
    """Test handling of HTTP errors from Semantic Scholar API"""
    # Arrange
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )
        mock_get.return_value = mock_response

        # Act
        results = await retriever.retrieve("nonexistent query")

        # Assert - should return empty list on error
        assert results == []


@pytest.mark.asyncio
async def test_semantic_scholar_timeout_handling(retriever: RAGRetriever):
    """Test handling of timeout errors"""
    # Arrange
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timeout")

        # Act
        results = await retriever.retrieve("test query")

        # Assert
        assert results == []


@pytest.mark.asyncio
async def test_semantic_scholar_api_key_header(retriever: RAGRetriever):
    """Test that API key is included in request headers"""
    # Arrange
    mock_response_data = {"data": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Act
        await retriever.retrieve("test")

        # Assert - check headers included API key
        call_kwargs = mock_get.call_args.kwargs
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["x-api-key"] == "test-ss-key"


# ============================================================================
# CACHE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cache_save_and_load(
    retriever: RAGRetriever, sample_source_docs: list[SourceDoc], temp_cache_dir: Path
):
    """Test saving and loading sources from cache"""
    # Arrange
    query = "machine learning"

    # Act - save to cache
    await retriever._save_to_cache(query, sample_source_docs)

    # Assert - cache file exists
    cache_files = list(temp_cache_dir.glob("*.json"))
    assert len(cache_files) == 1

    # Act - load from cache
    loaded_docs = await retriever._load_from_cache(query)

    # Assert - loaded data matches original
    assert loaded_docs is not None
    assert len(loaded_docs) == 2
    assert loaded_docs[0].title == "Machine Learning Basics"
    assert loaded_docs[1].doi == "10.5678/dl.2022.002"


@pytest.mark.asyncio
async def test_cache_hit_on_retrieve(
    retriever: RAGRetriever, sample_source_docs: list[SourceDoc]
):
    """Test that retrieve() uses cache when available"""
    # Arrange - pre-populate cache
    query = "cached query"
    await retriever._save_to_cache(query, sample_source_docs)

    # Act - retrieve should hit cache (no API call)
    with patch("httpx.AsyncClient.get") as mock_get:
        results = await retriever.retrieve(query)

        # Assert - no API call made
        mock_get.assert_not_called()
        assert len(results) == 2
        assert results[0].title == "Machine Learning Basics"


@pytest.mark.asyncio
async def test_cache_miss_on_new_query(retriever: RAGRetriever):
    """Test that new queries trigger API call (cache miss)"""
    # Arrange
    mock_response_data = {"data": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Act
        await retriever.retrieve("brand new query")

        # Assert - API call was made
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_cache_expiry_after_7_days(
    retriever: RAGRetriever, sample_source_docs: list[SourceDoc], temp_cache_dir: Path
):
    """Test that cache expires after 7 days"""
    # Arrange - create old cache file
    query = "old query"
    await retriever._save_to_cache(query, sample_source_docs)

    # Find cache file and modify timestamp to 8 days ago
    cache_files = list(temp_cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    cache_file = cache_files[0]

    # Set mtime to 8 days ago (beyond 7-day expiry)
    old_timestamp = datetime.now().timestamp() - (8 * 24 * 60 * 60)
    cache_file.touch()
    Path(cache_file).touch()  # Update to current time first
    import os

    os.utime(cache_file, (old_timestamp, old_timestamp))

    # Act - try to load expired cache
    loaded_docs = await retriever._load_from_cache(query)

    # Assert - should return None (expired)
    assert loaded_docs is None


# ============================================================================
# UTILITY METHOD TESTS
# ============================================================================


def test_query_to_cache_key():
    """Test cache key generation from query"""
    # Arrange
    query1 = "machine learning"
    query2 = "machine learning"
    query3 = "deep learning"

    # Act
    key1 = RAGRetriever._query_to_cache_key(query1)
    key2 = RAGRetriever._query_to_cache_key(query2)
    key3 = RAGRetriever._query_to_cache_key(query3)

    # Assert - same query = same key, different query = different key
    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 32  # MD5 hash length


def test_extract_year_from_content():
    """Test year extraction from text content"""
    # Act & Assert
    assert RAGRetriever._extract_year_from_content("Published in 2023") == 2023
    assert RAGRetriever._extract_year_from_content("The 2022 study showed...") == 2022
    assert (
        RAGRetriever._extract_year_from_content("19th century research")
        == datetime.now().year
    )  # No valid year - default
    assert (
        RAGRetriever._extract_year_from_content("No year here") == datetime.now().year
    )
    assert (
        RAGRetriever._extract_year_from_content("2015-2020 period") == 2015
    )  # First match


def test_deduplicate_sources_by_doi(sample_source_docs: list[SourceDoc]):
    """Test source deduplication by DOI"""
    # Arrange - add duplicate with same DOI
    duplicate = SourceDoc(
        title="Different Title",
        authors=["Different Author"],
        year=2024,
        doi="10.1234/ml.2023.001",  # Same DOI as first doc
    )
    sources = sample_source_docs + [duplicate]

    # Act
    retriever = RAGRetriever()
    deduplicated = retriever._deduplicate_sources(sources)

    # Assert - duplicate removed
    assert len(deduplicated) == 2  # Original 2, duplicate removed
    assert deduplicated[0].doi == "10.1234/ml.2023.001"


def test_deduplicate_sources_by_url():
    """Test source deduplication by URL when no DOI present"""
    # Arrange - create sources WITHOUT DOI so URL dedup applies
    sources = [
        SourceDoc(
            title="Paper One",
            authors=["Author A"],
            year=2023,
            url="https://example.com/paper1",
            doi=None,  # No DOI - URL dedup applies
        ),
        SourceDoc(
            title="Paper Two",
            authors=["Author B"],
            year=2022,
            url="https://example.com/paper2",
            doi=None,  # No DOI
        ),
        SourceDoc(
            title="Duplicate Paper",
            authors=["Author C"],
            year=2023,
            url="https://example.com/paper1",  # Same URL as first
            doi=None,  # No DOI - should be deduplicated by URL
        ),
    ]

    # Act
    retriever = RAGRetriever()
    deduplicated = retriever._deduplicate_sources(sources)

    # Assert - duplicate removed
    assert len(deduplicated) == 2
    urls = [doc.url for doc in deduplicated]
    assert "https://example.com/paper1" in urls
    assert "https://example.com/paper2" in urls


def test_deduplicate_sources_by_title():
    """Test source deduplication by title (when no DOI/URL)"""
    # Arrange
    sources = [
        SourceDoc(title="Machine Learning", authors=[], year=2023),
        SourceDoc(title="Machine Learning", authors=[], year=2023),  # Duplicate
        SourceDoc(title="Deep Learning", authors=[], year=2022),
    ]

    # Act
    retriever = RAGRetriever()
    deduplicated = retriever._deduplicate_sources(sources)

    # Assert
    assert len(deduplicated) == 2
    assert deduplicated[0].title == "Machine Learning"
    assert deduplicated[1].title == "Deep Learning"


# ============================================================================
# PERPLEXITY API TESTS
# ============================================================================


@pytest.mark.asyncio
@patch("app.core.config.settings.PERPLEXITY_API_KEY", "test-perplexity-key")
async def test_perplexity_search_success(
    retriever: RAGRetriever, mock_perplexity_response: dict[str, Any]
):
    """Test successful Perplexity API search"""
    # Arrange
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=mock_perplexity_response)
        mock_response.raise_for_status = MagicMock()

        async_client_instance = MagicMock()
        async_client_instance.post = AsyncMock(return_value=mock_response)
        async_client_instance.__aenter__ = AsyncMock(return_value=async_client_instance)
        async_client_instance.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = async_client_instance

        # Act
        results = await retriever.search_perplexity("neural networks")

        # Assert
        assert len(results) == 2
        assert results[0].title == "Neural Networks Fundamentals"
        assert results[0].year == 2021
        assert results[1].url == "https://arxiv.org/abs/2301.12345"


@pytest.mark.asyncio
@patch("app.core.config.settings.PERPLEXITY_API_KEY", None)
async def test_perplexity_search_no_api_key(retriever: RAGRetriever):
    """Test Perplexity search when API key not configured"""
    # Act
    results = await retriever.search_perplexity("test query")

    # Assert - should return empty list
    assert results == []


@pytest.mark.asyncio
@patch("app.core.config.settings.PERPLEXITY_API_KEY", "test-key")
async def test_perplexity_http_error_handling(retriever: RAGRetriever):
    """Test Perplexity API HTTP error handling"""
    # Arrange
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = mock_response

        # Act
        results = await retriever.search_perplexity("test")

        # Assert
        assert results == []


# ============================================================================
# TAVILY API TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_tavily_search_success(
    retriever: RAGRetriever, mock_tavily_response: dict[str, Any]
):
    """Test successful Tavily API search"""
    # Arrange - mock TavilyClient
    with patch.object(retriever, "tavily_client") as mock_client:
        mock_client.search.return_value = mock_tavily_response

        # Act
        results = await retriever.search_tavily("transformers NLP")

        # Assert
        assert len(results) == 2
        assert results[0].title == "Transformers in NLP"
        assert results[0].year == 2023
        assert results[0].authors == ["Carol White"]
        assert results[1].year == 2018


@pytest.mark.asyncio
async def test_tavily_search_no_client(temp_cache_dir: Path):
    """Test Tavily search when client not initialized"""
    # Arrange - retriever without Tavily key
    retriever = RAGRetriever(cache_dir=str(temp_cache_dir), tavily_api_key=None)

    # Act
    results = await retriever.search_tavily("test")

    # Assert
    assert results == []


@pytest.mark.asyncio
async def test_tavily_search_exception_handling(retriever: RAGRetriever):
    """Test Tavily API exception handling"""
    # Arrange
    with patch.object(retriever, "tavily_client") as mock_client:
        mock_client.search.side_effect = Exception("Tavily API error")

        # Act
        results = await retriever.search_tavily("test")

        # Assert
        assert results == []


# ============================================================================
# SERPER API TESTS
# ============================================================================


@pytest.mark.asyncio
@patch("app.core.config.settings.SERPER_API_KEY", "test-serper-key")
async def test_serper_search_success(
    retriever: RAGRetriever, mock_serper_response: dict[str, Any]
):
    """Test successful Serper API search"""
    # Arrange
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=mock_serper_response)
        mock_response.raise_for_status = MagicMock()

        async_client_instance = MagicMock()
        async_client_instance.post = AsyncMock(return_value=mock_response)
        async_client_instance.__aenter__ = AsyncMock(return_value=async_client_instance)
        async_client_instance.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = async_client_instance

        # Act
        results = await retriever.search_serper("computer vision")

        # Assert
        assert len(results) == 2
        assert results[0].title == "Introduction to Computer Vision - MIT"
        assert results[0].year == 2022
        assert results[1].year == 2023
        assert "mit.edu" in results[0].url


@pytest.mark.asyncio
@patch("app.core.config.settings.SERPER_API_KEY", None)
async def test_serper_search_no_api_key(retriever: RAGRetriever):
    """Test Serper search when API key not configured"""
    # Act
    results = await retriever.search_serper("test")

    # Assert
    assert results == []


@pytest.mark.asyncio
@patch("app.core.config.settings.SERPER_API_KEY", "test-key")
async def test_serper_http_error_handling(retriever: RAGRetriever):
    """Test Serper API HTTP error handling"""
    # Arrange
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Rate Limit", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = mock_response

        # Act
        results = await retriever.search_serper("test")

        # Assert
        assert results == []


# ============================================================================
# INTEGRATION TESTS (MULTI-SOURCE)
# ============================================================================


@pytest.mark.asyncio
@patch("app.core.config.settings.SEMANTIC_SCHOLAR_ENABLED", True)
@patch("app.core.config.settings.PERPLEXITY_API_KEY", "test-key")
@patch("app.core.config.settings.TAVILY_API_KEY", "test-key")
@patch("app.core.config.settings.SERPER_API_KEY", "test-key")
async def test_retrieve_sources_combines_all_apis(retriever: RAGRetriever):
    """Test retrieve_sources combines results from all APIs"""
    # Arrange - mock all API methods
    semantic_docs = [SourceDoc(title="Semantic Paper", authors=[], year=2023)]
    perplexity_docs = [SourceDoc(title="Perplexity Paper", authors=[], year=2022)]
    tavily_docs = [SourceDoc(title="Tavily Paper", authors=[], year=2021)]
    serper_docs = [SourceDoc(title="Serper Paper", authors=[], year=2020)]

    with patch.object(
        retriever, "search_semantic_scholar", return_value=semantic_docs
    ), patch.object(
        retriever, "search_perplexity", return_value=perplexity_docs
    ), patch.object(retriever, "search_tavily", return_value=tavily_docs), patch.object(
        retriever, "search_serper", return_value=serper_docs
    ):
        # Act
        results = await retriever.retrieve_sources("AI research", limit=10)

        # Assert
        assert len(results) == 4  # All 4 sources included
        titles = [doc.title for doc in results]
        assert "Semantic Paper" in titles
        assert "Perplexity Paper" in titles
        assert "Tavily Paper" in titles
        assert "Serper Paper" in titles


@pytest.mark.asyncio
@patch("app.core.config.settings.SEMANTIC_SCHOLAR_ENABLED", True)
async def test_retrieve_sources_deduplicates_results(retriever: RAGRetriever):
    """Test retrieve_sources deduplicates across multiple APIs"""
    # Arrange - same paper from multiple sources
    duplicate_paper = SourceDoc(
        title="Same Paper", authors=["Author"], year=2023, doi="10.1234/same.2023"
    )

    semantic_docs = [duplicate_paper]
    perplexity_docs = [duplicate_paper]  # Duplicate

    with patch.object(
        retriever, "search_semantic_scholar", return_value=semantic_docs
    ), patch.object(
        retriever, "search_perplexity", return_value=perplexity_docs
    ), patch.object(retriever, "search_tavily", return_value=[]), patch.object(
        retriever, "search_serper", return_value=[]
    ):
        # Act
        results = await retriever.retrieve_sources("test", limit=10)

        # Assert - duplicate removed
        assert len(results) == 1
        assert results[0].title == "Same Paper"


@pytest.mark.asyncio
async def test_retrieve_sources_respects_limit(retriever: RAGRetriever):
    """Test retrieve_sources respects limit parameter"""
    # Arrange - many results from APIs
    many_docs = [
        SourceDoc(
            title=f"Paper {i}", authors=[], year=2023, url=f"https://example.com/{i}"
        )
        for i in range(50)
    ]

    with patch.object(
        retriever, "search_semantic_scholar", return_value=many_docs[:25]
    ), patch.object(
        retriever, "search_perplexity", return_value=many_docs[25:]
    ), patch.object(retriever, "search_tavily", return_value=[]), patch.object(
        retriever, "search_serper", return_value=[]
    ):
        # Act
        results = await retriever.retrieve_sources("test", limit=10)

        # Assert
        assert len(results) == 10  # Limited to 10


@pytest.mark.asyncio
@patch("app.core.config.settings.SEMANTIC_SCHOLAR_ENABLED", True)
async def test_retrieve_sources_handles_partial_api_failures(retriever: RAGRetriever):
    """Test retrieve_sources continues if some APIs fail"""
    # Arrange
    semantic_docs = [SourceDoc(title="Semantic Paper", authors=[], year=2023)]

    with patch.object(
        retriever, "search_semantic_scholar", return_value=semantic_docs
    ), patch.object(
        retriever, "search_perplexity", side_effect=Exception("API error")
    ), patch.object(retriever, "search_tavily", return_value=[]), patch.object(
        retriever, "search_serper", return_value=[]
    ):
        # Act
        results = await retriever.retrieve_sources("test", limit=10)

        # Assert - still returns results from working APIs
        assert len(results) == 1
        assert results[0].title == "Semantic Paper"


# ============================================================================
# SOURCEDOC CONVERSION TEST
# ============================================================================


def test_source_doc_to_source_document_conversion():
    """Test SourceDoc to SourceDocument conversion for citations"""
    # Arrange
    source_doc = SourceDoc(
        title="Test Paper",
        authors=["John Doe", "Jane Smith"],
        year=2023,
        abstract="Abstract text",
        paper_id="p123",
        venue="AI Conference",
        citation_count=100,
        url="https://example.com/paper",
        doi="10.1234/test.2023",
    )

    # Act
    source_document = source_doc.to_source_document()

    # Assert
    assert source_document.title == "Test Paper"
    assert source_document.authors == ["John Doe", "Jane Smith"]
    assert source_document.year == 2023
    assert source_document.journal == "AI Conference"
    assert source_document.doi == "10.1234/test.2023"
    assert source_document.url == "https://example.com/paper"
