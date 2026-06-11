"""
Config dependency guards.

Claim verification reads source abstracts from
DocumentSource.canonical_metadata, populated only by the citation
verification stage — enabling claim verification without citation
verification would produce pure 'uncertain' noise, so Settings must
fail fast on that combination (see Settings.validate_verification_dependencies).
"""
import os

import pytest

# Required env vars so Settings() constructs in a bare test environment
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.config import Settings


def test_claim_verification_requires_citation_verification():
    with pytest.raises(ValueError, match="CLAIM_VERIFICATION_ENABLED"):
        Settings(
            CLAIM_VERIFICATION_ENABLED=True,
            CITATION_VERIFICATION_ENABLED=False,
        )


def test_claim_with_citation_accepted():
    settings = Settings(
        CLAIM_VERIFICATION_ENABLED=True,
        CITATION_VERIFICATION_ENABLED=True,
    )
    assert settings.CLAIM_VERIFICATION_ENABLED is True
    assert settings.CITATION_VERIFICATION_ENABLED is True


def test_defaults_accepted():
    settings = Settings()
    assert settings.CLAIM_VERIFICATION_ENABLED is False
    assert settings.CITATION_VERIFICATION_ENABLED is False


def test_citation_without_claim_accepted():
    settings = Settings(
        CITATION_VERIFICATION_ENABLED=True,
        CLAIM_VERIFICATION_ENABLED=False,
    )
    assert settings.CITATION_VERIFICATION_ENABLED is True
    assert settings.CLAIM_VERIFICATION_ENABLED is False
