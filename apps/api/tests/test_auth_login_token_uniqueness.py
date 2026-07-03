"""
Regression tests for duplicate session_token on rapid logins.

Two POST /auth/login for the same user within the same second used to
produce byte-identical refresh JWTs (iat/exp/nbf have 1-second resolution),
violating the unique index ix_user_sessions_session_token and turning a
valid login into a 401. Tokens now carry a random ``jti`` claim.
"""

import pytest
from sqlalchemy import select

from app.models.auth import User, UserSession
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_refresh_tokens_unique_within_same_second(db_session):
    service = AuthService(db_session)

    tokens = {service._create_refresh_token(1) for _ in range(20)}

    assert len(tokens) == 20


@pytest.mark.asyncio
async def test_access_tokens_unique_within_same_second(db_session):
    service = AuthService(db_session)

    tokens = {service._create_access_token(1) for _ in range(20)}

    assert len(tokens) == 20


@pytest.mark.asyncio
async def test_two_rapid_password_logins_both_succeed(db_session):
    user = User(
        email="manager-rapid@example.com",
        password_hash=AuthService.hash_password("secret123"),
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    service = AuthService(db_session)

    first = await service.login_with_password("manager-rapid@example.com", "secret123")
    second = await service.login_with_password("manager-rapid@example.com", "secret123")

    assert first["refresh_token"] != second["refresh_token"]

    result = await db_session.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    sessions = result.scalars().all()
    assert len(sessions) == 2
