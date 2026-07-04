"""
Tests for POST /api/v1/documents/{id}/feedback (manager feedback, internal MVP).

Feedback is stored as a DocumentProvenance event (stage="feedback",
event_type="manager_feedback") so it lands in the same append-only ledger
the admin already reads — no dedicated table.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.auth import User
from app.models.document import Document, DocumentProvenance
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


def auth_headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


async def seed_case(db_session):
    owner = User(email="fb-owner@test.com", full_name="Owner", is_active=True)
    other = User(email="fb-other@test.com", full_name="Other", is_active=True)
    admin = User(
        email="fb-admin@test.com", full_name="Admin", is_active=True, is_admin=True
    )
    db_session.add_all([owner, other, admin])
    await db_session.commit()
    for user in (owner, other, admin):
        await db_session.refresh(user)

    document = Document(user_id=owner.id, title="Feedback Doc", topic="AI in Education")
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return owner, other, admin, document


async def feedback_events(db_session, document_id):
    result = await db_session.execute(
        select(DocumentProvenance).where(
            DocumentProvenance.document_id == document_id,
            DocumentProvenance.stage == "feedback",
        )
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_owner_can_submit_feedback(client, db_session):
    owner, _, _, document = await seed_case(db_session)

    response = await client.post(
        f"/api/v1/documents/{document.id}/feedback",
        json={"text": "Вступ занадто загальний, третій розділ повторює другий."},
        headers=auth_headers_for(owner),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document_id"] == document.id
    assert body["event_id"] > 0

    events = await feedback_events(db_session, document.id)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "manager_feedback"
    assert event.payload["text"].startswith("Вступ занадто загальний")
    assert event.payload["author_id"] == owner.id
    assert event.payload["author_email"] == owner.email


@pytest.mark.asyncio
async def test_feedback_visible_in_provenance_ledger(client, db_session):
    owner, _, _, document = await seed_case(db_session)

    await client.post(
        f"/api/v1/documents/{document.id}/feedback",
        json={"text": "Джерела по третьому розділу застарілі."},
        headers=auth_headers_for(owner),
    )

    response = await client.get(
        f"/api/v1/documents/{document.id}/provenance",
        headers=auth_headers_for(owner),
    )
    assert response.status_code == 200
    events = response.json()["events"]
    feedback = [e for e in events if e["event_type"] == "manager_feedback"]
    assert len(feedback) == 1
    assert feedback[0]["stage"] == "feedback"
    assert feedback[0]["payload"]["text"] == "Джерела по третьому розділу застарілі."


@pytest.mark.asyncio
async def test_admin_can_submit_feedback_on_foreign_document(client, db_session):
    _, _, admin, document = await seed_case(db_session)

    response = await client.post(
        f"/api/v1/documents/{document.id}/feedback",
        json={"text": "Прийнято в роботу, дякую."},
        headers=auth_headers_for(admin),
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_foreign_user_gets_403(client, db_session):
    _, other, _, document = await seed_case(db_session)

    response = await client.post(
        f"/api/v1/documents/{document.id}/feedback",
        json={"text": "Не мій документ, але спробую."},
        headers=auth_headers_for(other),
    )

    assert response.status_code == 403
    assert await feedback_events(db_session, document.id) == []


@pytest.mark.asyncio
async def test_missing_document_404(client, db_session):
    owner, _, _, _ = await seed_case(db_session)

    response = await client.post(
        "/api/v1/documents/999999/feedback",
        json={"text": "Фідбек у порожнечу."},
        headers=auth_headers_for(owner),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_requires_auth(client, db_session):
    _, _, _, document = await seed_case(db_session)

    response = await client.post(
        f"/api/v1/documents/{document.id}/feedback",
        json={"text": "Анонімний фідбек."},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_html_is_stripped_and_short_text_rejected(client, db_session):
    owner, _, _, document = await seed_case(db_session)

    response = await client.post(
        f"/api/v1/documents/{document.id}/feedback",
        json={"text": "<script>alert(1)</script>Розділ 2 треба переписати."},
        headers=auth_headers_for(owner),
    )
    assert response.status_code == 201
    events = await feedback_events(db_session, document.id)
    assert events[0].payload["text"] == "alert(1)Розділ 2 треба переписати."

    too_short = await client.post(
        f"/api/v1/documents/{document.id}/feedback",
        json={"text": "<b></b>ok"},
        headers=auth_headers_for(owner),
    )
    assert too_short.status_code == 422
