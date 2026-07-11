"""DB round-trip tests for persist_source_pack / load_source_pack (WS2)."""

import pytest
from sqlalchemy import select

from app.models.auth import User
from app.models.document import Document, DocumentSource
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.source_verification_stage import (
    apply_source_pack_rows,
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
                    provider="crossref",
                    source_type="journal-article",
                    verification_status="verified",
                    canonical_metadata={"status": "verified"},
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
    assert loaded.sources[0].source.provider == "crossref"
    assert loaded.sources[0].source.source_type == "journal-article"
    assert loaded.sources[0].source.verification_status == "verified"
    assert loaded.sha256() == pack.sha256()


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


@pytest.mark.asyncio
async def test_same_title_year_different_authors_keep_distinct_keys(db_session):
    document = await _seed_document(db_session, "pack-collision@example.com")
    pack = SourcePack(
        document_id=document.id,
        topic="AI in education",
        sources=[
            PackedSource(
                SourceDoc(
                    title="Shared generic title",
                    authors=["Mario Rossi"],
                    year=2021,
                ),
                "Rossi2021",
                0.9,
            ),
            PackedSource(
                SourceDoc(
                    title="Shared generic title",
                    authors=["Anna Bianchi"],
                    year=2021,
                ),
                "Bianchi2021",
                0.8,
            ),
        ],
    )

    await persist_source_pack(db_session, document.id, pack)
    loaded = await load_source_pack(db_session, document.id)

    assert loaded is not None
    assert sorted(loaded.keys()) == ["Bianchi2021", "Rossi2021"]


@pytest.mark.asyncio
async def test_equal_score_reload_uses_canonical_key_order(db_session):
    document = await _seed_document(db_session, "pack-order@example.com")
    pack = SourcePack(
        document_id=document.id,
        topic="AI in education",
        sources=[
            PackedSource(
                SourceDoc(
                    title="Zulu source",
                    authors=["Zulu"],
                    year=2021,
                ),
                "Zulu2021",
                0.9,
            ),
            PackedSource(
                SourceDoc(
                    title="Alpha source",
                    authors=["Alpha"],
                    year=2021,
                ),
                "Alpha2021",
                0.9,
            ),
        ],
    )

    await persist_source_pack(db_session, document.id, pack)
    loaded = await load_source_pack(db_session, document.id)

    assert loaded is not None
    assert loaded.keys() == ["Alpha2021", "Zulu2021"]
    assert loaded.prompt_block() == pack.prompt_block()
    assert loaded.sha256() == pack.sha256()


@pytest.mark.asyncio
async def test_distinct_uploaded_files_with_same_doi_are_rejected_before_flush(
    db_session,
):
    document = await _seed_document(db_session, "pack-upload-doi-conflict@example.com")
    document_id = int(document.id)
    pack = SourcePack(
        document_id=document_id,
        topic="AI in education",
        sources=[
            PackedSource(
                SourceDoc(
                    title="Uploaded copy A",
                    authors=["Mario Rossi"],
                    year=2021,
                    paper_id="uploaded:10",
                    doi="10.1234/shared",
                ),
                "Rossi2021",
                1.0,
            ),
            PackedSource(
                SourceDoc(
                    title="Uploaded copy B",
                    authors=["Anna Bianchi"],
                    year=2022,
                    paper_id="uploaded:11",
                    doi="10.1234/shared",
                ),
                "Bianchi2022",
                1.0,
            ),
        ],
    )

    with pytest.raises(ValueError, match="same DOI"):
        await apply_source_pack_rows(db_session, document_id, pack)
    await db_session.rollback()

    assert (
        await db_session.execute(
            select(DocumentSource).where(DocumentSource.document_id == document_id)
        )
    ).scalars().all() == []
