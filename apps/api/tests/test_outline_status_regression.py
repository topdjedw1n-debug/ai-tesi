"""Regression: ISSUE-002, active full run hidden after outline persistence.

Found by /qa on 2026-09-07.
Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
"""

from unittest.mock import AsyncMock

import pytest

from app.models.auth import User
from app.models.document import Document
from app.services.ai_service import AIService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial_status", "expected_status"),
    [("generating", "generating"), ("draft", "outline_generated")],
)
async def test_outline_preserves_active_full_run(
    db_session, monkeypatch, initial_status, expected_status
):
    user = User(email="outline-status@example.com", is_active=True)
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Outline checkpoint",
        topic="Preserving the state of a full generation",
        status=initial_status,
        ai_provider="anthropic",
        ai_model="claude-opus-4-8",
    )
    db_session.add(document)
    await db_session.commit()
    provider = AsyncMock(
        return_value={
            "sections": [{"title": "Introduzione", "estimated_words": 1000}],
            "tokens_used": 50,
        }
    )
    monkeypatch.setattr(AIService, "_call_ai_provider", provider)
    fence = AsyncMock()

    await AIService(db_session).generate_outline(
        document.id, user.id, before_persist=fence
    )

    await db_session.refresh(document)
    assert document.status == expected_status
    assert document.outline["sections"][0]["title"] == "Introduzione"
    assert document.tokens_used == 50
    fence.assert_awaited_once()
