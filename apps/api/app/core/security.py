"""
Security utilities for token generation
"""

from datetime import datetime, timedelta

from jose import jwt

from app.core.config import settings


def create_access_token(user_id: int) -> str:
    """
    Create access token with iss, aud, and expiration claims.

    This is a standalone function for use in tests and utilities.
    For service usage, prefer AuthService._create_access_token().
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "access",
        "nbf": now,  # Not before - token valid from now
    }

    # Add iss (issuer) if configured
    if settings.JWT_ISS:
        to_encode["iss"] = settings.JWT_ISS

    # Add aud (audience) if configured
    if settings.JWT_AUD:
        to_encode["aud"] = settings.JWT_AUD

    return str(
        jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.JWT_ALG)
    )


def create_download_token(
    document_id: int, user_id: int, expiration_minutes: int = 60
) -> str:
    """
    Create JWT token for secure document download.

    Args:
        document_id: ID of the document to download
        user_id: ID of the user requesting download
        expiration_minutes: Token expiration time (default: 60 minutes)

    Returns:
        JWT token string for download authorization
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=expiration_minutes)
    to_encode = {
        "document_id": document_id,
        "user_id": user_id,
        "type": "download",
        "exp": expire,
        "iat": now,
        "iss": "tesigo-api",
        "aud": "tesigo-download",
    }
    return str(
        jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.JWT_ALG)
    )
