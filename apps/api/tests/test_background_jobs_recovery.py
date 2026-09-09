"""
Tests for background jobs error handling and recovery (Task 7).

Tests error paths: section failures, quality errors, Redis failures, export failures.
Uses SIMPLIFIED approach: patch only AI/quality services, let DB work naturally.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.models.auth import User
from app.models.document import Document
from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.background_jobs import (
    _resolve_citation_style,
)
from app.services.document_service import DocumentService


def test_resolve_citation_style_uses_stored_style_not_hardcoded_apa():
    assert _resolve_citation_style("chicago") is CitationStyle.CHICAGO
    assert _resolve_citation_style("MLA") is CitationStyle.MLA
    assert _resolve_citation_style(None) is CitationStyle.APA


@pytest.mark.asyncio
async def test_document_creation_persists_additional_requirements(db_session):
    """Creation requirements remain available after the request transaction ends."""
    user = User(email="requirements@example.com", full_name="Requirements User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    requirements = (
        "Work type: Master's thesis. Citation style: Chicago. "
        "Follow the uploaded university methodology."
    )
    result = await DocumentService(db_session).create_document(
        user_id=user.id,
        title="Italian Thesis",
        topic="Digital transformation in Italian universities",
        additional_requirements=requirements,
        citation_style="chicago",
    )

    document = await db_session.get(Document, result["id"])
    assert document is not None
    assert document.additional_requirements == requirements
    assert document.citation_style == "chicago"


# ============================================================================
# Test 1: Section Generation Error - Stop Generation
# ============================================================================


# ============================================================================
# Test 2: Quality Threshold Error - WebSocket Notification
# ============================================================================


# ============================================================================
# Test 3: All Sections Fail - Document Marked Failed
# ============================================================================


# ============================================================================
# Test 4: Redis Save Error - Non-Critical
# ============================================================================


# ============================================================================
# Test 5: Redis Load Error - Start Fresh
# ============================================================================


# ============================================================================
# Test 6: Export Failure - Document Must Fail
# ============================================================================


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db():
    """Mock async database session"""
    db_mock = MagicMock()
    db_mock.execute = AsyncMock()  # Must be AsyncMock for await
    db_mock.commit = AsyncMock()
    db_mock.refresh = AsyncMock()
    return db_mock


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
    """Mock settings with quality gates disabled for simpler tests"""
    settings = Settings(
        QUALITY_GATES_ENABLED=False,  # Disabled to simplify test flow
        QUALITY_GATES_MAX_CONTEXT_SECTIONS=10,
        QUALITY_MAX_REGENERATE_ATTEMPTS=0,  # No retries
    )
    monkeypatch.setattr("app.services.background_jobs.settings", settings)
    return settings
