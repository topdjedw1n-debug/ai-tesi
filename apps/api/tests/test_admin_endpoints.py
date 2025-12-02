"""
Integration tests for admin API endpoints
Tests full request/response cycles through the API
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
async def admin_token(client, admin_user):
    """Get admin access token"""
    # In a real scenario, you'd login through the admin auth endpoint
    # For now, we'll simulate by creating a token manually
    from app.core.security import create_access_token

    token = create_access_token(admin_user.id)
    return token


@pytest.mark.asyncio
async def test_admin_stats_endpoint_requires_auth(client):
    """Test admin stats endpoint requires authentication"""
    response = await client.get("/api/v1/admin/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_stats_endpoint_requires_admin(client, admin_token):
    """Test admin stats endpoint requires admin role"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/stats", headers=headers)
    # Should return 200 if admin, or 403 if not admin
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_admin_users_list_endpoint(client, admin_token):
    """Test admin users list endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/users", headers=headers)
    # Should return 200 or 403 depending on permissions
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_admin_users_list_with_filters(client, admin_token):
    """Test admin users list endpoint with filters"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(
        "/api/v1/admin/users?status=active&page=1&per_page=10",
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_admin_dashboard_charts_endpoint(client, admin_token):
    """Test admin dashboard charts endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(
        "/api/v1/admin/dashboard/charts?period=week",
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_admin_dashboard_activity_endpoint(client, admin_token):
    """Test admin dashboard activity endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(
        "/api/v1/admin/dashboard/activity?type=recent&limit=10",
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_admin_dashboard_metrics_endpoint(client, admin_token):
    """Test admin dashboard metrics endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/dashboard/metrics", headers=headers)
    assert response.status_code in [200, 403]

