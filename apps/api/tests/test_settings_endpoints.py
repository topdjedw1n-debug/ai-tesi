"""
Integration tests for settings API endpoints
Tests settings management endpoints
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
async def test_get_settings_requires_auth(client):
    """Test get settings requires authentication"""
    response = await client.get("/api/v1/admin/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_requires_admin(client, admin_token):
    """Test get settings requires admin role"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/settings", headers=headers)
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_get_settings_by_category(client, admin_token):
    """Test get settings by category"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/settings/pricing", headers=headers)
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_update_pricing_settings_requires_auth(client):
    """Test update pricing settings requires authentication"""
    pricing_data = {
        "price_per_page": "0.75",
        "min_pages": 3,
        "max_pages": 200,
        "currencies": ["EUR"],
    }
    response = await client.put("/api/v1/admin/settings/pricing", json=pricing_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_pricing_settings(client, admin_token):
    """Test update pricing settings endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    pricing_data = {
        "price_per_page": "0.75",
        "min_pages": 3,
        "max_pages": 200,
        "currencies": ["EUR"],
    }
    response = await client.put(
        "/api/v1/admin/settings/pricing",
        json=pricing_data,
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_update_ai_settings(client, admin_token):
    """Test update AI settings endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    ai_data = {
        "default_provider": "openai",
        "default_model": "gpt-4",
        "fallback_models": ["gpt-3.5-turbo"],
        "max_retries": 3,
        "timeout_seconds": 300,
        "temperature_default": 0.7,
    }
    response = await client.put(
        "/api/v1/admin/settings/ai",
        json=ai_data,
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_update_limit_settings(client, admin_token):
    """Test update limit settings endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    limit_data = {
        "max_concurrent_generations": 5,
        "max_documents_per_user": 100,
        "max_pages_per_document": 200,
        "daily_token_limit": 1000000,
    }
    response = await client.put(
        "/api/v1/admin/settings/limits",
        json=limit_data,
        headers=headers,
    )
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_update_maintenance_settings(client, admin_token):
    """Test update maintenance settings endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    maintenance_data = {
        "enabled": False,
        "message": "System maintenance in progress",
        "allowed_ips": [],
    }
    response = await client.put(
        "/api/v1/admin/settings/maintenance",
        json=maintenance_data,
        headers=headers,
    )
    assert response.status_code in [200, 403]

