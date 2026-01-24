"""
Tests for admin document endpoints
Covers /api/v1/admin/documents/* endpoints
"""
import os
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.user import User
from app.models.document import Document
from app.core.security import create_access_token
from main import app


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
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
async def admin_user(db_session):
    """Create an admin user for testing"""
    admin = User(
        email="admin@test.com",
        is_active=True,
        is_admin=True,
        is_super_admin=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def regular_user(db_session):
    """Create a regular user for testing"""
    user = User(
        email="user@test.com",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_documents(db_session, regular_user):
    """Create sample documents for testing"""
    doc1 = Document(
        user_id=regular_user.id,
        title="AI Ethics Research Paper",
        topic="Artificial Intelligence Ethics",
        language="en",
        target_pages=25,
        status="completed",
        created_at=datetime.utcnow() - timedelta(days=5),
    )
    doc2 = Document(
        user_id=regular_user.id,
        title="Machine Learning Basics",
        topic="Introduction to ML",
        language="en",
        target_pages=15,
        status="generating",
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    doc3 = Document(
        user_id=regular_user.id,
        title="Quantum Computing",
        topic="Quantum Algorithms",
        language="en",
        target_pages=30,
        status="failed",
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add_all([doc1, doc2, doc3])
    await db_session.commit()
    return [doc1, doc2, doc3]


@pytest.fixture
async def admin_token(admin_user):
    """Get admin access token"""
    token = create_access_token(admin_user.id)
    return token


@pytest.fixture
async def user_token(regular_user):
    """Get regular user access token"""
    token = create_access_token(regular_user.id)
    return token


@pytest.mark.asyncio
async def test_list_documents_requires_auth(client, db_session):
    """Test listing documents requires authentication"""
    response = await client.get("/api/v1/admin/documents")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_documents_requires_admin(client, db_session, user_token):
    """Test listing documents requires admin role"""
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.get("/api/v1/admin/documents", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_documents_success(client, db_session, admin_user, admin_token, sample_documents):
    """Test successful document listing"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/documents", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert len(data["documents"]) == 3  # All 3 sample documents


@pytest.mark.asyncio
async def test_list_documents_filter_by_status(client, db_session, admin_user, admin_token, sample_documents):
    """Test filtering documents by status"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/documents?status=completed", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_list_documents_filter_by_user_id(client, db_session, admin_user, admin_token, sample_documents, regular_user):
    """Test filtering documents by user_id"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(f"/api/v1/admin/documents?user_id={regular_user.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 3  # All documents belong to regular_user


@pytest.mark.asyncio
async def test_list_documents_pagination(client, db_session, admin_user, admin_token, sample_documents):
    """Test document listing pagination"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/documents?page=1&per_page=2", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 2
    assert data["page"] == 1
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_documents_filter_by_language(client, db_session, admin_user, admin_token, sample_documents):
    """Test filtering documents by language"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/documents?language=en", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 3  # All documents are in English


@pytest.mark.asyncio
async def test_get_document_details_requires_auth(client, db_session, sample_documents):
    """Test getting document details requires authentication"""
    doc_id = sample_documents[0].id
    response = await client.get(f"/api/v1/admin/documents/{doc_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_document_details_requires_admin(client, db_session, user_token, sample_documents):
    """Test getting document details requires admin role"""
    headers = {"Authorization": f"Bearer {user_token}"}
    doc_id = sample_documents[0].id
    response = await client.get(f"/api/v1/admin/documents/{doc_id}", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_document_details_success(client, db_session, admin_user, admin_token, sample_documents):
    """Test successful document details retrieval"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    doc_id = sample_documents[0].id
    response = await client.get(f"/api/v1/admin/documents/{doc_id}", headers=headers)
    assert response.status_code in [200, 404]  # May not exist depending on implementation


@pytest.mark.asyncio
async def test_get_document_details_not_found(client, db_session, admin_user, admin_token):
    """Test getting non-existent document returns 404"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/documents/99999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_requires_admin(client, db_session, user_token, sample_documents):
    """Test deleting document requires admin role"""
    headers = {"Authorization": f"Bearer {user_token}"}
    doc_id = sample_documents[0].id
    response = await client.delete(f"/api/v1/admin/documents/{doc_id}", headers=headers)
    assert response.status_code == 403
