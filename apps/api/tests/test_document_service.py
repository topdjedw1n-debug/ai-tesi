"""
Unit tests for DocumentService
"""
import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.auth import User
from app.models.document import Document, DocumentSection
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_create_document_success(db_session):
    """Test creating a document successfully"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create service
    service = DocumentService(db_session)

    # Create document
    result = await service.create_document(
        user_id=user.id,
        title="Test Thesis",
        topic="AI in Education",
        language="en",
        target_pages=15,
        ai_provider="openai",
        ai_model="gpt-4"
    )

    # Verify result
    assert result["id"] is not None
    assert result["title"] == "Test Thesis"
    assert result["topic"] == "AI in Education"
    assert result["status"] == "draft"

    # Verify document in database
    document = await db_session.get(Document, result["id"])
    assert document is not None
    assert document.user_id == user.id
    assert document.title == "Test Thesis"
    assert document.status == "draft"

    # Verify user's document count was updated
    await db_session.refresh(user)
    assert user.total_documents_created == 1


@pytest.mark.asyncio
async def test_get_document_success(db_session):
    """Test getting a document successfully"""
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
        language="en",
        target_pages=15,
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create service and get document
    service = DocumentService(db_session)
    result = await service.get_document(document_id=document.id, user_id=user.id)

    # Verify result
    assert result["id"] == document.id
    assert result["title"] == "Test Thesis"
    assert result["topic"] == "AI in Education"
    assert result["sections"] == []  # No sections yet


@pytest.mark.asyncio
async def test_get_document_not_found(db_session):
    """Test getting a non-existent document raises NotFoundError"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create service and try to get non-existent document
    service = DocumentService(db_session)

    with pytest.raises(NotFoundError, match="Document not found"):
        await service.get_document(document_id=999, user_id=user.id)


@pytest.mark.asyncio
async def test_get_user_documents_with_pagination(db_session):
    """Test getting user documents with pagination"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create multiple documents
    for i in range(5):
        document = Document(
            user_id=user.id,
            title=f"Thesis {i}",
            topic=f"Topic {i}",
            status="draft"
        )
        db_session.add(document)
    await db_session.commit()

    # Create service
    service = DocumentService(db_session)

    # Get first page
    result = await service.get_user_documents(user_id=user.id, limit=2, offset=0)
    assert result["total"] == 5
    assert len(result["documents"]) == 2
    assert result["per_page"] == 2
    assert result["page"] == 1


@pytest.mark.asyncio
async def test_update_document_success(db_session):
    """Test updating a document successfully"""
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

    # Create service and update document
    service = DocumentService(db_session)
    result = await service.update_document(
        document_id=document.id,
        user_id=user.id,
        title="Updated Title",
        topic="Updated Topic"
    )

    assert result["message"] == "Document updated successfully"

    # Verify document was updated
    await db_session.refresh(document)
    assert document.title == "Updated Title"
    assert document.topic == "Updated Topic"


@pytest.mark.asyncio
async def test_delete_document_success(db_session):
    """Test deleting a document successfully"""
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
    document_id = document.id

    # Create service and delete document
    service = DocumentService(db_session)
    result = await service.delete_document(document_id=document_id, user_id=user.id)

    assert result["message"] == "Document deleted successfully"

    # Verify document was deleted
    deleted_document = await db_session.get(Document, document_id)
    assert deleted_document is None


@pytest.mark.asyncio
async def test_export_document_docx_fails_on_incomplete(db_session):
    """Test that export fails for incomplete documents"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create incomplete document
    document = Document(
        user_id=user.id,
        title="Incomplete Thesis",
        topic="AI in Education",
        status="draft"  # Not completed
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create service and try to export
    service = DocumentService(db_session)

    with pytest.raises(ValidationError, match="Document is not completed"):
        await service.export_document(
            document_id=document.id,
            format="docx",
            user_id=user.id
        )


@pytest.mark.asyncio
async def test_export_document_pdf_fails_on_incomplete(db_session):
    """Test that PDF export fails for incomplete documents"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create incomplete document
    document = Document(
        user_id=user.id,
        title="Incomplete Thesis",
        topic="AI in Education",
        status="draft"  # Not completed
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create service and try to export
    service = DocumentService(db_session)

    with pytest.raises(ValidationError, match="Document is not completed"):
        await service.export_document(
            document_id=document.id,
            format="pdf",
            user_id=user.id
        )


@pytest.mark.asyncio
async def test_export_document_pdf_unsupported_format(db_session):
    """Test that export fails for unsupported format"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create completed document
    document = Document(
        user_id=user.id,
        title="Complete Thesis",
        topic="AI in Education",
        status="completed",
        content="Test content"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create service and try to export with unsupported format
    service = DocumentService(db_session)

    with pytest.raises(ValidationError, match="Unsupported export format"):
        await service.export_document(
            document_id=document.id,
            format="txt",  # Unsupported format
            user_id=user.id
        )


@pytest.mark.asyncio
async def test_update_document_not_found(db_session):
    """Test updating non-existent document raises NotFoundError"""
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = DocumentService(db_session)

    with pytest.raises(NotFoundError):
        await service.update_document(
            document_id=999,
            user_id=user.id,
            title="Updated Title"
        )


@pytest.mark.asyncio
async def test_delete_document_not_found(db_session):
    """Test deleting non-existent document raises NotFoundError"""
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = DocumentService(db_session)

    with pytest.raises((NotFoundError, ValidationError)):  # Can raise NotFoundError or ValidationError
        await service.delete_document(document_id=999, user_id=user.id)


@pytest.mark.asyncio
async def test_get_document_sections_not_found(db_session):
    """Test getting sections for non-existent document raises NotFoundError"""
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = DocumentService(db_session)

    with pytest.raises(NotFoundError):
        await service.get_document_sections(document_id=999, user_id=user.id)


@pytest.mark.asyncio
async def test_get_document_sections_success(db_session):
    """Test getting document sections successfully"""
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

    # Create service and get sections
    service = DocumentService(db_session)
    sections = await service.get_document_sections(
        document_id=document.id,
        user_id=user.id
    )

    assert len(sections) == 3
    assert sections[0]["title"] == "Section 0"
    assert sections[2]["title"] == "Section 2"

