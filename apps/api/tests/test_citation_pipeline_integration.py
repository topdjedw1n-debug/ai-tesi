from app.services.generation_profile import generation_profile_sha256

"""
Integration tests for citation verification in the generation pipeline.

Hybrid harness: service mocks follow test_background_jobs_recovery.py, but the
DB is the REAL db_session (SQLite) wrapped behind AsyncSessionLocal so that
DocumentSource/DocumentProvenance rows and the partial unique DOI index are
actually exercised.
"""

import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.exceptions import CitationIntegrityError
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    DocumentSource,
)
from app.services.background_jobs import (
    BackgroundJobService,
    _map_verification_status,
    _persist_cited_sources,
)
from app.services.citation_verifier import VerificationResult, VerificationStatus
from app.services.generation_contract import generation_contract_sha256

# ----------------------------------------------------------------------
# Fixtures and helpers
# ----------------------------------------------------------------------

SOURCE_A = {
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani"],
    "year": 2017,
    "abstract": None,
    "paper_id": None,
    "venue": "NeurIPS",
    "citation_count": 100,
    "url": None,
    "doi": "10.5555/attention",
}
SOURCE_B = {
    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
    "authors": ["Jacob Devlin"],
    "year": 2019,
    "abstract": None,
    "paper_id": None,
    "venue": "NAACL",
    "citation_count": 50,
    "url": None,
    "doi": None,
}


def make_settings(**overrides) -> Settings:
    defaults = {
        "QUALITY_GATES_ENABLED": False,
        "QUALITY_MAX_REGENERATE_ATTEMPTS": 0,
        "CITATION_VERIFICATION_ENABLED": True,
        "CITATION_VERIFICATION_POLICY": "strict",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def vres(status, title="T", score=1.0, doi=None) -> VerificationResult:
    return VerificationResult(
        status=status,
        title=title,
        match_score=score,
        doi=doi,
        provider="crossref" if status == VerificationStatus.VERIFIED else None,
    )


def verifier_by_title(status_by_title):
    """verify_sources side_effect mapping each SourceInput by title"""

    def _side_effect(inputs):
        return [
            status_by_title.get(
                s.title, vres(VerificationStatus.VERIFIED, title=s.title)
            )
            for s in inputs
        ]

    return _side_effect


async def seed_document(db_session, section_titles=("Introduction", "Methods")):
    user = User(email="pipeline-test@example.com", full_name="Pipeline Tester")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    document = Document(
        user_id=user.id,
        title="Citation Test Thesis",
        topic="AI in Education",
        status="draft",
        language="en",
        ai_provider="openai",
        ai_model="gpt-4",
        additional_requirements="Extracted university methodology",
        requirements_file_processed=True,
        citation_style="apa",
        outline={"sections": [{"title": t} for t in section_titles]},
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return user, document


def section_result(index, cited_sources):
    return {
        "section_title": f"Section {index}",
        "section_index": index,
        "content": f"Generated content for section {index}",
        "citations": [],
        "bibliography": ["ref"],
        "sources_used": len(cited_sources),
        "humanized": False,
        "cited_sources": cited_sources,
    }


def pipeline_harness(
    stack: ExitStack,
    db_session,
    mock_redis,
    *,
    generate_side_effect,
    verifier_side_effect=None,
    grammar_side_effect=None,
):
    """Apply the standard patch block; returns dict of mocks for assertions"""
    mocks = {}

    gen_class = stack.enter_context(
        patch("app.services.background_jobs.SectionGenerator")
    )
    generator = MagicMock()
    generator.generate_section = AsyncMock(side_effect=generate_side_effect)
    gen_class.return_value = generator
    mocks["generate_section"] = generator.generate_section

    humanizer_class = stack.enter_context(
        patch("app.services.background_jobs.Humanizer")
    )
    humanizer = MagicMock()
    humanizer.humanize = AsyncMock(
        side_effect=lambda *a, **k: k.get("text", "Humanized")
    )
    humanizer_class.return_value = humanizer

    quality_class = stack.enter_context(
        patch("app.services.background_jobs.QualityValidator")
    )
    quality_validator = MagicMock()
    quality_validator.validate_section = AsyncMock(
        return_value={"overall_score": 85.0, "issues": []}
    )
    quality_class.return_value = quality_validator

    stack.enter_context(
        patch(
            "app.services.background_jobs._check_grammar_quality",
            AsyncMock(
                side_effect=grammar_side_effect if grammar_side_effect else None,
                return_value=(95.0, 0, "passed", None),
            ),
        )
    )
    stack.enter_context(
        patch(
            "app.services.background_jobs._check_plagiarism_quality",
            AsyncMock(return_value=(5.0, 95.0, "passed", None)),
        )
    )
    stack.enter_context(
        patch(
            "app.services.background_jobs._check_ai_detection_quality",
            AsyncMock(
                side_effect=lambda content, *a, **k: (
                    20.0,
                    content,
                    "mock",
                    "passed",
                    None,
                )
            ),
        )
    )

    manager = stack.enter_context(patch("app.services.background_jobs.manager"))
    manager.send_progress = AsyncMock()
    mocks["manager"] = manager

    doc_service_class = stack.enter_context(
        patch("app.services.background_jobs.DocumentService")
    )
    doc_service = MagicMock()
    doc_service.export_document = AsyncMock(
        return_value={"download_url": "https://example.com/doc.docx"}
    )
    doc_service_class.return_value = doc_service
    mocks["export_document"] = doc_service.export_document

    stack.enter_context(
        patch(
            "app.services.background_jobs.get_redis",
            AsyncMock(return_value=mock_redis),
        )
    )

    session_class = stack.enter_context(
        patch("app.services.background_jobs.database.AsyncSessionLocal")
    )
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=db_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    session_class.return_value = mock_session

    verifier_class = stack.enter_context(
        patch("app.services.background_jobs.CitationVerifier")
    )
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        side_effect=(
            verifier_side_effect if verifier_side_effect else verifier_by_title({})
        )
    )
    verifier_class.return_value = verifier
    mocks["verifier_class"] = verifier_class
    mocks["verify_sources"] = verifier.verify_sources

    stack.enter_context(patch("app.services.notification_service.notification_service"))

    return mocks


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


def ws_stages(mocks) -> list[str]:
    return [
        call.args[1].get("stage")
        for call in mocks["manager"].send_progress.call_args_list
        if len(call.args) > 1 and isinstance(call.args[1], dict)
    ]


async def provenance_events(db_session, document_id) -> dict[str, dict]:
    result = await db_session.execute(
        select(DocumentProvenance).where(DocumentProvenance.document_id == document_id)
    )
    return {row.event_type: row.payload for row in result.scalars().all()}


# ----------------------------------------------------------------------
# Pipeline scenarios
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strict_block_survives_async_wrapper(db_session, mock_redis, monkeypatch):
    """Through generate_full_document_async: job failed, document failed_quality"""
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(CITATION_VERIFICATION_POLICY="strict"),
    )
    user, document = await seed_document(db_session)
    document_id = document.id

    job = AIGenerationJob(
        user_id=user.id,
        document_id=document_id,
        job_type="document_generation",
        status="queued",
        progress=0,
        request_payload={
            "additional_requirements": None,
            "profile_sha256": generation_profile_sha256(document, user.id),
            "generation_contract_sha256": generation_contract_sha256(
                document, None, None
            ),
        },
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    job_id = job.id

    with ExitStack() as stack:
        # Isolate the citation failure under test; academic gates have
        # independent leased-pipeline and release regression coverage.
        stack.enter_context(
            patch(
                "app.services.background_jobs.run_academic_review",
                AsyncMock(return_value={"status": "passed"}),
            )
        )
        stack.enter_context(
            patch("app.services.background_jobs.prepare_final_plan", AsyncMock())
        )
        mocks = pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[
                section_result(1, [SOURCE_A]),
                section_result(2, [SOURCE_B]),
            ],
            verifier_side_effect=verifier_by_title(
                {
                    SOURCE_A["title"]: vres(
                        VerificationStatus.NOT_FOUND, title=SOURCE_A["title"]
                    )
                }
            ),
        )
        try:
            await BackgroundJobService.generate_full_document_async(
                document_id=document_id, user_id=user.id, job_id=job_id
            )
        except CitationIntegrityError:
            pass  # wrapper may re-raise; both behaviors acceptable

        ws_messages = [
            call.args[1]
            for call in mocks["manager"].send_progress.call_args_list
            if len(call.args) > 1 and isinstance(call.args[1], dict)
        ]
        assert any(m.get("type") == "job_failed" for m in ws_messages)

    refreshed_job = (
        await db_session.execute(
            select(AIGenerationJob).where(AIGenerationJob.id == job_id)
        )
    ).scalar_one()
    assert refreshed_job.status == "failed"
    assert "Citation verification failed" in (refreshed_job.error_message or "")

    refreshed = (
        await db_session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one()
    assert refreshed.status == "failed_quality"  # NOT overwritten by 'failed'


# ----------------------------------------------------------------------
# Helper units
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_cited_sources_unit(db_session):
    user, document = await seed_document(db_session)
    document_id = document.id

    # Empty titles are skipped
    await _persist_cited_sources(
        db_session, document_id, None, [dict(SOURCE_A, title="")]
    )
    # Same payload twice -> still one row
    await _persist_cited_sources(db_session, document_id, None, [SOURCE_A])
    await _persist_cited_sources(db_session, document_id, None, [SOURCE_A])

    sources = (
        (
            await db_session.execute(
                select(DocumentSource).where(DocumentSource.document_id == document_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(sources) == 1

    # A failing commit must not raise and must leave the session usable
    original_commit = db_session.commit
    db_session.commit = AsyncMock(side_effect=RuntimeError("db hiccup"))
    try:
        await _persist_cited_sources(db_session, document_id, None, [SOURCE_B])
    finally:
        db_session.commit = original_commit

    count_after = len(
        (
            await db_session.execute(
                select(DocumentSource).where(DocumentSource.document_id == document_id)
            )
        )
        .scalars()
        .all()
    )
    assert count_after == 1  # nothing half-written, session still works


@pytest.mark.parametrize(
    ("status", "score", "expected"),
    [
        (VerificationStatus.VERIFIED, 1.0, "verified"),
        (VerificationStatus.VERIFIED, 0.90, "verified"),
        (VerificationStatus.VERIFIED, 0.89, "mismatched"),
        (VerificationStatus.VERIFIED, None, "verified"),
        (VerificationStatus.NOT_FOUND, None, "not_found"),
        (VerificationStatus.UNRESOLVABLE, None, "failed"),
    ],
)
def test_map_verification_status_unit(status, score, expected):
    result = VerificationResult(status=status, match_score=score)
    assert _map_verification_status(result) == expected


# ----------------------------------------------------------------------
# Generator contract (SSE byte-compat)
# ----------------------------------------------------------------------

LEGACY_RESULT_KEYS = {
    "section_title",
    "section_index",
    "content",
    "citations",
    "bibliography",
    "sources_used",
    "humanized",
    # Honest writer trail (Validation-6): planned vs actual model + fallback
    # flag are unconditional — a provider outage must never swap the writer
    # invisibly.
    "writer_planned",
    "writer_actual",
    "writer_fallback_used",
}


async def _generate_with_flag(monkeypatch, enabled: bool):
    from app.services.ai_pipeline.generator import SectionGenerator
    from app.services.ai_pipeline.rag_retriever import SourceDoc

    monkeypatch.setattr(
        "app.services.ai_pipeline.generator.settings",
        make_settings(CITATION_VERIFICATION_ENABLED=enabled),
    )

    generator = SectionGenerator()
    generator.rag_retriever = MagicMock()
    generator.rag_retriever.retrieve_sources = AsyncMock(
        return_value=[
            SourceDoc(
                title="Attention Is All You Need",
                authors=["Ashish Vaswani"],
                year=2017,
                doi="10.5555/attention",
            )
        ]
    )
    generator._call_ai_with_fallback = AsyncMock(
        return_value="Attention mechanisms dominate [Vaswani, 2017]."
    )
    generator.training_collector = MagicMock()
    generator.training_collector.collect_generation_sample = AsyncMock()

    document = Document(
        id=1,
        user_id=1,
        title="T",
        topic="Transformers",
        language="en",
    )
    return await generator.generate_section(
        document=document,
        section_title="Background",
        section_index=1,
        provider="openai",
        model="gpt-4",
    )


@pytest.mark.asyncio
async def test_generator_flag_off_keys_unchanged(monkeypatch):
    """Locks the SSE byte-compat contract: no new keys when flag is off"""
    result = await _generate_with_flag(monkeypatch, enabled=False)
    assert set(result.keys()) == LEGACY_RESULT_KEYS


@pytest.mark.asyncio
async def test_generator_flag_on_adds_serializable_cited_sources(monkeypatch):
    result = await _generate_with_flag(monkeypatch, enabled=True)
    assert set(result.keys()) == LEGACY_RESULT_KEYS | {"cited_sources"}
    assert isinstance(result["cited_sources"], list)
    assert result["cited_sources"][0]["doi"] == "10.5555/attention"
    json.dumps(result)  # SSE serializability: must not raise


# ----------------------------------------------------------------------
# Frozen frontend contract (see app/schemas/provenance.py)
# ----------------------------------------------------------------------
