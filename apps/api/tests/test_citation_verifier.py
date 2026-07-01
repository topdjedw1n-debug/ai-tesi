"""
Unit tests for CitationVerifier (mocked HTTP and Redis)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.citation_verifier import (
    MAX_ABSTRACT_LENGTH,
    PROVIDERS,
    CitationVerifier,
    SourceInput,
    VerificationResult,
    VerificationStatus,
    normalize_doi,
    normalize_title,
)

CROSSREF_WORK = {
    "title": ["Attention Is All You Need"],
    "author": [
        {"given": "Ashish", "family": "Vaswani"},
        {"given": "Noam", "family": "Shazeer"},
    ],
    "issued": {"date-parts": [[2017, 6]]},
    "container-title": ["Advances in Neural Information Processing Systems"],
    "DOI": "10.5555/3295222",
    # JATS XML fragment, as Crossref returns it
    "abstract": "<jats:p>We propose an architecture based on attention "
    "&amp; recurrence-free encoders.</jats:p>",
}

OPENALEX_WORK = {
    "title": "Attention Is All You Need",
    "publication_year": 2017,
    "authorships": [{"author": {"display_name": "Ashish Vaswani"}}],
    "primary_location": {"source": {"display_name": "NeurIPS"}},
    "doi": "https://doi.org/10.5555/3295222",
    # Out-of-order keys and a repeated word exercise the reconstruction
    "abstract_inverted_index": {
        "replace": [2],
        "Attention": [0],
        "layers": [1, 4],
        "recurrent": [3],
    },
}

S2_PAPER = {
    "title": "Attention Is All You Need",
    "year": 2017,
    "authors": [{"name": "Ashish Vaswani"}],
    "venue": "NeurIPS",
    "externalIds": {"DOI": "10.5555/3295222"},
    "abstract": "We propose the Transformer, built solely on attention.",
}

ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <published>2017-06-12T17:57:34Z</published>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <summary>
      The dominant approach uses recurrent networks;   we propose
      attention instead.
    </summary>
    <arxiv:doi xmlns:arxiv="http://arxiv.org/schemas/atom">10.48550/arXiv.1706.03762</arxiv:doi>
  </entry>
</feed>
"""

ARXIV_EMPTY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>
"""

CROSSREF_EMPTY = {"message": {"items": []}}
OPENALEX_EMPTY = {"results": []}
S2_EMPTY = {"data": []}


def make_response(status_code=200, json_data=None, text_data=None):
    """Build a MagicMock httpx.Response; raise_for_status raises for >=400"""
    response = MagicMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=json_data)
    response.text = text_data or ""
    if status_code >= 400:
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=response
            )
        )
    else:
        response.raise_for_status = MagicMock()
    return response


def make_client(side_effect):
    """MagicMock for httpx.AsyncClient with async context manager support"""
    instance = MagicMock()
    instance.get = AsyncMock(side_effect=side_effect)
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    return instance


def empty_dispatch(url, params=None, headers=None):
    """All providers respond cleanly with zero results"""
    if "openalex" in url:
        return make_response(200, OPENALEX_EMPTY)
    if "semanticscholar" in url:
        return make_response(200, S2_EMPTY)
    if "arxiv" in url:
        return make_response(200, text_data=ARXIV_EMPTY_FEED)
    return make_response(200, CROSSREF_EMPTY)


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


def make_verifier(mock_redis, **kwargs) -> CitationVerifier:
    """Verifier with instant retries and effectively unlimited rate limits"""
    return CitationVerifier(
        redis_client=mock_redis,
        retry_delays=[0, 0],
        rate_limits_rps=dict.fromkeys(PROVIDERS, 10000.0),
        **kwargs,
    )


# ----------------------------------------------------------------------
# Identifier lookups
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_doi_exact_match_crossref(mock_redis):
    verifier = make_verifier(mock_redis)
    source = SourceInput(
        title="Attention Is All You Need", year=2017, doi="10.5555/3295222"
    )
    client = make_client([make_response(200, {"message": CROSSREF_WORK})])

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    assert result.provider == "crossref"
    assert result.match_score == 1.0
    assert result.doi == "10.5555/3295222"
    assert result.year == 2017
    assert "Ashish Vaswani" in result.authors
    assert result.venue == "Advances in Neural Information Processing Systems"
    # JATS tags stripped, entities unescaped
    assert result.abstract == (
        "We propose an architecture based on attention & recurrence-free encoders."
    )
    assert client.get.call_count == 1  # cascade stopped at the DOI hit


@pytest.mark.asyncio
async def test_arxiv_id_match(mock_redis):
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Attention Is All You Need", arxiv_id="arXiv:1706.03762")
    client = make_client([make_response(200, text_data=ARXIV_FEED)])

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    assert result.provider == "arxiv"
    assert result.venue == "arXiv"
    assert result.year == 2017
    assert result.doi == "10.48550/arxiv.1706.03762"
    # atom:summary with internal whitespace collapsed
    assert result.abstract == (
        "The dominant approach uses recurrent networks; we propose "
        "attention instead."
    )
    assert client.get.call_count == 1


@pytest.mark.asyncio
async def test_doi_404_falls_back_to_title_search(mock_redis):
    """A 404 on the DOI is definitive (no retry) but the cascade continues"""
    verifier = make_verifier(mock_redis)
    source = SourceInput(
        title="Attention Is All You Need", year=2017, doi="10.9999/hallucinated"
    )

    def dispatch(url, params=None, headers=None):
        if "/works/10.9999/hallucinated" in url:
            return make_response(404)
        return make_response(200, {"message": {"items": [CROSSREF_WORK]}})

    client = make_client(dispatch)
    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    # Canonical DOI from the title match, not the hallucinated input one
    assert result.doi == "10.5555/3295222"
    # 404 was attempted exactly once (not retried) + one search call
    assert client.get.call_count == 2


@pytest.mark.asyncio
async def test_doi_normalization(mock_redis):
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="", doi="https://doi.org/10.1234/ABC")
    client = make_client([make_response(200, {"message": CROSSREF_WORK})])

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    requested_url = client.get.call_args_list[0].args[0]
    assert requested_url.endswith("/works/10.1234/abc")
    cache_key = mock_redis.set.call_args.args[0]
    assert cache_key == "citation_verify:doi:10.1234/abc"


# ----------------------------------------------------------------------
# Title search cascade
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuzzy_title_match_crossref(mock_redis):
    verifier = make_verifier(mock_redis)
    # One extra word: normalized titles differ but similarity >= 0.90
    source = SourceInput(title="The Attention Is All You Need", year=2017)
    client = make_client([make_response(200, {"message": {"items": [CROSSREF_WORK]}})])

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    assert result.provider == "crossref"
    assert result.match_score is not None
    assert 0.90 <= result.match_score < 1.0
    assert client.get.call_count == 1  # cascade stopped at first hit


@pytest.mark.asyncio
async def test_not_found_all_providers_empty(mock_redis):
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Nonexistent Paper About Nothing", year=2020)
    client = make_client(empty_dispatch)

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.NOT_FOUND
    assert client.get.call_count == 4  # all four providers were asked
    # not_found IS cached with the 90-day TTL
    assert mock_redis.set.call_count == 1
    assert mock_redis.set.call_args.kwargs["ex"] == 90 * 24 * 3600
    assert '"not_found"' in mock_redis.set.call_args.args[1]


@pytest.mark.asyncio
async def test_partial_degradation_openalex_matches(mock_redis):
    """Crossref is down but OpenAlex confirms the source"""
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Attention Is All You Need", year=2017)

    def dispatch(url, params=None, headers=None):
        if "crossref" in url:
            raise httpx.ConnectError("connection refused")
        if "openalex" in url:
            return make_response(200, {"results": [OPENALEX_WORK]})
        return empty_dispatch(url, params, headers)

    client = make_client(dispatch)
    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    assert result.provider == "openalex"
    assert result.doi == "10.5555/3295222"  # normalized from the doi.org URL
    assert result.venue == "NeurIPS"
    # Reconstructed from abstract_inverted_index (position-sorted, repeats kept)
    assert result.abstract == "Attention layers replace recurrent layers"


@pytest.mark.asyncio
async def test_s2_match_includes_abstract(mock_redis):
    """Crossref and OpenAlex come up empty; Semantic Scholar matches and
    its search request asks for the abstract field"""
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Attention Is All You Need", year=2017)

    def dispatch(url, params=None, headers=None):
        if "semanticscholar" in url:
            return make_response(200, {"data": [S2_PAPER]})
        return empty_dispatch(url, params, headers)

    client = make_client(dispatch)
    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    assert result.provider == "semantic_scholar"
    assert result.abstract == "We propose the Transformer, built solely on attention."
    s2_call = next(
        c for c in client.get.call_args_list if "semanticscholar" in c.args[0]
    )
    assert "abstract" in s2_call.kwargs["params"]["fields"].split(",")


@pytest.mark.asyncio
async def test_all_timeout_unresolvable(mock_redis):
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Some Real Paper Title", year=2021)
    client = make_client(httpx.TimeoutException("timed out"))

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.UNRESOLVABLE
    assert result.reason == "provider_errors"
    mock_redis.set.assert_not_called()  # unresolvable is never cached


@pytest.mark.asyncio
async def test_authoritative_clean_no_match_beats_lower_provider_error(mock_redis):
    """An authoritative clean no-match (Crossref) yields NOT_FOUND even when a
    lower-priority provider throttles. Under the strict policy NOT_FOUND blocks,
    so a fabricated citation must not be masked as UNRESOLVABLE just because
    Semantic Scholar returned 403/429."""
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Nonexistent Paper About Nothing", year=2020)

    def dispatch(url, params=None, headers=None):
        if "openalex" in url:
            raise httpx.ConnectError("connection refused")
        if "semanticscholar" in url:
            return make_response(403)  # throttled: 403 is not retried
        if "arxiv" in url:
            raise httpx.ConnectError("connection refused")
        return make_response(200, CROSSREF_EMPTY)  # authoritative clean no-match

    client = make_client(dispatch)
    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.NOT_FOUND
    assert result.reason == "not_found_partial_provider_errors"
    # A NOT_FOUND reached despite provider errors is never cached: a later run
    # may reach the errored providers and verify a work only they index.
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_lower_provider_clean_does_not_rescue_authoritative_errors(mock_redis):
    """Contrast case: only the lower-priority providers (S2/arXiv) ran cleanly;
    both authoritative providers errored. Without a trustworthy authoritative
    read we must stay UNRESOLVABLE rather than assert NOT_FOUND."""
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Some Real Paper Title", year=2021)

    def dispatch(url, params=None, headers=None):
        if "openalex" in url:
            raise httpx.ConnectError("connection refused")
        if "semanticscholar" in url:
            return make_response(200, S2_EMPTY)  # clean, but not authoritative
        if "arxiv" in url:
            return make_response(200, text_data=ARXIV_EMPTY_FEED)
        raise httpx.ConnectError("connection refused")  # crossref down

    client = make_client(dispatch)
    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.UNRESOLVABLE
    assert result.reason == "provider_errors"
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_retry_on_500_then_success(mock_redis):
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Attention Is All You Need", year=2017)
    client = make_client(
        [
            make_response(500),
            make_response(200, {"message": {"items": [CROSSREF_WORK]}}),
        ]
    )

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    assert client.get.call_count == 2  # one 500, one successful retry


@pytest.mark.asyncio
async def test_year_mismatch_rejected(mock_redis):
    """Identical title but year off by 3 fails the year gate"""
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Attention Is All You Need", year=2014)

    def dispatch(url, params=None, headers=None):
        if "crossref" in url and "/works/" not in url:
            return make_response(200, {"message": {"items": [CROSSREF_WORK]}})
        return empty_dispatch(url, params, headers)

    client = make_client(dispatch)
    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_insufficient_metadata(mock_redis):
    verifier = make_verifier(mock_redis)
    with patch("httpx.AsyncClient") as client_class:
        result = await verifier.verify_source(SourceInput(title=""))

    assert result.status == VerificationStatus.UNRESOLVABLE
    assert result.reason == "insufficient_metadata"
    client_class.assert_not_called()


# ----------------------------------------------------------------------
# Caching
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_http(mock_redis):
    # Deliberately has no "abstract" key: entries written before the
    # abstract field existed must still deserialize
    cached_payload = json.dumps(
        {
            "v": 1,
            "status": "verified",
            "doi": "10.5555/3295222",
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": ["Ashish Vaswani"],
            "venue": "NeurIPS",
            "provider": "crossref",
            "match_score": 1.0,
            "reason": None,
        }
    )
    mock_redis.get = AsyncMock(return_value=cached_payload)
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Attention Is All You Need", doi="10.5555/3295222")

    with patch("httpx.AsyncClient") as client_class:
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED
    assert result.from_cache is True
    assert result.doi == "10.5555/3295222"
    assert result.provider == "crossref"
    assert result.abstract is None  # legacy entry, no abstract key
    client_class.assert_not_called()


@pytest.mark.asyncio
async def test_redis_down_still_verifies(mock_redis):
    mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
    mock_redis.set = AsyncMock(side_effect=ConnectionError("redis down"))
    verifier = make_verifier(mock_redis)
    source = SourceInput(title="Attention Is All You Need", doi="10.5555/3295222")
    client = make_client([make_response(200, {"message": CROSSREF_WORK})])

    with patch("httpx.AsyncClient", return_value=client):
        result = await verifier.verify_source(source)

    assert result.status == VerificationStatus.VERIFIED


# ----------------------------------------------------------------------
# Batch API
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_sources_preserves_order(mock_redis):
    verifier = make_verifier(mock_redis)
    sources = [
        SourceInput(title="Attention Is All You Need", doi="10.5555/3295222"),
        SourceInput(title=""),  # insufficient metadata
        SourceInput(title="Nonexistent Paper About Nothing"),
    ]

    def dispatch(url, params=None, headers=None):
        if "/works/10.5555/3295222" in url:
            return make_response(200, {"message": CROSSREF_WORK})
        return empty_dispatch(url, params, headers)

    client = make_client(dispatch)
    with patch("httpx.AsyncClient", return_value=client):
        results = await verifier.verify_sources(sources)

    assert [r.status for r in results] == [
        VerificationStatus.VERIFIED,
        VerificationStatus.UNRESOLVABLE,
        VerificationStatus.NOT_FOUND,
    ]


# ----------------------------------------------------------------------
# Abstract extraction (parsers + serialization, no mocks)
# ----------------------------------------------------------------------


def test_crossref_parser_missing_abstract():
    item = {k: v for k, v in CROSSREF_WORK.items() if k != "abstract"}
    assert CitationVerifier._parse_crossref_item(item)["abstract"] is None


@pytest.mark.parametrize(
    "inverted",
    [
        None,
        "not-a-dict",
        {},
        {"word": "bad-positions"},
        {"word": [-1]},
    ],
)
def test_openalex_parser_malformed_inverted_index(inverted):
    work = {"title": "T", "abstract_inverted_index": inverted}
    assert CitationVerifier._parse_openalex_work(work)["abstract"] is None


def test_arxiv_parser_missing_summary():
    feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <published>2017-06-12T17:57:34Z</published>
  </entry>
</feed>
"""
    entries = CitationVerifier._parse_arxiv_feed(feed)
    assert entries[0]["abstract"] is None


def test_abstract_capped_at_max_length():
    paper = {"title": "T", "abstract": "word " * 1000}  # ~5000 chars
    candidate = CitationVerifier._parse_s2_paper(paper)
    assert len(candidate["abstract"]) == MAX_ABSTRACT_LENGTH


def test_result_roundtrip_preserves_abstract():
    result = VerificationResult(
        status=VerificationStatus.VERIFIED, title="T", abstract="Some abstract"
    )
    data = result.to_dict()
    assert data["abstract"] == "Some abstract"
    assert VerificationResult.from_dict(data).abstract == "Some abstract"


def test_from_dict_without_abstract_key():
    """Old cache entries (pre-abstract schema) deserialize to abstract=None"""
    result = VerificationResult.from_dict({"status": "verified", "title": "T"})
    assert result.abstract is None


# ----------------------------------------------------------------------
# Pure normalization helpers (no mocks)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Attention Is All You Need!", "attention is all you need"),
        ("  Café — Über-Étude  ", "cafe uber etude"),
        ("Deep   Learning:\tA Survey", "deep learning a survey"),
        ("Глибинне навчання: огляд", "глибинне навчання огляд"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_title(raw, expected):
    assert normalize_title(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://doi.org/10.1234/ABC", "10.1234/abc"),
        ("http://dx.doi.org/10.2/Z", "10.2/z"),
        ("doi:10.1/X", "10.1/x"),
        ("10.5555/3295222", "10.5555/3295222"),
        ("not-a-doi", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected
