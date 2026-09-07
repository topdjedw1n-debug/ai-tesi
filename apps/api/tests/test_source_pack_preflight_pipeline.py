from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.core.exceptions import CitationIntegrityError
from app.models.document import AIGenerationJob, Document, DocumentProvenance
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.background_jobs import BackgroundJobService, _build_source_pack
from app.services.citation_verifier import VerificationResult, VerificationStatus
from app.services.source_verification_stage import load_source_pack, persist_source_pack
from tests.release_profile import RELEASE_PROFILE
from tests.test_source_pack_rebuild import (
    fake_pack,
    make_settings,
    rebuild_harness,
    seed_document,
)


@pytest.fixture(autouse=True)
def _stub_claim_judge(monkeypatch):
    """Source-preflight tests must never call a paid claim judge."""
    monkeypatch.setattr(
        "app.services.background_jobs.verify_section_claims",
        AsyncMock(
            return_value=(
                {
                    "total": 1,
                    "checked": 1,
                    "counts": {"supported": 1},
                    "claims": [],
                },
                [],
                1,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.background_jobs._run_claim_verification_stage",
        AsyncMock(),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("context_only", [True, False])
async def test_retry_refreshes_unfrozen_persisted_pack_before_writing(
    db_session, monkeypatch, context_only
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        _preflight_settings(
            SOURCE_PACK_TARGET_SIZE=24,
            SOURCE_PACK_MIN_VERIFIED=18,
            SOURCE_PACK_CANDIDATE_RESERVE_SIZE=48,
        ),
    )
    user, document = await seed_document(
        db_session,
        f"retry-provisional-{context_only}@example.com",
        sections=["Introduzione"],
    )
    incomplete = fake_pack(int(document.id))
    incomplete.underfilled = True
    incomplete.provider_errors = ["crossref: temporary outage"]
    if context_only:
        incomplete.context_sources = incomplete.sources
        incomplete.sources = []
        incomplete.context_sources[0].citation_key = ""
    await persist_source_pack(db_session, int(document.id), incomplete)
    persisted = await load_source_pack(db_session, int(document.id))
    assert persisted is not None
    assert len(persisted.all_sources()) == 1

    recovered = _release_pack(int(document.id))
    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        build = stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(return_value=recovered),
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(side_effect=load_source_pack),
            )
        )
        verifier = MagicMock()
        verifier.verify_sources = AsyncMock(side_effect=_verified_inputs)
        stack.enter_context(
            patch(
                "app.services.background_jobs.CitationVerifier", return_value=verifier
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._run_citation_verification_stage",
                AsyncMock(),
            )
        )

        await BackgroundJobService.generate_full_document(
            document_id=int(document.id), user_id=int(user.id)
        )

        assert build.await_count == 2
        assert build.await_args_list[0].kwargs.get("section_titles") is None
        assert build.await_args_list[1].kwargs["section_titles"] == ["Introduzione"]
        writer_pack = mocks["generate_section"].call_args.kwargs["source_pack"]
        assert len(writer_pack.sources) == 24
        assert all(
            item.source.verification_status == "verified"
            for item in writer_pack.sources
        )
        mocks["export_document"].assert_awaited_once()

    events = (
        (
            await db_session.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.document_id == int(document.id))
                .order_by(DocumentProvenance.id)
            )
        )
        .scalars()
        .all()
    )
    event_types = [event.event_type for event in events]
    assert "source_pack_insufficient" not in event_types
    assert event_types.index("source_pack_preflight") < event_types.index(
        "section_writer"
    )


@pytest.mark.asyncio
async def test_legacy_resume_still_reuses_persisted_keys(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(SOURCE_PACK_PREFLIGHT_ENABLED=False),
    )
    user, document = await seed_document(
        db_session,
        "legacy-persisted-resume@example.com",
        sections=["Introduzione", "Futuro"],
        completed=1,
    )
    pack = fake_pack(int(document.id))
    await persist_source_pack(db_session, int(document.id), pack)

    with ExitStack() as stack:
        mocks = rebuild_harness(
            stack, db_session, redis_checkpoint='{"last_completed_section_index": 1}'
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(side_effect=load_source_pack),
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=int(document.id), user_id=int(user.id)
        )

        mocks["build_pack"].assert_not_awaited()
        mocks["generate_section"].assert_awaited_once()
        writer_pack = mocks["generate_section"].call_args.kwargs["source_pack"]
        assert writer_pack.keys() == pack.keys()


@pytest.mark.asyncio
async def test_preflight_event_precedes_writer_and_writer_gets_verified_pack(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "preflight-pass@example.com",
        sections=["Introduzione"],
    )
    pack = fake_pack(int(document.id))

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        build = AsyncMock(side_effect=lambda *args, **kwargs: pack)
        stack.enter_context(
            patch("app.services.background_jobs._build_source_pack", build)
        )
        verifier = MagicMock()
        verifier.verify_sources = AsyncMock(return_value=[_verified_result(pack)])
        stack.enter_context(
            patch(
                "app.services.background_jobs.CitationVerifier", return_value=verifier
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._run_citation_verification_stage",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(side_effect=load_source_pack),
            )
        )

        await BackgroundJobService.generate_full_document(
            document_id=int(document.id), user_id=int(user.id)
        )

        writer_pack = mocks["generate_section"].call_args.kwargs["source_pack"]
        assert writer_pack.sources[0].source.verification_status == "verified"

    events = (
        (
            await db_session.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.document_id == int(document.id))
                .order_by(DocumentProvenance.id)
            )
        )
        .scalars()
        .all()
    )
    event_types = [event.event_type for event in events]
    assert event_types.index("source_pack_preflight") < event_types.index(
        "section_writer"
    )


@pytest.mark.asyncio
async def test_preflight_keeps_initial_topic_sources_when_adding_section_candidates(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        _preflight_settings(
            SOURCE_PACK_TARGET_SIZE=24,
            SOURCE_PACK_MIN_VERIFIED=18,
            SOURCE_PACK_CANDIDATE_RESERVE_SIZE=48,
        ),
    )
    user, document = await seed_document(
        db_session,
        "preflight-merge@example.com",
        sections=["Introduzione"],
    )
    initial = _release_pack(int(document.id))
    initial.sources = initial.sources[:18]
    initial.bilingual = True
    section_specific = SourcePack(
        document_id=int(document.id),
        topic=str(document.topic),
        sources=[
            PackedSource(
                SourceDoc(
                    title="Section-specific verified evidence",
                    authors=["Bianchi"],
                    year=2023,
                    abstract="Evidence for the promised section",
                    doi="10.1000/section-specific",
                    source_type="journal-article",
                ),
                "Bianchi2023",
                0.8,
            )
        ],
    )
    empty_top_up = SourcePack(
        document_id=int(document.id),
        topic=str(document.topic),
        sources=[],
    )

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        mocks["generate_section"].return_value = {
            "section_title": "Introduzione",
            "section_index": 1,
            "content": "Testo (Bianchi, 2023) con il 30% di dati.",
            "content_with_markers": "Testo [Bianchi2023] con il 30% di dati.",
            "pack_keys_used": ["Bianchi2023"],
            "citations": [],
            "bibliography": [],
            "sources_used": 1,
            "humanized": False,
        }
        stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(side_effect=[initial, section_specific, empty_top_up]),
            )
        )
        verifier = MagicMock()
        verifier.verify_sources = AsyncMock(side_effect=_verified_inputs)
        stack.enter_context(
            patch(
                "app.services.background_jobs.CitationVerifier", return_value=verifier
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(side_effect=load_source_pack),
            )
        )

        await BackgroundJobService.generate_full_document(
            document_id=int(document.id), user_id=int(user.id)
        )

        writer_pack = mocks["generate_section"].call_args.kwargs["source_pack"]
        writer_titles = {item.source.title for item in writer_pack.sources}
        assert {item.source.title for item in initial.sources} <= writer_titles
        assert section_specific.sources[0].source.title in writer_titles
        assert writer_pack.bilingual is True


@pytest.mark.asyncio
async def test_complete_release_profile_runs_preflight_before_writer(
    db_session, monkeypatch
):
    runtime = make_settings(**RELEASE_PROFILE)
    monkeypatch.setattr("app.services.background_jobs.settings", runtime)
    user, document = await seed_document(
        db_session,
        "release-profile-pipeline@example.com",
        sections=["Introduzione"],
    )
    pack = _release_pack(int(document.id))

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(return_value=pack),
            )
        )
        verifier = MagicMock()
        verifier.verify_sources = AsyncMock(side_effect=_verified_inputs)
        stack.enter_context(
            patch(
                "app.services.background_jobs.CitationVerifier",
                return_value=verifier,
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._check_panel_quality",
                AsyncMock(
                    return_value={
                        "overall_score": 90.0,
                        "passed": True,
                        "critical_override": False,
                        "reviews": [],
                    }
                ),
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._run_citation_verification_stage",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(side_effect=load_source_pack),
            )
        )

        await BackgroundJobService.generate_full_document(
            document_id=int(document.id), user_id=int(user.id)
        )

        assert mocks["generate_section"].call_count == 1
        writer_pack = mocks["generate_section"].call_args.kwargs["source_pack"]
        assert len(writer_pack.sources) == 24
        assert all(
            item.source.verification_status == "verified"
            for item in writer_pack.sources
        )

    event_types = [
        event.event_type
        for event in (
            (
                await db_session.execute(
                    select(DocumentProvenance)
                    .where(DocumentProvenance.document_id == int(document.id))
                    .order_by(DocumentProvenance.id)
                )
            )
            .scalars()
            .all()
        )
    ]
    assert event_types.index("source_pack_preflight") < event_types.index(
        "section_writer"
    )


@pytest.mark.asyncio
async def test_insufficient_preflight_blocks_before_writer(db_session, monkeypatch):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "preflight-fail@example.com",
        sections=["Introduzione"],
    )
    pack = fake_pack(int(document.id))

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(side_effect=lambda *args, **kwargs: pack),
            )
        )
        verifier = MagicMock()
        verifier.verify_sources = AsyncMock(
            side_effect=lambda inputs: [
                VerificationResult(status=VerificationStatus.NOT_FOUND) for _ in inputs
            ]
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs.CitationVerifier", return_value=verifier
            )
        )

        with pytest.raises(CitationIntegrityError, match="only 0 verified"):
            await BackgroundJobService.generate_full_document(
                document_id=int(document.id), user_id=int(user.id)
            )
        assert mocks["generate_section"].called is False

    refreshed = await db_session.get(Document, int(document.id))
    assert refreshed.status == "failed_quality"


@pytest.mark.asyncio
async def test_underfilled_relaxed_pack_stops_before_writer_or_preflight(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "underfilled-before-writing@example.com",
        sections=["Introduzione"],
    )
    weak = SourcePack(
        document_id=int(document.id),
        topic=str(document.topic),
        sources=[],
        underfilled=True,
        context_sources=[
            PackedSource(
                SourceDoc(
                    title=f"Weak context {index}",
                    authors=[f"Author {index}"],
                    year=2020,
                    abstract="Tangential context",
                ),
                "",
                0.2,
            )
            for index in range(24)
        ],
    )

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(return_value=weak),
            )
        )
        verifier_class = stack.enter_context(
            patch("app.services.background_jobs.CitationVerifier")
        )

        with pytest.raises(
            CitationIntegrityError, match="Automatic source selection needs review"
        ) as stopped:
            await BackgroundJobService.generate_full_document(
                document_id=int(document.id), user_id=int(user.id)
            )

        assert mocks["generate_section"].called is False
        verifier_class.assert_not_called()
        assert "PDF sources are optional" in str(stopped.value)

    refreshed = await db_session.get(Document, int(document.id))
    assert refreshed.status == "failed_quality"
    event = (
        await db_session.execute(
            select(DocumentProvenance).where(
                DocumentProvenance.document_id == int(document.id),
                DocumentProvenance.event_type == "source_pack_insufficient",
            )
        )
    ).scalar_one()
    assert event.payload["citable_sources"] == 0
    assert event.payload["context_sources"] == 24


@pytest.mark.asyncio
async def test_underfilled_pack_with_provider_outage_remains_retryable(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "underfilled-provider-outage@example.com",
        sections=["Introduzione"],
    )
    unavailable = SourcePack(
        document_id=int(document.id),
        topic=str(document.topic),
        sources=[],
        underfilled=True,
        provider_errors=["crossref: temporary outage"],
    )

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(return_value=unavailable),
            )
        )
        verifier_class = stack.enter_context(
            patch("app.services.background_jobs.CitationVerifier")
        )

        with pytest.raises(RuntimeError, match="providers were unavailable"):
            await BackgroundJobService.generate_full_document(
                document_id=int(document.id), user_id=int(user.id)
            )

        assert mocks["generate_section"].called is False
        verifier_class.assert_not_called()

    insufficient_events = (
        await db_session.execute(
            select(DocumentProvenance).where(
                DocumentProvenance.document_id == int(document.id),
                DocumentProvenance.event_type == "source_pack_insufficient",
            )
        )
    ).scalars()
    assert list(insufficient_events) == []


@pytest.mark.asyncio
async def test_resume_reuses_frozen_pack_without_retrieval_or_reverification(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "preflight-resume@example.com",
        sections=["Introduzione", "Discussione"],
        completed=1,
    )
    pack = fake_pack(int(document.id))
    pack.sources[0].source.verification_status = "verified"
    pack.sources[0].source.canonical_metadata = {"status": "verified"}
    await persist_source_pack(db_session, int(document.id), pack)

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        mocks["build_pack"].reset_mock()
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(return_value=pack),
            )
        )
        verifier_class = stack.enter_context(
            patch("app.services.background_jobs.CitationVerifier")
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._run_citation_verification_stage",
                AsyncMock(),
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=int(document.id), user_id=int(user.id)
        )

        assert mocks["build_pack"].called is False
        verifier_class.assert_not_called()
        assert mocks["generate_section"].call_count == 1


@pytest.mark.asyncio
async def test_resume_rejects_frozen_pack_without_verification_proof(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "preflight-invalid-proof@example.com",
        sections=["Introduzione", "Discussione"],
        completed=1,
    )
    pack = fake_pack(int(document.id))
    pack.sources[0].source.verification_status = "failed"
    pack.sources[0].source.canonical_metadata = {"status": "verified"}

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(return_value=pack),
            )
        )

        with pytest.raises(CitationIntegrityError, match="no valid preflight proof"):
            await BackgroundJobService.generate_full_document(
                document_id=int(document.id), user_id=int(user.id)
            )

        assert mocks["generate_section"].called is False


@pytest.mark.asyncio
async def test_existing_job_digest_reuses_pack_before_first_completed_section(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "preflight-frozen-before-writer@example.com",
        sections=["Introduzione"],
    )
    pack = fake_pack(int(document.id))
    pack.sources[0].source.verification_status = "verified"
    pack.sources[0].source.canonical_metadata = {"status": "verified"}
    await persist_source_pack(db_session, int(document.id), pack)
    digest = pack.sha256()
    job = AIGenerationJob(
        user_id=int(user.id),
        document_id=int(document.id),
        job_type="full_document",
        status="running",
        lease_owner="resume-worker",
        lease_token="resume-token",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        source_pack_sha256=digest,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        mocks["build_pack"].reset_mock()
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(return_value=pack),
            )
        )
        verifier_class = stack.enter_context(
            patch("app.services.background_jobs.CitationVerifier")
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._run_citation_verification_stage",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._export_document_with_fence",
                AsyncMock(
                    return_value={
                        "download_url": "https://example.com/document.docx",
                        "format": "docx",
                    }
                ),
            )
        )

        await BackgroundJobService.generate_full_document(
            document_id=int(document.id),
            user_id=int(user.id),
            job_id=int(job.id),
            lease_owner="resume-worker",
            lease_token="resume-token",
        )

        assert mocks["build_pack"].called is False
        verifier_class.assert_not_called()
        assert mocks["generate_section"].call_count == 1

    refreshed_job = await db_session.get(AIGenerationJob, int(job.id))
    assert refreshed_job.source_pack_sha256 == digest


@pytest.mark.asyncio
async def test_status_tamper_after_writing_blocks_before_export(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        "preflight-status-tamper@example.com",
        sections=["Introduzione"],
    )
    candidates = fake_pack(int(document.id))

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        stack.enter_context(
            patch(
                "app.services.background_jobs._build_source_pack",
                AsyncMock(side_effect=lambda *args, **kwargs: candidates),
            )
        )
        verifier = MagicMock()
        verifier.verify_sources = AsyncMock(return_value=[_verified_result(candidates)])
        stack.enter_context(
            patch(
                "app.services.background_jobs.CitationVerifier", return_value=verifier
            )
        )

        async def load_and_tamper(db, document_id):
            loaded = await load_source_pack(db, document_id)
            if loaded is not None and mocks["generate_section"].called:
                loaded.sources[0].source.verification_status = "failed"
            return loaded

        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(side_effect=load_and_tamper),
            )
        )

        with pytest.raises(CitationIntegrityError, match="lost verification proof"):
            await BackgroundJobService.generate_full_document(
                document_id=int(document.id), user_id=int(user.id)
            )

        assert mocks["generate_section"].call_count == 1
        assert mocks["export_document"].called is False
