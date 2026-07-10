"""
PlagiarismChecker (Copyscape) parsing must be fail-visible:

- An <error> element in the HTTP-200 XML body (bad credentials, no credits,
  rejected input) must yield checked=False — NOT "0 matches / 100% unique".
  This exact fail-open masked a dead checker: text searches were sent via
  GET, Copyscape rejected them with an <error>, and the parser read the
  absence of <result> elements as a clean pass.
- Text searches must go through POST (Copyscape rejects "t" via GET).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.plagiarism_checker import PlagiarismChecker

ERROR_XML = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    "<response>\n\t<error>Username or API key not correct</error>\n</response>"
)

NO_MATCH_XML = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    "<response>\n\t<query>...</query>\n\t<count>0</count>\n</response>"
)

# Real csearch shape: querywords at response level, minwordsmatched per
# result (as returned live by the Copyscape API).
MATCH_XML = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    "<response><querywords>100</querywords><count>2</count>"
    "<result><index>1</index>"
    "<url>http://example.com/page</url><title>Example</title>"
    "<minwordsmatched>40</minwordsmatched>"
    "</result>"
    "<result><index>2</index>"
    "<url>http://example.org/mirror</url><title>Mirror</title>"
    "<minwordsmatched>35</minwordsmatched>"
    "</result></response>"
)


def _client_returning(xml_text: str) -> MagicMock:
    response = MagicMock()
    response.text = xml_text
    response.raise_for_status = MagicMock()
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _response(xml_text: str) -> MagicMock:
    response = MagicMock()
    response.text = xml_text
    response.raise_for_status = MagicMock()
    return response


def _configured_checker() -> PlagiarismChecker:
    checker = PlagiarismChecker()
    checker.api_key = "test-key"
    checker.api_username = "test-user"
    return checker


@pytest.mark.asyncio
async def test_api_error_xml_is_unchecked_not_clean_pass():
    client = _client_returning(ERROR_XML)
    with patch("httpx.AsyncClient", return_value=client):
        result = await _configured_checker().check_text("Some text to check")

    assert result["checked"] is False
    assert "Username or API key not correct" in result["error"]
    assert result["uniqueness_percentage"] is None


@pytest.mark.asyncio
async def test_text_search_uses_post_not_get():
    client = _client_returning(NO_MATCH_XML)
    with patch("httpx.AsyncClient", return_value=client):
        result = await _configured_checker().check_text("Some text to check")

    assert client.post.await_count == 1
    assert client.get.await_count == 0
    sent = client.post.await_args.kwargs.get("data") or {}
    assert sent.get("o") == "csearch"
    assert "Some text" in sent.get("t", "")
    assert result["checked"] is True


@pytest.mark.asyncio
async def test_clean_response_without_results_is_100_unique():
    client = _client_returning(NO_MATCH_XML)
    with patch("httpx.AsyncClient", return_value=client):
        result = await _configured_checker().check_text("Testo unico di prova")

    assert result["checked"] is True
    assert result["uniqueness_percentage"] == 100.0
    assert result["matches_found"] == 0


@pytest.mark.asyncio
async def test_matches_reduce_uniqueness_by_best_match_not_sum():
    client = _client_returning(MATCH_XML)
    text = " ".join(["parola"] * 100)
    with patch("httpx.AsyncClient", return_value=client):
        result = await _configured_checker().check_text(text)

    assert result["checked"] is True
    assert result["matches_found"] == 2
    # Best match 40/100 words -> 60% unique. Summing (40+35) would
    # double-count the same passage mirrored on two pages.
    assert result["uniqueness_percentage"] == 60.0


@pytest.mark.asyncio
async def test_unconfigured_credentials_are_unchecked():
    checker = PlagiarismChecker()
    checker.api_key = None
    checker.api_username = None
    result = await checker.check_text("Some text")

    assert result["checked"] is False
    assert result["uniqueness_percentage"] is None


@pytest.mark.asyncio
async def test_long_text_checks_words_after_first_1000_and_uses_worst_chunk():
    words = [f"word-{index}" for index in range(1100)]
    client = _client_returning(NO_MATCH_XML)
    client.post = AsyncMock(side_effect=[_response(NO_MATCH_XML), _response(MATCH_XML)])

    with patch("httpx.AsyncClient", return_value=client):
        result = await _configured_checker().check_document_section(
            " ".join(words), "Analisi"
        )

    assert client.post.await_count == 2
    first_request = client.post.await_args_list[0].kwargs["data"]["t"].split()
    second_request = client.post.await_args_list[1].kwargs["data"]["t"].split()
    assert first_request == words[:1000]
    assert second_request == words[1000:]

    assert result["checked"] is True
    assert result["section_title"] == "Analisi"
    assert result["uniqueness_percentage"] == 60.0
    assert result["text_length_words"] == 1100
    assert result["chunks_total"] == 2
    assert result["chunks_checked"] == 2
    assert [chunk["text_length_words"] for chunk in result["chunk_results"]] == [
        1000,
        100,
    ]
    assert result["matches"][0]["chunk_index"] == 2
    assert result["matches"][0]["word_start"] == 1001
    assert result["matches"][0]["word_end"] == 1100


@pytest.mark.asyncio
async def test_partial_chunk_failure_is_unchecked_but_keeps_checked_evidence():
    words = [f"word-{index}" for index in range(2100)]
    client = _client_returning(NO_MATCH_XML)
    client.post = AsyncMock(
        side_effect=[
            _response(MATCH_XML),
            httpx.ReadTimeout("provider timeout"),
            _response(NO_MATCH_XML),
        ]
    )

    with patch("httpx.AsyncClient", return_value=client):
        result = await _configured_checker().check_text(" ".join(words))

    # A failed middle request must not prevent later chunks from being checked.
    assert client.post.await_count == 3
    assert result["checked"] is False
    assert result["uniqueness_percentage"] is None
    assert result["partial_uniqueness_percentage"] == 60.0
    assert result["text_length_words"] == 2100
    assert result["chunks_total"] == 3
    assert result["chunks_checked"] == 2
    assert result["failed_chunks"] == [2]
    assert "chunk 2" in result["error"]

    # Successful chunks still keep their match evidence for diagnosis/review.
    assert result["matches_found"] == 2
    assert {match["url"] for match in result["matches"]} == {
        "http://example.com/page",
        "http://example.org/mirror",
    }
    assert all(match["chunk_index"] == 1 for match in result["matches"])
    assert result["chunk_results"][1]["checked"] is False
    assert "provider timeout" in result["chunk_results"][1]["error"]
