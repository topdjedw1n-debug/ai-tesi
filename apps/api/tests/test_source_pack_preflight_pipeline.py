from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.exceptions import CitationIntegrityError
from app.models.document import AIGenerationJob, Document, DocumentProvenance
from app.services.ai_pipeline.source_pack import SourcePack
from app.services.background_jobs import BackgroundJobService
from app.services.citation_verifier import VerificationResult, VerificationStatus
from app.services.source_verification_stage import load_source_pack, persist_source_pack
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
    return make_settings(
        SOURCE_PACK_PREFLIGHT_ENABLED=True,
        CITATION_VERIFICATION_ENABLED=True,
        CITATION_VERIFICATION_POLICY="strict",
        CLAIM_VERIFICATION_ENABLED=True,
        CLAIM_VERIFICATION_BLOCKING=True,
        SOURCE_PACK_TARGET_SIZE=1,
        SOURCE_PACK_MIN_VERIFIED=1,
        SOURCE_PACK_CANDIDATE_RESERVE_SIZE=2,
        PROVENANCE_LEDGER_ENABLED=True,
        **overrides,
    )


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
