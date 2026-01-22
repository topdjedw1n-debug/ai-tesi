"""
Tests for /api/v1/documents/activity endpoint
"""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.core.security import create_access_token
from app.models.auth import User
from app.models.document import Document
from main import app  # noqa: E402


@pytest.fixture
async def test_db():
    """Create test database"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(test_db: AsyncSession):
    """Create test user"""
    user = User(
        email="test@example.com",
        full_name="Test User",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user: User):
    """Create authentication headers"""
    token = create_access_token(user_id=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_activity_requires_authentication(client: AsyncClient):
    """Test that activity endpoint requires authentication"""
    response = await client.get("/api/v1/documents/activity")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_activity_returns_empty_for_new_user(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Test that activity returns empty list for user with no documents"""
    response = await client.get("/api/v1/documents/activity", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "activities" in data
    assert data["activities"] == []


@pytest.mark.asyncio
async def test_activity_returns_user_documents(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Test that activity returns only current user's documents"""
    # Create documents for test user
    doc1 = Document(
        user_id=test_user.id,
        title="Test Document 1",
        topic="Test topic 1",
        status="completed",
    )
    doc2 = Document(
        user_id=test_user.id,
        title="Test Document 2",
        topic="Test topic 2",
        status="generating",
    )
    test_db.add_all([doc1, doc2])
    await test_db.commit()

    response = await client.get("/api/v1/documents/activity", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "activities" in data
    assert len(data["activities"]) == 2

    # Check activity structure
    activity = data["activities"][0]
    assert "id" in activity
    assert "type" in activity
    assert "title" in activity
    assert "description" in activity
    assert "timestamp" in activity
    assert "status" in activity


@pytest.mark.asyncio
async def test_activity_idor_protection(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Test IDOR protection - users see only their own documents"""
    # Create another user and their document
    other_user = User(
        email="other@example.com",
        full_name="Other User",
        is_active=True,
    )
    test_db.add(other_user)
    await test_db.flush()

    other_doc = Document(
        user_id=other_user.id,
        title="Other User Document",
        topic="Other topic",
        status="completed",
    )
    test_db.add(other_doc)

    # Create document for test user
    my_doc = Document(
        user_id=test_user.id,
        title="My Document",
        topic="My topic",
        status="completed",
    )
    test_db.add(my_doc)
    await test_db.commit()

    # Fetch activities for test user
    response = await client.get("/api/v1/documents/activity", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Should only see own document
    assert len(data["activities"]) == 1
    assert data["activities"][0]["title"] == "My Document"


@pytest.mark.asyncio
async def test_activity_limit_parameter(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Test limit parameter works correctly"""
    # Create 15 documents
    for i in range(15):
        doc = Document(
            user_id=test_user.id,
            title=f"Document {i}",
            topic=f"Topic {i}",
            status="completed",
        )
        test_db.add(doc)
    await test_db.commit()

    # Test limit=5
    response = await client.get(
        "/api/v1/documents/activity?limit=5", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["activities"]) == 5

    # Test limit=20 (max is 50)
    response = await client.get(
        "/api/v1/documents/activity?limit=20", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["activities"]) == 15  # Only 15 exist


@pytest.mark.asyncio
async def test_activity_limit_validation(client: AsyncClient, auth_headers: dict):
    """Test limit parameter validation"""
    # Test limit=0 (below minimum)
    response = await client.get(
        "/api/v1/documents/activity?limit=0", headers=auth_headers
    )
    assert response.status_code == 422  # Validation error

    # Test limit=100 (above maximum)
    response = await client.get(
        "/api/v1/documents/activity?limit=100", headers=auth_headers
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_activity_ordering(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Test activities are ordered by most recent first"""
    from datetime import datetime, timedelta

    # Create documents with explicit timestamps
    now = datetime.utcnow()

    doc1 = Document(
        user_id=test_user.id,
        title="First Document",
        topic="Topic 1",
        status="completed",
        updated_at=now - timedelta(seconds=10),  # 10 seconds ago
    )
    test_db.add(doc1)
    await test_db.flush()

    doc2 = Document(
        user_id=test_user.id,
        title="Second Document",
        topic="Topic 2",
        status="completed",
        updated_at=now,  # Most recent
    )
    test_db.add(doc2)
    await test_db.commit()

    response = await client.get("/api/v1/documents/activity", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Most recent should be first
    assert len(data["activities"]) == 2
    assert data["activities"][0]["title"] == "Second Document"
    assert data["activities"][1]["title"] == "First Document"


@pytest.mark.asyncio
async def test_activity_status_mapping(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Test that document status maps correctly to activity status"""
    # Create documents with different statuses
    statuses = [
        ("draft", "pending"),
        ("generating", "pending"),
        ("completed", "success"),
        ("failed", "error"),
        ("outline_generated", "success"),
    ]

    for doc_status, expected_activity_status in statuses:
        doc = Document(
            user_id=test_user.id,
            title=f"Doc {doc_status}",
            topic="Test topic",
            status=doc_status,
        )
        test_db.add(doc)
    await test_db.commit()

    response = await client.get("/api/v1/documents/activity", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Verify status mapping
    activities_by_title = {a["title"]: a for a in data["activities"]}

    for doc_status, expected_activity_status in statuses:
        title = f"Doc {doc_status}"
        assert title in activities_by_title
        assert activities_by_title[title]["status"] == expected_activity_status
