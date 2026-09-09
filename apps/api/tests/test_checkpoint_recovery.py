"""
Tests for checkpoint recovery system (Task 3.7.7)

Tests checkpoint save/load/cleanup and idempotency for section generation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings

# Verify: Section 3 was generated (not 1 or 2)
# Should only generate sections 3+ (sections 1-2 skipped)
# Exact verification depends on mocking completeness


# ========== Fixtures ==========


@pytest.fixture
def mock_db():
    """Mock async database session"""
    return MagicMock()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.delete = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings with quality gates enabled"""
    settings = Settings(
        QUALITY_GATES_ENABLED=True,
        QUALITY_GATES_MAX_CONTEXT_SECTIONS=10,
        QUALITY_MAX_REGENERATE_ATTEMPTS=2,
    )
    monkeypatch.setattr("app.services.background_jobs.settings", settings)
    return settings
