"""Focused coverage for source origin/type metadata in the RAG layer."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_pipeline.rag_retriever import RAGRetriever, SourceDoc


def _retriever(cache_dir: Path) -> RAGRetriever:
    return RAGRetriever(
        cache_dir=str(cache_dir),
        semantic_scholar_api_key="test-key",
        tavily_api_key=None,
    )


def _mock_http_client(payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


def test_uploaded_identifier_preserves_manual_source_origin() -> None:
    source = SourceDoc(
        title="Course reader",
        authors=["Rossi"],
        year=2024,
        paper_id="uploaded:42",
    )

    assert source.provider == "uploaded"
    assert source.source_type == "uploaded_pdf"


@pytest.mark.asyncio
async def test_source_metadata_survives_cache_round_trip(tmp_path: Path) -> None:
    retriever = _retriever(tmp_path)
    source = SourceDoc(
        title="A study",
        authors=["Rossi"],
        year=2024,
        provider="crossref",
        source_type="journal-article",
    )

    await retriever._save_to_cache("query", [source])
    loaded = await retriever._load_from_cache("query")

    assert loaded is not None
    assert loaded[0].provider == "crossref"
    assert loaded[0].source_type == "journal-article"


@pytest.mark.asyncio
async def test_crossref_preserves_provider_and_work_type(tmp_path: Path) -> None:
    retriever = _retriever(tmp_path)
    client = _mock_http_client(
        {
            "message": {
                "items": [
                    {
                        "title": ["A verified article"],
                        "author": [{"given": "Ada", "family": "Rossi"}],
                        "issued": {"date-parts": [[2024]]},
                        "DOI": "10.1000/example",
                        "type": "journal-article",
                    }
                ]
            }
        }
    )

    with patch("httpx.AsyncClient", return_value=client):
        results = await retriever.search_crossref("query", limit=1, page=2)

    assert results[0].provider == "crossref"
    assert results[0].source_type == "journal-article"
    assert "type" in client.get.call_args.kwargs["params"]["select"].split(",")
    assert client.get.call_args.kwargs["params"]["offset"] == 1


@pytest.mark.asyncio
async def test_openalex_preserves_provider_and_work_type(tmp_path: Path) -> None:
    retriever = _retriever(tmp_path)
    client = _mock_http_client(
        {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "A repository thesis",
                    "publication_year": 2023,
                    "authorships": [{"author": {"display_name": "Ada Rossi"}}],
                    "type": "dissertation",
                }
            ]
        }
    )

    with patch("httpx.AsyncClient", return_value=client):
        results = await retriever.search_openalex("query", limit=1, page=2)

    assert results[0].provider == "openalex"
    assert results[0].source_type == "dissertation"
    assert client.get.call_args.kwargs["params"]["page"] == 2


@pytest.mark.asyncio
async def test_strict_retrieval_surfaces_provider_failure(tmp_path: Path) -> None:
    retriever = _retriever(tmp_path)
    client = MagicMock()
    client.get = AsyncMock(side_effect=RuntimeError("provider down"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=client):
        with pytest.raises(RuntimeError, match="provider down"):
            await retriever.search_crossref("query", limit=1, raise_on_error=True)


@pytest.mark.asyncio
async def test_semantic_scholar_preserves_provider_and_publication_type(
    tmp_path: Path,
) -> None:
    retriever = _retriever(tmp_path)
    client = _mock_http_client(
        {
            "data": [
                {
                    "paperId": "S2-1",
                    "title": "A conference paper",
                    "authors": [{"name": "Ada Rossi"}],
                    "year": 2022,
                    "publicationTypes": ["Conference"],
                }
            ]
        }
    )

    with patch("httpx.AsyncClient", return_value=client):
        results = await retriever.retrieve("query")

    assert results[0].provider == "semantic_scholar"
    assert results[0].source_type == "Conference"
