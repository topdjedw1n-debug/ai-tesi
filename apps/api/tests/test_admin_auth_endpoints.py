"""
Regression tests for admin auth endpoints.
Covers the admin logout typing fix (dict[str, Any] instead of dict[str, str]).
"""
import os

import pytest
from httpx import AsyncClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.core.database import AsyncSessionLocal, Base, get_engine  # noqa: E402
from app.models.user import User  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def admin_user(db_session):
    admin = User(
        email="admin-auth-test@test.com",
        is_active=True,
        is_admin=True,
        is_super_admin=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def admin_token(admin_user):
    from app.core.security import create_access_token

    return create_access_token(admin_user.id)


@pytest.mark.asyncio
async def test_admin_logout_requires_auth(client):
    """POST /api/v1/admin/auth/logout without token -> 401"""
    response = await client.post("/api/v1/admin/auth/logout")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_logout_returns_200(client, admin_token):
    """POST /api/v1/admin/auth/logout with valid admin token -> 200"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post("/api/v1/admin/auth/logout", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_logout_response_types(client, admin_token):
    """Response must have count:int and message:str (guards against dict[str,str] regression)"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post("/api/v1/admin/auth/logout", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "message" in data
    assert isinstance(data["count"], int)
    assert isinstance(data["message"], str)
