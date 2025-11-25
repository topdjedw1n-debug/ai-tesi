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

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.JWT_ALG)
