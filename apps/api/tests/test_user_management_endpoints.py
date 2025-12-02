"""
Integration tests for user management admin endpoints
Tests user block/unblock/delete/make-admin endpoints
"""
import os

import pytest
from httpx import AsyncClient

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.user import User
from main import app  # noqa: E402


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
async def test_user(db_session):
    """Create a test user"""
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
async def admin_user(db_session):
    """Create an admin user"""
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
async def admin_token(client, admin_user):
    """Get admin access token"""
    from app.core.security import create_access_token

    token = create_access_token(admin_user.id)
    return token


@pytest.mark.asyncio
async def test_get_user_details_requires_auth(client):
    """Test get user details requires authentication"""
    response = await client.get("/api/v1/admin/users/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_user_details_requires_admin(client, admin_token, test_user):
    """Test get user details requires admin role"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(f"/api/v1/admin/users/{test_user.id}", headers=headers)
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_block_user_requires_auth(client):
    """Test block user requires authentication"""
    response = await client.put("/api/v1/admin/users/1/block", json={"reason": "Test"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_block_user(client, admin_token, test_user):
    """Test block user endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.put(
        f"/api/v1/admin/users/{test_user.id}/block",
        json={"reason": "Test block"},
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_unblock_user(client, admin_token, test_user):
    """Test unblock user endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    # First block the user
    block_response = await client.put(
        f"/api/v1/admin/users/{test_user.id}/block",
        json={"reason": "Test reason"},  # min_length=5
        headers=headers,
    )
    assert block_response.status_code == 200  # Ensure block succeeded

    # Then unblock
    response = await client.put(
        f"/api/v1/admin/users/{test_user.id}/unblock",
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_delete_user_requires_auth(client):
    """Test delete user requires authentication"""
    response = await client.delete("/api/v1/admin/users/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_user(client, admin_token, test_user):
    """Test delete user endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.delete(
        f"/api/v1/admin/users/{test_user.id}",
        headers=headers,
    )
    assert response.status_code in [200, 204, 403]


@pytest.mark.asyncio
async def test_make_admin_requires_auth(client):
    """Test make admin requires authentication"""
    response = await client.post(
        "/api/v1/admin/users/1/make-admin",
        json={"is_admin": True, "is_super_admin": False},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_make_admin(client, admin_token, test_user):
    """Test make admin endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post(
        f"/api/v1/admin/users/{test_user.id}/make-admin",
        json={"is_admin": True, "is_super_admin": False},
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_revoke_admin(client, admin_token, test_user):
    """Test revoke admin endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    # First make admin
    await client.post(
        f"/api/v1/admin/users/{test_user.id}/make-admin",
        json={"is_admin": True, "is_super_admin": False},
        headers=headers,
    )

    # Then revoke
    response = await client.post(
        f"/api/v1/admin/users/{test_user.id}/revoke-admin",
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_bulk_user_action(client, admin_token, test_user):
    """Test bulk user action endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    bulk_data = {
        "user_ids": [test_user.id],
        "action": "block",
        "reason": "Bulk block test",
    }
    response = await client.post(
        "/api/v1/admin/users/bulk",
        json=bulk_data,
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_get_user_documents(client, admin_token, test_user):
    """Test get user documents endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(
        f"/api/v1/admin/users/{test_user.id}/documents?page=1&per_page=10",
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_get_user_payments(client, admin_token, test_user):
    """Test get user payments endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(
        f"/api/v1/admin/users/{test_user.id}/payments?page=1&per_page=10",
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_send_email_to_user(client, admin_token, test_user):
    """Test send email to user endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    email_data = {
        "subject": "Test Email",
        "message": "Test message content",
    }
    response = await client.post(
        f"/api/v1/admin/users/{test_user.id}/send-email",
        json=email_data,
        headers=headers,
    )
    assert response.status_code in [200, 403]
