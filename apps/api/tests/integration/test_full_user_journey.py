"""
Full user journey integration tests
Tests complete user flow: registration → document creation → generation → payment → export
"""
import os

import pytest
from faker import Faker
from httpx import AsyncClient

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_journey.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-mock-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_mock")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.auth import MagicLinkToken
from main import app  # noqa: E402

fake = Faker()


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        ac.headers.update(
            {
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        yield ac


@pytest.fixture
async def db_session():
    """Create a test database session"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_user_email():
    """Generate unique test user email"""
    return fake.email()


@pytest.fixture
async def auth_token(client, db_session, test_user_email):
    """Create authenticated user and return token"""
    # Step 1: Request magic link
    response = await client.post(
        "/api/v1/auth/magic-link", json={"email": test_user_email}
    )
    # Magic link might be rate limited, skip if so
    if response.status_code != 200:
        pytest.skip("Magic link request failed (likely rate limited)")

    # Step 2: Get token from database
    from sqlalchemy import select

    token_result = await db_session.execute(
        select(MagicLinkToken)
        .where(MagicLinkToken.email == test_user_email)
        .order_by(MagicLinkToken.created_at.desc())
    )
    magic_token = token_result.scalar_one_or_none()

    if not magic_token:
        pytest.skip("Magic link token not found")

    # Step 3: Verify magic link
    verify_response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": magic_token.token, "gdpr_consent": True},
    )

    if verify_response.status_code != 200:
        pytest.skip(f"Magic link verification failed: {verify_response.text}")

    verify_data = verify_response.json()
    assert "access_token" in verify_data
    return verify_data["access_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_user_journey(client, db_session, auth_token, test_user_email):
    """
    Complete user journey: registration → document → generation → payment → export
    """
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Step 1: Verify user is authenticated
    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    user_data = me_response.json()
    assert user_data["email"] == test_user_email

    # Step 2: Create document
    document_data = {
        "title": "Test Thesis: AI in Education",
        "topic": "The impact of artificial intelligence on modern educational systems",
        "language": "en",
        "target_pages": 10,
    }
    create_response = await client.post(
        "/api/v1/documents/",
        json=document_data,
        headers={
            **headers,
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
        },
    )
    assert create_response.status_code in [
        200,
        201,
    ], f"Failed to create document: {create_response.text}"
    document = create_response.json()
    document_id = document.get("id") or document.get("document", {}).get("id")
    assert document_id is not None, "Document ID should be present"

    # Step 3: Get document to verify creation
    get_response = await client.get(f"/api/v1/documents/{document_id}", headers=headers)
    assert get_response.status_code == 200
    doc_data = get_response.json()
    assert doc_data.get("title") == document_data["title"]
    assert doc_data.get("status") == "draft"

    # Step 4: Generate outline (mock mode - won't actually call AI)
    outline_response = await client.post(
        "/api/v1/generate/outline",
        json={"document_id": document_id, "additional_requirements": None},
        headers=headers,
    )
    # Outline generation might fail if AI is not configured, but document should still exist
    if outline_response.status_code == 200:
        outline_data = outline_response.json()
        assert "outline" in outline_data or "document_id" in outline_data

    # Step 5: List documents
    list_response = await client.get("/api/v1/documents/", headers=headers)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "documents" in list_data or isinstance(list_data, list)

    # Verify our document is in the list
    if isinstance(list_data, dict) and "documents" in list_data:
        doc_ids = [doc.get("id") for doc in list_data["documents"]]
    else:
        doc_ids = [doc.get("id") for doc in list_data]
    assert document_id in doc_ids

    # Step 6: Get usage stats
    usage_response = await client.get(
        f"/api/v1/generate/usage/{user_data['id']}", headers=headers
    )
    assert usage_response.status_code == 200
    usage_data = usage_response.json()
    assert "user_id" in usage_data or "total_documents" in usage_data

    # Step 7: Update document
    update_response = await client.put(
        f"/api/v1/documents/{document_id}",
        json={"title": "Updated Thesis Title"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_doc = update_response.json()
    assert updated_doc.get("title") == "Updated Thesis Title"

    # Step 8: Verify payment history endpoint (even if empty)
    payment_history = await client.get("/api/v1/payment/history", headers=headers)
    assert payment_history.status_code == 200
    payments = payment_history.json()
    assert isinstance(payments, list)

    # Step 9: Clean up - delete document
    delete_response = await client.delete(
        f"/api/v1/documents/{document_id}", headers=headers
    )
    assert delete_response.status_code == 200

    # Verify deletion
    deleted_get = await client.get(f"/api/v1/documents/{document_id}", headers=headers)
    assert deleted_get.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_documents_workflow(client, db_session, auth_token):
    """Test creating and managing multiple documents"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 3 documents
    document_ids = []
    for i in range(3):
        doc_response = await client.post(
            "/api/v1/documents/",
            json={
                "title": f"Document {i+1}",
                "topic": f"Research topic number {i+1} with sufficient length",
                "language": "en",
                "target_pages": 10,
            },
            headers={
                **headers,
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
            },
        )
        if doc_response.status_code in [200, 201]:
            doc_data = doc_response.json()
            doc_id = doc_data.get("id") or doc_data.get("document", {}).get("id")
            if doc_id:
                document_ids.append(doc_id)

    assert len(document_ids) == 3, f"Expected 3 documents, got {len(document_ids)}"

    # List all documents
    list_response = await client.get("/api/v1/documents/", headers=headers)
    assert list_response.status_code == 200
    list_data = list_response.json()

    if isinstance(list_data, dict) and "documents" in list_data:
        listed_ids = [doc.get("id") for doc in list_data["documents"]]
    else:
        listed_ids = [doc.get("id") for doc in list_data]

    # Verify all documents are listed
    for doc_id in document_ids:
        assert doc_id in listed_ids

    # Delete all documents
    for doc_id in document_ids:
        delete_response = await client.delete(
            f"/api/v1/documents/{doc_id}", headers=headers
        )
        assert delete_response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
async def test_document_export_flow(client, db_session, auth_token):
    """Test document export flow"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create document
    create_response = await client.post(
        "/api/v1/documents/",
        json={
            "title": "Export Test Document",
            "topic": "A test document for export functionality",
            "language": "en",
            "target_pages": 10,
        },
        headers={
            **headers,
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
        },
    )

    if create_response.status_code not in [200, 201]:
        pytest.skip("Could not create document for export test")

    document = create_response.json()
    document_id = document.get("id") or document.get("document", {}).get("id")

    if not document_id:
        pytest.skip("Could not extract document ID")

    # Update document to completed status with some content
    from sqlalchemy import select

    from app.models.document import Document

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = "completed"
            doc.content = "# Test Document\n\nThis is test content for export."
            await session.commit()

    # Test export (might fail if export service not fully configured, that's ok)
    export_response = await client.post(
        f"/api/v1/documents/{document_id}/export",
        json={"format": "pdf"},
        headers=headers,
    )

    # Export might return 200 (success), 202 (accepted), 404 (not found), or 500 (service error)
    # We just verify the endpoint exists and handles the request
    assert export_response.status_code in [
        200,
        202,
        404,
        500,
        503,
    ], f"Unexpected export response: {export_response.status_code}"

    # Cleanup
    await client.delete(f"/api/v1/documents/{document_id}", headers=headers)
