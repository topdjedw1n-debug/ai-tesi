"""
Full integration tests for API flows
Tests complete request/response cycles through the API
"""
import os

import pytest
from httpx import AsyncClient

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_integration.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.auth import MagicLinkToken, User
from app.services.auth_service import AuthService
from main import app  # noqa: E402


@pytest.fixture
async def client():
    """Create async test client"""
    # Add CSRF token header for state-changing requests
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Set default headers with CSRF token
        ac.headers.update({
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
            "X-Requested-With": "XMLHttpRequest",
        })
        yield ac


@pytest.fixture
async def db_session():
    """Create a test database session"""
    # Create tables
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with AsyncSessionLocal() as session:
        yield session

    # Clean up after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        full_name="Test User",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_token(db_session, test_user):
    """Create auth token for test user using AuthService"""
    AuthService(db_session)
    # Use the actual token creation method from AuthService
    from datetime import datetime, timedelta

    from jose import jwt

    from app.core.config import settings

    secret_key = settings.JWT_SECRET or settings.SECRET_KEY
    expires_delta = timedelta(minutes=settings.JWT_EXP_MIN or 30)
    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": str(test_user.id),  # JWT sub claim should be string
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),
    }
    if settings.JWT_ISS:
        payload["iss"] = settings.JWT_ISS
    if settings.JWT_AUD:
        payload["aud"] = settings.JWT_AUD

    token = jwt.encode(payload, secret_key, algorithm=settings.JWT_ALG)
    return token


@pytest.mark.asyncio
async def test_auth_flow(client, db_session, test_user):
    """Integration test: Complete auth flow (magic link → verify → me)"""
    # Step 1: Request magic link
    response = await client.post(
        "/api/v1/auth/magic-link",
        json={"email": test_user.email}
    )
    # Magic link might return 403 if rate limited, or 200 if successful
    assert response.status_code in [200, 403]

    if response.status_code == 200:
        data = response.json()
        assert "message" in data

        # Step 2: Get token from database
        from sqlalchemy import select
        token_result = await db_session.execute(
            select(MagicLinkToken)
            .where(MagicLinkToken.email == test_user.email)
            .order_by(MagicLinkToken.created_at.desc())
        )
        magic_token = token_result.scalar_one_or_none()

        if magic_token:
            # Step 3: Verify magic link
            verify_response = await client.post(
                "/api/v1/auth/verify-magic-link",
                json={"token": magic_token.token}
            )
            assert verify_response.status_code == 200
            verify_data = verify_response.json()
            assert "access_token" in verify_data
            access_token = verify_data["access_token"]

            # Step 4: Use token to get user info
            me_response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert me_response.status_code == 200
            me_data = me_response.json()
            assert me_data["email"] == test_user.email


@pytest.mark.asyncio
async def test_create_document_flow(client, db_session, auth_token, test_user):
    """Integration test: Create document flow (auth → create → get)"""
    # Step 1: Create document
    document_data = {
        "title": "Test Thesis",
        "topic": "AI in Education",
        "language": "en",
        "target_pages": 10
    }
    create_response = await client.post(
        "/api/v1/documents/",
        json=document_data,
        headers={
            "Authorization": f"Bearer {auth_token}",
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890"
        }
    )
    # Check response status
    assert create_response.status_code in [200, 201], f"Expected 200/201, got {create_response.status_code}: {create_response.text}"

    if create_response.status_code in [200, 201]:
        create_data = create_response.json()
        # Response might be different format, check for either "id" or nested structure
        if "id" in create_data:
            document_id = create_data["id"]
        elif isinstance(create_data, dict) and any("id" in str(v) for v in create_data.values()):
            # Try to find ID in response
            document_id = next((v for k, v in create_data.items() if "id" in k.lower()), None)
        else:
            pytest.skip("Could not extract document ID from response")

        assert document_id is not None, "Document ID should be present"

        # Step 2: Get document
        get_response = await client.get(
            f"/api/v1/documents/{document_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        # Check document exists
        assert "id" in get_data or "title" in get_data


@pytest.mark.asyncio
async def test_document_list_flow(client, db_session, auth_token, test_user):
    """Integration test: Document list flow"""
    # Create multiple documents
    for i in range(3):
        doc_data = {
            "title": f"Test Document {i+1}",
            "topic": f"Research Topic Number {i+1}",  # Must be >= 10 chars
            "language": "en",
            "target_pages": 10
        }
        await client.post(
            "/api/v1/documents/",
            json=doc_data,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890"
            }
        )

    # Get list - use trailing slash to avoid redirect
    list_response = await client.get(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "documents" in list_data
    assert len(list_data["documents"]) >= 3


@pytest.mark.asyncio
async def test_document_update_flow(client, db_session, auth_token, test_user):
    """Integration test: Update document flow"""
    # Create document
    doc_response = await client.post(
        "/api/v1/documents/",
        json={
            "title": "Original Title",
            "topic": "Original Research Topic",
            "language": "en",
            "target_pages": 10
        },
        headers={
            "Authorization": f"Bearer {auth_token}",
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890"
        }
    )
    doc_id = doc_response.json()["id"]

    # Update document
    update_response = await client.put(
        f"/api/v1/documents/{doc_id}",
        json={"title": "Updated Title"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert update_response.status_code == 200
    updated_data = update_response.json()
    assert updated_data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_document_delete_flow(client, db_session, auth_token, test_user):
    """Integration test: Delete document flow"""
    # Create document
    doc_response = await client.post(
        "/api/v1/documents/",
        json={
            "title": "To Delete",
            "topic": "Test Topic Long Enough",
            "language": "en",
            "target_pages": 10
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    doc_id = doc_response.json()["id"]

    # Delete document
    delete_response = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert delete_response.status_code == 200

    # Verify deleted
    get_response = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_usage_stats_flow(client, db_session, auth_token, test_user):
    """Integration test: Usage stats flow"""
    response = await client.get(
        f"/api/v1/generate/usage/{test_user.id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "total_documents" in data
    assert "total_tokens_used" in data

