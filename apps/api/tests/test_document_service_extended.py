"""
Extended tests for DocumentService to improve coverage
"""
import pytest

from app.models.auth import User
from app.models.document import Document, DocumentSection
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_get_user_documents_empty(db_session):
    """Test getting documents for user with no documents"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = DocumentService(db_session)

    result = await service.get_user_documents(user_id=user.id, limit=20, offset=0)

    assert result["total"] == 0
    assert len(result["documents"]) == 0
    assert result["per_page"] == 20


@pytest.mark.asyncio
async def test_get_user_documents_pagination(db_session):
    """Test pagination for get_user_documents"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create multiple documents
    for i in range(5):
        document = Document(
            user_id=user.id,
            title=f"Document {i}",
            topic=f"Topic {i}",
            status="draft"
        )
        db_session.add(document)
    await db_session.commit()

    service = DocumentService(db_session)

    # Get first page
    result1 = await service.get_user_documents(user_id=user.id, limit=2, offset=0)
    assert result1["total"] == 5
    assert len(result1["documents"]) == 2

    # Get second page
    result2 = await service.get_user_documents(user_id=user.id, limit=2, offset=2)
    assert result2["total"] == 5
    assert len(result2["documents"]) == 2


@pytest.mark.asyncio
async def test_update_document_partial_fields(db_session):
    """Test updating document with partial fields"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id,
        title="Original Title",
        topic="Original Topic",
        language="en",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    service = DocumentService(db_session)

    # Update only title
    result = await service.update_document(
        document_id=document.id,
        user_id=user.id,
        title="Updated Title Only"
    )

    assert result["message"] == "Document updated successfully"

    # Verify only title changed
    await db_session.refresh(document)
    assert document.title == "Updated Title Only"
    assert document.topic == "Original Topic"  # Unchanged


@pytest.mark.asyncio
async def test_get_document_with_sections(db_session):
    """Test getting document that has sections"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id,
        title="Test Thesis",
        topic="AI in Education",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create sections
    for i in range(3):
        section = DocumentSection(
            document_id=document.id,
            title=f"Section {i}",
            section_index=i,
            content=f"Content {i}",
            status="completed"
        )
        db_session.add(section)
    await db_session.commit()

    service = DocumentService(db_session)

    result = await service.get_document(document_id=document.id, user_id=user.id)

    assert result["id"] == document.id
    assert len(result["sections"]) == 3
    assert result["sections"][0]["title"] == "Section 0"


@pytest.mark.asyncio
async def test_update_document_invalid_field(db_session):
    """Test updating document with invalid field (should ignore)"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id,
        title="Original Title",
        topic="Original Topic",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    service = DocumentService(db_session)

    # Update with invalid field (should be ignored)
    result = await service.update_document(
        document_id=document.id,
        user_id=user.id,
        invalid_field="Should be ignored",
        title="Updated Title"
    )

    assert result["message"] == "Document updated successfully"

    # Verify title changed
    await db_session.refresh(document)
    assert document.title == "Updated Title"


@pytest.mark.asyncio
async def test_delete_document_with_sections(db_session):
    """Test deleting document that has sections (cascade)"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id,
        title="Test Thesis",
        topic="AI in Education",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create sections
    section = DocumentSection(
        document_id=document.id,
        title="Section 1",
        section_index=0,
        content="Content",
        status="completed"
    )
    db_session.add(section)
    await db_session.commit()

    service = DocumentService(db_session)

    # Delete document (sections should be cascade deleted)
    result = await service.delete_document(document_id=document.id, user_id=user.id)

    assert result["message"] == "Document deleted successfully"

    # Verify document is deleted
    deleted_document = await db_session.get(Document, document.id)
    assert deleted_document is None

