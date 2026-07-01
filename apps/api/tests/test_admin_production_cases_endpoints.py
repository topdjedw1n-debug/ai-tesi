"""Focused tests for Phase B production case admin endpoints."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.auth import User
from app.models.document import Document, ProductionCase
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_user(db_session):
    user = User(
        email="production-admin@example.com",
        is_active=True,
        is_admin=True,
        is_super_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def regular_user(db_session):
    user = User(
        email="production-client@example.com",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def editor_user(db_session):
    user = User(
        email="production-editor@example.com",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_document(db_session, regular_user):
    document = Document(
        user_id=regular_user.id,
        title="AI Governance Thesis",
        topic="AI governance in European universities",
        language="en",
        target_pages=40,
        status="draft",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.mark.asyncio
async def test_production_cases_require_auth(client):
    response = await client.get("/api/v1/admin/production-cases")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_production_cases_require_admin(client, regular_user):
    response = await client.get(
        "/api/v1/admin/production-cases",
        headers=auth_headers(regular_user),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_production_case_patch_allows_browser_preflight(client):
    response = await client.options(
        "/api/v1/admin/production-cases/1",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
        },
    )

    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]


@pytest.mark.asyncio
async def test_admin_can_create_production_case_without_payment(
    client, admin_user, sample_document, editor_user
):
    deadline = (datetime.utcnow() + timedelta(days=7)).isoformat()

    response = await client.post(
        "/api/v1/admin/production-cases",
        headers=auth_headers(admin_user),
        json={
            "document_id": sample_document.id,
            "manager_id": admin_user.id,
            "editor_id": editor_user.id,
            "deadline_at": deadline,
            "citation_style": "apa",
            "requirements_text": "Use current EU AI Act sources.",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["document_id"] == sample_document.id
    assert body["client_user_id"] == sample_document.user_id
    assert body["manager_id"] == admin_user.id
    assert body["editor_id"] == editor_user.id
    assert body["citation_style"] == "apa"
    assert body["requirements_text"] == "Use current EU AI Act sources."

    assert body["intake_status"] == "draft"
    assert body["generation_status"] == "not_started"
    assert body["qa_status"] == "no_data"
    assert body["editorial_status"] == "not_started"
    assert body["payment_status"] == "not_required"
    assert body["delivery_status"] == "not_ready"
    assert body["release_status"] == "not_ready"

    assert body["document"]["id"] == sample_document.id
    assert body["document"]["title"] == sample_document.title
    assert body["client_email"] == "production-client@example.com"


@pytest.mark.asyncio
async def test_admin_can_list_and_get_production_cases(
    client, db_session, admin_user, sample_document
):
    production_case = ProductionCase(
        document_id=sample_document.id,
        client_user_id=sample_document.user_id,
        manager_id=admin_user.id,
        citation_style="mla",
        requirements_text="Match the department rubric.",
        intake_status="ready",
        generation_status="running",
        qa_status="no_data",
    )
    db_session.add(production_case)
    await db_session.commit()
    await db_session.refresh(production_case)

    list_response = await client.get(
        "/api/v1/admin/production-cases",
        headers=auth_headers(admin_user),
    )
    assert list_response.status_code == 200, list_response.text
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["cases"][0]["id"] == production_case.id
    assert list_body["cases"][0]["generation_status"] == "running"

    get_response = await client.get(
        f"/api/v1/admin/production-cases/{production_case.id}",
        headers=auth_headers(admin_user),
    )
    assert get_response.status_code == 200, get_response.text
    get_body = get_response.json()
    assert get_body["id"] == production_case.id
    assert get_body["document"]["status"] == sample_document.status
    assert get_body["manager_email"] == "production-admin@example.com"


@pytest.mark.asyncio
async def test_admin_can_patch_separate_status_dimensions(
    client, db_session, admin_user, sample_document, editor_user
):
    production_case = ProductionCase(
        document_id=sample_document.id,
        client_user_id=sample_document.user_id,
    )
    db_session.add(production_case)
    await db_session.commit()
    await db_session.refresh(production_case)

    response = await client.patch(
        f"/api/v1/admin/production-cases/{production_case.id}",
        headers=auth_headers(admin_user),
        json={
            "manager_id": admin_user.id,
            "editor_id": editor_user.id,
            "intake_status": "ready",
            "generation_status": "completed",
            "qa_status": "needs_review",
            "editorial_status": "in_progress",
            "payment_status": "pending",
            "delivery_status": "not_ready",
            "release_status": "blocked",
            "human_minutes_budget": 45,
            "human_minutes_used": 12,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["manager_id"] == admin_user.id
    assert body["editor_id"] == editor_user.id
    assert body["intake_status"] == "ready"
    assert body["generation_status"] == "completed"
    assert body["qa_status"] == "needs_review"
    assert body["editorial_status"] == "in_progress"
    assert body["payment_status"] == "pending"
    assert body["delivery_status"] == "not_ready"
    assert body["release_status"] == "blocked"
    assert body["human_minutes_budget"] == 45
    assert body["human_minutes_used"] == 12


@pytest.mark.asyncio
async def test_create_production_case_rejects_duplicate_document(
    client, db_session, admin_user, sample_document
):
    db_session.add(
        ProductionCase(
            document_id=sample_document.id,
            client_user_id=sample_document.user_id,
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/admin/production-cases",
        headers=auth_headers(admin_user),
        json={"document_id": sample_document.id},
    )

    assert response.status_code == 409
