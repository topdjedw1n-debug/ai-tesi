from functools import partial

import httpx
import pytest

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.background_jobs import _build_source_pack
from app.services.citation_verifier import VerificationResult, VerificationStatus
from tests.test_source_pack_rebuild import (
    fake_pack,
    make_settings,
    seed_document,
)


def _preflight_settings(**overrides):
    values = {
        "SOURCE_PACK_PREFLIGHT_ENABLED": True,
        "CITATION_VERIFICATION_ENABLED": True,
        "CITATION_VERIFICATION_POLICY": "strict",
        "CLAIM_VERIFICATION_ENABLED": True,
        "CLAIM_VERIFICATION_BLOCKING": True,
        "SOURCE_PACK_TARGET_SIZE": 1,
        "SOURCE_PACK_MIN_VERIFIED": 1,
        "SOURCE_PACK_CANDIDATE_RESERVE_SIZE": 2,
        "PROVENANCE_LEDGER_ENABLED": True,
    }
    values.update(overrides)
    return make_settings(**values)


def _verified_result(pack: SourcePack) -> VerificationResult:
    source = pack.sources[0].source
    return VerificationResult(
        status=VerificationStatus.VERIFIED,
        title=source.title,
        authors=source.authors,
        year=source.year,
        abstract=source.abstract,
        provider="crossref",
        match_score=1.0,
    )


def _release_pack(document_id: int) -> SourcePack:
    pack = fake_pack(document_id)
    pack.sources[0].source.source_type = "journal-article"
    for index in range(1, 24):
        pack.sources.append(
            PackedSource(
                SourceDoc(
                    title=f"Verified academic source {index}",
                    authors=[f"Author {index}"],
                    year=2020 + (index % 6),
                    abstract=f"Evidence for the document topic {index}",
                    doi=f"10.1000/release-{index}",
                    source_type="journal-article",
                ),
                f"Author{index}2020",
                0.9 - index / 1000,
            )
        )
    return pack


def _verified_inputs(inputs) -> list[VerificationResult]:
    return [
        VerificationResult(
            status=VerificationStatus.VERIFIED,
            title=item.title,
            authors=item.authors,
            year=item.year,
            doi=item.doi,
            abstract="Verified evidence",
            provider="crossref",
            match_score=1.0,
        )
        for item in inputs
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("crossref_status", [200, 503])
async def test_initial_retrieval_distinguishes_empty_results_from_http_outage(
    db_session, monkeypatch, crossref_status
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    _, document = await seed_document(
        db_session,
        f"retrieval-http-{crossref_status}@example.com",
        sections=["Introduzione"],
    )
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.host == "api.crossref.org":
            return httpx.Response(crossref_status, json={"message": {"items": []}})
        assert request.url.host == "api.openalex.org"
        return httpx.Response(200, json={"results": []})

    monkeypatch.setattr(
        "app.services.ai_pipeline.rag_retriever.httpx.AsyncClient",
        partial(httpx.AsyncClient, transport=httpx.MockTransport(respond)),
    )

    pack = await _build_source_pack(db_session, document)

    assert {request.url.host for request in requests} == {
        "api.crossref.org",
        "api.openalex.org",
    }
    assert pack.sources == []
    assert pack.underfilled is True
    assert bool(pack.provider_errors) is (crossref_status == 503)
    assert all("503" in error for error in pack.provider_errors)
