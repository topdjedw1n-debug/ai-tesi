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

MATCH_XML = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    "<response><count>1</count><result>"
    "<url>http://example.com/page</url><title>Example</title>"
    "<words>40</words><minwords>40</minwords>"
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
async def test_matches_reduce_uniqueness():
    client = _client_returning(MATCH_XML)
    text = " ".join(["parola"] * 100)  # 100 words, 40 matched -> 60% unique
    with patch("httpx.AsyncClient", return_value=client):
        result = await _configured_checker().check_text(text)

    assert result["checked"] is True
    assert result["matches_found"] == 1
    assert result["uniqueness_percentage"] == 60.0


@pytest.mark.asyncio
async def test_unconfigured_credentials_are_unchecked():
    checker = PlagiarismChecker()
    checker.api_key = None
    checker.api_username = None
    result = await checker.check_text("Some text")

    assert result["checked"] is False
    assert result["uniqueness_percentage"] is None
