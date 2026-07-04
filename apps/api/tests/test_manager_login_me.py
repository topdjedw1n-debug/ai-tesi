"""
Regression: manager accounts use bare logins (no @) stored in User.email.

GET /api/v1/auth/me must serialize such users instead of 500-ing on
EmailStr response validation — otherwise a manager can log in but the
console immediately kicks them back to the login page.
"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.auth import User
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_me_works_for_bare_login_manager(client, db_session):
    manager = User(
        email="manager1",  # bare login, not an email address
        full_name="Manager One",
        is_active=True,
        is_verified=True,
    )
    db_session.add(manager)
    await db_session.commit()
    await db_session.refresh(manager)

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {create_access_token(user_id=manager.id)}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "manager1"
    assert body["id"] == manager.id
