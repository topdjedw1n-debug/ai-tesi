"""
JWT Security Tests

Tests for JWT secret key validation, token expiration, and claims.
"""
import os
from datetime import datetime, timedelta

import pytest
from jose import jwt

from app.core.config import Settings
from app.models.auth import User
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_jwt_secret_validation_short_key():
    """Test that short JWT_SECRET is rejected"""
    # Save original env
    original_env = os.environ.copy()

    try:
        # Set short JWT_SECRET
        os.environ["JWT_SECRET"] = "short"
        os.environ["ENVIRONMENT"] = "development"

        with pytest.raises(
            ValueError, match="JWT_SECRET must be at least 32 characters"
        ):
            Settings()
    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


@pytest.mark.asyncio
async def test_jwt_secret_validation_forbidden_word():
    """Test that JWT_SECRET with forbidden words is rejected"""
    # Save original env
    original_env = os.environ.copy()

    try:
        # Set JWT_SECRET with forbidden word
        os.environ["JWT_SECRET"] = "secretpassword12345678901234567890"
        os.environ["ENVIRONMENT"] = "development"

        with pytest.raises(ValueError, match="must not contain forbidden words"):
            Settings()
    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


@pytest.mark.asyncio
async def test_jwt_secret_same_as_secret_key():
    """Test that JWT_SECRET cannot be same as SECRET_KEY in production"""
    # Save original env
    original_env = os.environ.copy()

    try:
        # Set same values
        same_key = "a" * 64
        os.environ["SECRET_KEY"] = same_key
        os.environ["JWT_SECRET"] = same_key
        os.environ["ENVIRONMENT"] = "production"
        # Use realistic production database URL (not localhost or default credentials)
        os.environ[
            "DATABASE_URL"
        ] = "postgresql+asyncpg://produser:prodpass123@db.example.com:5432/proddb"
        # Set CORS_ALLOWED_ORIGINS for production (no localhost)
        os.environ[
            "CORS_ALLOWED_ORIGINS"
        ] = "https://example.com,https://app.example.com"

        with pytest.raises(
            ValueError, match="JWT_SECRET must be different from SECRET_KEY"
        ):
            Settings()
    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


@pytest.mark.asyncio
async def test_jwt_token_expires_after_1_hour(db_session):
    """Test that access token expires after 1 hour"""
    # Create user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = AuthService(db_session)

    # Create access token (default is 30 minutes, but test with 1 hour setting)
    from app.core.config import settings

    original_exp = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    try:
        # Set to 1 hour
        settings.ACCESS_TOKEN_EXPIRE_MINUTES = 60

        access_token = service._create_access_token(user.id)

        # Decode and check expiration
        payload = jwt.decode(
            access_token, settings.jwt_secret_key, algorithms=[settings.JWT_ALG]
        )

        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        time_until_expiry = exp_time - now

        # Should be close to 1 hour (allow 1 minute tolerance)
        assert 59 <= time_until_expiry.total_seconds() / 60 <= 61
    finally:
        settings.ACCESS_TOKEN_EXPIRE_MINUTES = original_exp


@pytest.mark.asyncio
async def test_refresh_token_expires_after_7_days(db_session):
    """Test that refresh token expires after 7 days"""
    # Create user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = AuthService(db_session)
    refresh_token = service._create_refresh_token(user.id)

    # Decode and check expiration
    from app.core.config import settings

    payload = jwt.decode(
        refresh_token, settings.jwt_secret_key, algorithms=[settings.JWT_ALG]
    )

    exp_time = datetime.fromtimestamp(payload["exp"])
    now = datetime.utcnow()
    time_until_expiry = exp_time - now

    # Should be close to 7 days (allow 1 hour tolerance)
    assert 6.9 <= time_until_expiry.total_seconds() / (3600 * 24) <= 7.1


@pytest.mark.asyncio
async def test_jwt_token_with_iss_claim(db_session):
    """Test that JWT includes iss claim when configured"""
    # Save original env
    original_env = os.environ.copy()

    try:
        # Set JWT_ISS
        os.environ["JWT_ISS"] = "tesigo.com"
        os.environ["JWT_AUD"] = "tesigo-api"

        # Recreate settings
        settings = Settings()

        user = User(email="test@example.com", full_name="Test User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        service = AuthService(db_session)
        access_token = service._create_access_token(user.id)

        # Decode and check iss claim
        payload = jwt.decode(
            access_token,
            settings.jwt_secret_key,
            algorithms=[settings.JWT_ALG],
            issuer=settings.JWT_ISS,
            audience=settings.JWT_AUD,
        )

        assert "iss" in payload
        assert payload["iss"] == "tesigo.com"
        assert "aud" in payload
        assert payload["aud"] == "tesigo-api"
    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


@pytest.mark.asyncio
async def test_jwt_token_without_iss_claim(db_session):
    """Test that JWT doesn't include iss claim when not configured"""
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = AuthService(db_session)
    access_token = service._create_access_token(user.id)

    # Decode without requiring iss
    from app.core.config import settings

    payload = jwt.decode(
        access_token,
        settings.jwt_secret_key,
        algorithms=[settings.JWT_ALG],
        options={"verify_iss": False, "verify_aud": False},
    )

    # Should not have iss/aud when not configured
    assert "iss" not in payload
    assert "aud" not in payload


@pytest.mark.asyncio
async def test_jwt_token_invalid_iss(db_session):
    """Test that JWT with wrong iss claim is rejected"""
    # Save original env
    original_env = os.environ.copy()

    try:
        # Set JWT_ISS
        os.environ["JWT_ISS"] = "tesigo.com"

        # Recreate settings
        settings = Settings()

        user = User(email="test@example.com", full_name="Test User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        service = AuthService(db_session)
        access_token = service._create_access_token(user.id)

        # Try to decode with wrong issuer
        with pytest.raises(jwt.InvalidIssuerError):
            jwt.decode(
                access_token,
                settings.jwt_secret_key,
                algorithms=[settings.JWT_ALG],
                issuer="wrong-issuer.com",
            )
    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


@pytest.mark.asyncio
async def test_jwt_token_invalid_signature(db_session):
    """Test that JWT with invalid signature is rejected"""
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = AuthService(db_session)
    access_token = service._create_access_token(user.id)

    # Try to decode with wrong secret
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(access_token, "wrong-secret-key", algorithms=["HS256"])


@pytest.mark.asyncio
async def test_jwt_token_nbf_claim(db_session):
    """Test that JWT includes nbf (not before) claim"""
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = AuthService(db_session)
    access_token = service._create_access_token(user.id)

    # Decode and check nbf claim
    from app.core.config import settings

    payload = jwt.decode(
        access_token, settings.jwt_secret_key, algorithms=[settings.JWT_ALG]
    )

    assert "nbf" in payload
    nbf_time = datetime.fromtimestamp(payload["nbf"])
    now = datetime.utcnow()

    # nbf should be close to now (allow 1 minute tolerance)
    assert (now - timedelta(minutes=1)) <= nbf_time <= (now + timedelta(minutes=1))
