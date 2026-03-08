"""
Regression tests for documents stats routing.
"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.auth import User
from main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(db_session):
    """Create test user."""
    user = User(
        email="stats-route@test.com",
        full_name="Stats Route User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user: User):
    """Create authentication headers."""
    token = create_access_token(user_id=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_documents_stats_returns_200(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """Ensure /documents/stats is resolved as static route, not document_id."""
    response = await client.get("/api/v1/documents/stats", headers=auth_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


@pytest.mark.asyncio
async def test_get_document_with_non_numeric_id_returns_422(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """Ensure dynamic document route keeps int validation semantics."""
    response = await client.get("/api/v1/documents/not-a-number", headers=auth_headers)

    assert response.status_code == 422
