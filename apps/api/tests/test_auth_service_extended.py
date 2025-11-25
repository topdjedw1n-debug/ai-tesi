"""
Extended tests for AuthService to improve coverage
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AuthenticationError, ValidationError
from app.models.auth import MagicLinkToken, User
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_send_magic_link_new_user(db_session):
    """Test sending magic link to new user (creates user)"""
    service = AuthService(db_session)

    result = await service.send_magic_link("newuser@example.com")

    assert "message" in result
    assert result["email"] == "newuser@example.com"

    # Verify user was created
    from sqlalchemy import select
    user_result = await db_session.execute(
        select(User).where(User.email == "newuser@example.com")
    )
    user = user_result.scalar_one_or_none()
    assert user is not None


@pytest.mark.asyncio
async def test_send_magic_link_existing_user(db_session):
    """Test sending magic link to existing user"""
    # Create existing user
    user = User(email="existing@example.com", full_name="Existing User")
    db_session.add(user)
    await db_session.commit()

    service = AuthService(db_session)

    result = await service.send_magic_link("existing@example.com")

    assert "message" in result
    assert result["email"] == "existing@example.com"


@pytest.mark.asyncio
async def test_send_magic_link_invalid_email(db_session):
    """Test sending magic link with invalid email"""
    service = AuthService(db_session)

    with pytest.raises((ValidationError, AuthenticationError)):
        await service.send_magic_link("invalid-email")


@pytest.mark.asyncio
async def test_verify_magic_link_success(db_session):
    """Test verifying magic link successfully"""
    # Create user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create magic link token
    token = "test-magic-token-12345"
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    magic_token = MagicLinkToken(
        token=token,
        email=user.email,
        expires_at=expires_at,
        is_used=False
    )
    db_session.add(magic_token)
    await db_session.commit()

    service = AuthService(db_session)

    result = await service.verify_magic_link(token)

    assert "access_token" in result
    assert "user" in result

    # Verify token was marked as used
    await db_session.refresh(magic_token)
    assert magic_token.is_used is True


@pytest.mark.asyncio
async def test_verify_magic_link_invalid_token(db_session):
    """Test verifying invalid magic link token"""
    service = AuthService(db_session)

    with pytest.raises(AuthenticationError, match="Invalid or expired magic link"):
        await service.verify_magic_link("invalid-token")


@pytest.mark.asyncio
async def test_verify_magic_link_expired_token(db_session):
    """Test verifying expired magic link token"""
    # Create expired token
    token = "expired-token-12345"
    expires_at = datetime.utcnow() - timedelta(minutes=1)  # Expired
    magic_token = MagicLinkToken(
        token=token,
        email="test@example.com",
        expires_at=expires_at,
        is_used=False
    )
    db_session.add(magic_token)
    await db_session.commit()

    service = AuthService(db_session)

    with pytest.raises(AuthenticationError, match="Invalid or expired magic link"):
        await service.verify_magic_link(token)


@pytest.mark.asyncio
async def test_verify_magic_link_already_used(db_session):
    """Test verifying already used magic link token"""
    # Create used token
    token = "used-token-12345"
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    magic_token = MagicLinkToken(
        token=token,
        email="test@example.com",
        expires_at=expires_at,
        is_used=True,
        used_at=datetime.utcnow()
    )
    db_session.add(magic_token)
    await db_session.commit()

    service = AuthService(db_session)

    with pytest.raises(AuthenticationError, match="Invalid or expired magic link"):
        await service.verify_magic_link(token)


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session):
    """Test getting current user with invalid token"""
    service = AuthService(db_session)

    with pytest.raises(AuthenticationError):
        await service.get_current_user("invalid-token")


@pytest.mark.asyncio
async def test_get_current_user_user_not_found(db_session):
    """Test getting current user when user doesn't exist"""
    from datetime import datetime, timedelta

    from jose import jwt

    from app.core.config import settings

    # Create token for non-existent user
    secret_key = settings.JWT_SECRET or settings.SECRET_KEY
    payload = {
        "sub": "99999",  # Non-existent user ID
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    service = AuthService(db_session)

    with pytest.raises(AuthenticationError, match="User not found or inactive"):
        await service.get_current_user(token)


@pytest.mark.asyncio
async def test_get_current_user_inactive(db_session):
    """Test getting current user when user is inactive"""
    # Create inactive user
    user = User(email="inactive@example.com", full_name="Inactive User", is_active=False)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    from datetime import datetime, timedelta

    from jose import jwt

    from app.core.config import settings

    # Create token for inactive user
    secret_key = settings.JWT_SECRET or settings.SECRET_KEY
    payload = {
        "sub": str(user.id),
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    service = AuthService(db_session)

    with pytest.raises(AuthenticationError, match="User not found or inactive"):
        await service.get_current_user(token)

