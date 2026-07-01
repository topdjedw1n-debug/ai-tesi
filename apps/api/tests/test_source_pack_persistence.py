"""DB round-trip tests for persist_source_pack / load_source_pack (WS2)."""

import pytest
from sqlalchemy import select

from app.models.auth import User
from app.models.document import Document, DocumentSource
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.source_verification_stage import (
    load_source_pack,
    persist_source_pack,
)


async def _seed_document(db_session, email):
    user = User(email=email, full_name="Pack Tester")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    document = Document(
        user_id=user.id,
        title="Pack Test",
        topic="AI in education",
        status="draft",
        language="en",
        ai_provider="openai",
        ai_model="gpt-4",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


def _pack(document_id):
    return SourcePack(
        document_id=document_id,
        topic="AI in education",
        sources=[
            PackedSource(
                SourceDoc(
                    title="AI tutoring in classrooms",
                    authors=["Rossi"],
                    year=2021,
                    abstract="abstract one",
                    doi="10.1/edu",
                ),
                "Rossi2021",
                0.9,
            ),
            PackedSource(
                SourceDoc(
                    title="Adaptive learning systems",
                    authors=["Bianchi"],
                    year=2020,
                    abstract="abstract two",
                ),
                "Bianchi2020",
                0.7,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_persist_and_load_round_trip(db_session):
    document = await _seed_document(db_session, "pack-roundtrip@example.com")
    pack = _pack(document.id)

    await persist_source_pack(db_session, document.id, pack)
    loaded = await load_source_pack(db_session, document.id)

    assert loaded is not None
    assert loaded.topic == "AI in education"
    assert sorted(loaded.keys()) == ["Bianchi2020", "Rossi2021"]
    # Ranked by on_topic_score desc.
    assert loaded.sources[0].citation_key == "Rossi2021"
    assert loaded.sources[0].on_topic_score == 0.9


@pytest.mark.asyncio
async def test_persist_is_idempotent_upsert(db_session):
    document = await _seed_document(db_session, "pack-idempotent@example.com")
    pack = _pack(document.id)

    await persist_source_pack(db_session, document.id, pack)
    await persist_source_pack(db_session, document.id, pack)  # re-run

    rows = (
        (
            await db_session.execute(
                select(DocumentSource).where(
                    DocumentSource.document_id == document.id,
                    DocumentSource.is_in_upfront_pack.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    # No duplicates despite two runs.
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_rebuild_resets_stale_pack_membership(db_session):
    document = await _seed_document(db_session, "pack-rebuild@example.com")
    await persist_source_pack(db_session, document.id, _pack(document.id))

    # Second build drops Bianchi2020 and re-keys Rossi.
    new_pack = SourcePack(
        document_id=document.id,
        topic="AI in education",
        sources=[
            PackedSource(
                SourceDoc(
                    title="AI tutoring in classrooms",
                    authors=["Rossi"],
                    year=2021,
                    abstract="abstract one",
                    doi="10.1/edu",
                ),
                "Rossi2021",
                0.95,
            )
        ],
    )
    await persist_source_pack(db_session, document.id, new_pack)

    loaded = await load_source_pack(db_session, document.id)
    assert loaded is not None
    assert loaded.keys() == ["Rossi2021"]  # stale Bianchi dropped from the pack


@pytest.mark.asyncio
async def test_load_returns_none_without_pack(db_session):
    document = await _seed_document(db_session, "pack-none@example.com")
    assert await load_source_pack(db_session, document.id) is None
