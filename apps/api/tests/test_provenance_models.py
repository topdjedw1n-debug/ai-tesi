"""
Unit tests for DocumentProvenance and DocumentSource models
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.document import (
    Document,
    DocumentProvenance,
    DocumentSection,
    DocumentSource,
)


async def _create_document(db_session) -> Document:
    """Create a user and a document owned by them"""
    user = User(email="provenance-test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    document = Document(user_id=user.id, title="Test Thesis", topic="AI in Education")
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


async def _create_section(db_session, document: Document) -> DocumentSection:
    section = DocumentSection(
        document_id=document.id, title="Introduction", section_index=0
    )
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(section)
    return section


@pytest.mark.asyncio
async def test_create_provenance_event_with_json_payload(db_session):
    """Provenance event persists with a JSON payload that round-trips as dict"""
    document = await _create_document(db_session)

    event = DocumentProvenance(
        document_id=document.id,
        stage="verification",
        event_type="source_verified",
        payload={"doi": "10.1000/x", "match_score": 0.97},
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    assert event.id is not None
    assert event.created_at is not None
    assert event.payload == {"doi": "10.1000/x", "match_score": 0.97}
    assert event.payload["match_score"] == 0.97


@pytest.mark.asyncio
async def test_create_source_with_defaults(db_session):
    """Source created with only required fields gets safe defaults"""
    document = await _create_document(db_session)

    source = DocumentSource(document_id=document.id, title="Attention Is All You Need")
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    assert source.id is not None
    assert source.verification_status == "unverified"
    assert source.section_id is None
    assert source.canonical_metadata is None
    assert source.created_at is not None


@pytest.mark.asyncio
async def test_create_source_full_sourcedoc_fields(db_session):
    """All SourceDoc-mirror fields persist; authors round-trips as a list"""
    document = await _create_document(db_session)

    source = DocumentSource(
        document_id=document.id,
        title="A Survey of Retrieval-Augmented Generation",
        authors=["A. Smith", "B. Jones"],
        year=2024,
        abstract="An overview of RAG methods.",
        paper_id="abc123",
        venue="ACL",
        citation_count=42,
        url="https://example.org/paper",
        doi="10.1234/example.2024",
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    assert source.authors == ["A. Smith", "B. Jones"]
    assert isinstance(source.authors, list)
    assert source.year == 2024
    assert source.citation_count == 42
    assert source.doi == "10.1234/example.2024"


@pytest.mark.asyncio
async def test_source_nullable_section_link(db_session):
    """section_id is optional; when set, the section relationship resolves"""
    document = await _create_document(db_session)
    section = await _create_section(db_session, document)

    linked = DocumentSource(
        document_id=document.id, section_id=section.id, title="Linked Source"
    )
    unlinked = DocumentSource(document_id=document.id, title="Unlinked Source")
    db_session.add_all([linked, unlinked])
    await db_session.commit()

    result = await db_session.execute(
        select(DocumentSource)
        .where(DocumentSource.title == "Linked Source")
        .options(selectinload(DocumentSource.section))
    )
    linked_loaded = result.scalar_one()
    assert linked_loaded.section is not None
    assert linked_loaded.section.id == section.id

    result = await db_session.execute(
        select(DocumentSource)
        .where(DocumentSource.title == "Unlinked Source")
        .options(selectinload(DocumentSource.section))
    )
    assert result.scalar_one().section is None


@pytest.mark.asyncio
async def test_document_relationships(db_session):
    """Document.sources and Document.provenance_events load via selectinload"""
    document = await _create_document(db_session)

    db_session.add_all(
        [
            DocumentSource(document_id=document.id, title="Source One"),
            DocumentSource(document_id=document.id, title="Source Two"),
            DocumentProvenance(
                document_id=document.id,
                stage="retrieval",
                event_type="sources_retrieved",
            ),
            DocumentProvenance(
                document_id=document.id,
                stage="generation",
                event_type="section_generated",
            ),
        ]
    )
    await db_session.commit()

    result = await db_session.execute(
        select(Document)
        .where(Document.id == document.id)
        .options(
            selectinload(Document.sources), selectinload(Document.provenance_events)
        )
    )
    loaded = result.scalar_one()
    assert len(loaded.sources) == 2
    assert len(loaded.provenance_events) == 2
    assert {s.title for s in loaded.sources} == {"Source One", "Source Two"}


@pytest.mark.asyncio
async def test_cascade_delete_document_removes_sources_and_provenance(db_session):
    """ORM delete of a document cascades to its sources and provenance events"""
    document = await _create_document(db_session)
    document_id = document.id

    db_session.add_all(
        [
            DocumentSource(document_id=document_id, title="Doomed Source"),
            DocumentProvenance(
                document_id=document_id,
                stage="retrieval",
                event_type="sources_retrieved",
            ),
        ]
    )
    await db_session.commit()

    # Re-load with collections eager so the ORM cascade can process them
    result = await db_session.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.sources),
            selectinload(Document.provenance_events),
            selectinload(Document.sections),
        )
    )
    loaded = result.scalar_one()
    await db_session.delete(loaded)
    await db_session.commit()

    sources_left = await db_session.scalar(
        select(func.count())
        .select_from(DocumentSource)
        .where(DocumentSource.document_id == document_id)
    )
    events_left = await db_session.scalar(
        select(func.count())
        .select_from(DocumentProvenance)
        .where(DocumentProvenance.document_id == document_id)
    )
    assert sources_left == 0
    assert events_left == 0


@pytest.mark.asyncio
async def test_update_verification_status_and_canonical_metadata(db_session):
    """Verification updates persist (assign a new dict - JSON columns don't track in-place mutation)"""
    document = await _create_document(db_session)

    source = DocumentSource(
        document_id=document.id, title="To Verify", doi="10.5555/verify.me"
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    source.verification_status = "verified"
    source.canonical_metadata = {
        "title": "To Verify (canonical)",
        "doi": "10.5555/verify.me",
        "provider": "crossref",
    }
    await db_session.commit()

    result = await db_session.execute(
        select(DocumentSource).where(DocumentSource.id == source.id)
    )
    reloaded = result.scalar_one()
    assert reloaded.verification_status == "verified"
    assert reloaded.canonical_metadata["provider"] == "crossref"


@pytest.mark.asyncio
async def test_unique_doi_per_document(db_session):
    """Duplicate (document_id, doi) is rejected; multiple NULL DOIs are allowed"""
    document = await _create_document(db_session)
    # Capture the id: rollback() below expires instances, and touching
    # document.id afterwards would trigger a sync lazy-load in async context
    document_id = document.id

    first = DocumentSource(
        document_id=document_id, title="First", doi="10.9999/duplicate"
    )
    db_session.add(first)
    await db_session.commit()

    duplicate = DocumentSource(
        document_id=document_id, title="Duplicate", doi="10.9999/duplicate"
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Partial index: DOI-less sources are unconstrained
    db_session.add_all(
        [
            DocumentSource(document_id=document_id, title="No DOI 1"),
            DocumentSource(document_id=document_id, title="No DOI 2"),
        ]
    )
    await db_session.commit()

    count = await db_session.scalar(
        select(func.count())
        .select_from(DocumentSource)
        .where(DocumentSource.document_id == document_id)
    )
    assert count == 3
