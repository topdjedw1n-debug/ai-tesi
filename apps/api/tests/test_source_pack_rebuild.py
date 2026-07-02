"""Pipeline tests for the post-outline source-pack rebuild (fix-wave 2).

Fresh generation must rebuild the pack with the outline's section titles;
resume-from-checkpoint must NOT rebuild (already-generated sections cite the
persisted keys — a rebuild would re-key the pack and orphan them).
"""

import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.auth import User
from app.models.document import Document, DocumentSection
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.background_jobs import BackgroundJobService


def make_settings(**overrides) -> Settings:
    defaults = {
        "QUALITY_GATES_ENABLED": False,
        "QUALITY_MAX_REGENERATE_ATTEMPTS": 0,
        "CITATION_VERIFICATION_ENABLED": False,
        "CLAIM_VERIFICATION_ENABLED": False,
        "PROVENANCE_LEDGER_ENABLED": False,
        "SOURCE_GROUNDING_ENABLED": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def fake_pack(document_id: int) -> SourcePack:
    return SourcePack(
        document_id=document_id,
        topic="AI in Education",
        sources=[
            PackedSource(
                SourceDoc(
                    title="AI tutoring in classrooms",
                    authors=["Rossi"],
                    year=2021,
                    abstract="students learning",
                ),
                "Rossi2021",
                0.9,
            )
        ],
    )


async def seed_document(
    db_session, email: str, *, sections: list[str], completed: int = 0
):
    """Seed a document with an outline; optionally pre-complete N sections
    (needed for resume tests so content assembly finds the checkpointed rows)."""
    user = User(email=email, full_name="Rebuild Tester")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    document = Document(
        user_id=user.id,
        title="Rebuild Test Thesis",
        topic="AI in Education",
        status="draft",
        language="en",
        ai_provider="openai",
        ai_model="gpt-4",
        outline={"sections": [{"title": t} for t in sections]},
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    for i in range(completed):
        db_session.add(
            DocumentSection(
                document_id=document.id,
                title=sections[i],
                section_index=i + 1,
                status="completed",
                content=f"Contenuto completato della sezione {i + 1}.",
                word_count=8,
            )
        )
    if completed:
        await db_session.commit()
    return user, document


def rebuild_harness(stack: ExitStack, db_session, redis_checkpoint: str | None):
    """Trimmed pipeline harness (mirrors test_claim_verifier's) + pack mocks."""
    gen_class = stack.enter_context(
        patch("app.services.background_jobs.SectionGenerator")
    )
    generator = MagicMock()
    generator.generate_section = AsyncMock(
        return_value={
            "section_title": "Introduzione",
            "section_index": 1,
            "content": "Testo [Rossi2021, 2021] con il 30% di dati.",
            "citations": [],
            "bibliography": [],
            "sources_used": 1,
            "humanized": False,
        }
    )
    gen_class.return_value = generator

    humanizer_class = stack.enter_context(
        patch("app.services.background_jobs.Humanizer")
    )
    humanizer = MagicMock()
    humanizer.humanize = AsyncMock(side_effect=lambda *a, **k: k.get("text", "x"))
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
            AsyncMock(return_value=(95.0, 0, "passed", None)),
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

    doc_service_class = stack.enter_context(
        patch("app.services.background_jobs.DocumentService")
    )
    doc_service = MagicMock()
    doc_service.export_document = AsyncMock(
        return_value={"download_url": "https://example.com/doc.docx", "format": "docx"}
    )
    doc_service_class.return_value = doc_service

    redis = MagicMock()
    redis.get = AsyncMock(return_value=redis_checkpoint)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    stack.enter_context(
        patch("app.services.background_jobs.get_redis", AsyncMock(return_value=redis))
    )

    session_class = stack.enter_context(
        patch("app.services.background_jobs.database.AsyncSessionLocal")
    )
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=db_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    session_class.return_value = mock_session

    stack.enter_context(patch("app.services.notification_service.notification_service"))

    # Pack seams (module globals, per the thin-wrapper convention).
    build_pack = AsyncMock(
        side_effect=lambda db, doc, section_titles=None: fake_pack(int(doc.id))
    )
    stack.enter_context(
        patch("app.services.background_jobs._build_source_pack", build_pack)
    )
    stack.enter_context(
        patch(
            "app.services.background_jobs._load_source_pack",
            AsyncMock(return_value=None),
        )
    )
    persist_pack = AsyncMock()
    stack.enter_context(
        patch("app.services.background_jobs._persist_source_pack", persist_pack)
    )

    return {
        "build_pack": build_pack,
        "persist_pack": persist_pack,
        "generate_section": generator.generate_section,
        "export_document": doc_service.export_document,
    }


@pytest.mark.asyncio
async def test_fresh_generation_rebuilds_pack_with_section_titles(
    db_session, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", make_settings())
    user, document = await seed_document(
        db_session, "rebuild-fresh@example.com", sections=["Introduzione"]
    )
    document_id = document.id

    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

        # Initial build (no titles) + post-outline rebuild (with titles).
        assert mocks["build_pack"].call_count == 2
        rebuild_kwargs = mocks["build_pack"].call_args_list[1].kwargs
        assert rebuild_kwargs.get("section_titles") == ["Introduzione"]
        assert mocks["persist_pack"].call_count == 2
        # The rebuilt pack is what sections consume.
        section_kwargs = mocks["generate_section"].call_args.kwargs
        assert section_kwargs["source_pack"] is not None
        assert mocks["export_document"].call_count == 1

    refreshed = (
        await db_session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one()
    assert refreshed.status == "completed"


@pytest.mark.asyncio
async def test_resume_skips_rebuild(db_session, monkeypatch):
    monkeypatch.setattr("app.services.background_jobs.settings", make_settings())
    user, document = await seed_document(
        db_session,
        "rebuild-resume@example.com",
        sections=["Introduzione", "Futuro"],
        completed=1,
    )
    document_id = document.id

    checkpoint = json.dumps({"last_completed_section_index": 1})
    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=checkpoint)
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

        # Only the initial build — resume must NOT re-key the pack.
        assert mocks["build_pack"].call_count == 1
        assert mocks["build_pack"].call_args.kwargs.get("section_titles") in (
            None,
            [],
        )
        # Section 1 (checkpointed) skipped; only section 2 generated.
        assert mocks["generate_section"].call_count == 1
