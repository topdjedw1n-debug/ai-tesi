"""Configured managers can operate their own work without admin privileges."""

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.auth import User
from app.models.document import AIGenerationJob, Document, ProductionCase
from app.services.auth_service import AuthService
from app.services.storage_service import StorageService
from main import app

pytestmark = pytest.mark.asyncio
BASE = "/api/v1/admin/production-cases"


@pytest.fixture
async def operator(db_session, monkeypatch):
    user = User(
        email="manager1",
        is_active=True,
        is_verified=True,
        is_admin=False,
        password_hash=AuthService.hash_password("local-test-password"),
    )
    other = User(email="another-manager", is_active=True)
    db_session.add_all([user, other])
    await db_session.flush()
    own = Document(
        user_id=user.id,
        title="Own work",
        topic="Nursing review",
        status="draft",
        language="it",
        target_pages=18,
        work_type="tesi_triennale",
    )
    foreign = Document(
        user_id=other.id, title="Private work", topic="Private topic", status="draft"
    )
    db_session.add_all([own, foreign])
    await db_session.flush()
    foreign_case = ProductionCase(
        document_id=foreign.id, client_user_id=other.id, manager_id=other.id
    )
    db_session.add(foreign_case)
    await db_session.commit()
    monkeypatch.setattr(settings, "PRODUCTION_OPERATOR_USER_IDS", [user.id])
    return user, other, own, foreign, foreign_case


@pytest.fixture
async def client(operator):
    async with AsyncClient(
        app=app,
        base_url="http://test",
        headers={"Authorization": f"Bearer {create_access_token(operator[0].id)}"},
    ) as ac:
        yield ac


async def test_password_login_profile_and_own_case_without_generation(
    client, operator, db_session
):
    user, _, own, _, _ = operator
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "manager1", "password": "local-test-password"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["is_admin"] is False
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["can_access_production"] is True
    created = await client.post(
        BASE, json={"document_id": own.id, "citation_style": "apa"}
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    assert created.json()["manager_id"] == user.id
    listed = (await client.get(BASE)).json()
    assert listed["total"] == 1
    assert [case["id"] for case in listed["cases"]] == [case_id]
    assert (await client.get(f"{BASE}/{case_id}")).status_code == 200
    assert (await client.get(f"{BASE}/{case_id}/release-gates")).status_code == 200
    assert (
        await client.patch(f"{BASE}/{case_id}", json={"requirements_text": "APA"})
    ).status_code == 200
    missing_file = await client.post(f"/api/v1/admin/documents/{own.id}/download")
    assert missing_file.status_code == 409  # authorized, artifact genuinely absent
    release = await client.post(f"{BASE}/{case_id}/release", json={})
    assert release.status_code == 409  # quality gates remain enforced
    assert await db_session.scalar(select(func.count(AIGenerationJob.id))) == 0
    assert (await client.post(BASE, json={"document_id": own.id})).status_code == 409


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("intake_status", "ready"),
        ("generation_status", "completed"),
        ("qa_status", "passed"),
        ("editorial_status", "approved"),
        ("payment_status", "paid"),
        ("human_minutes_budget", 100),
        ("human_minutes_used", 0),
        ("cost_cents", 0),
    ],
)
async def test_operator_cannot_patch_administrative_statuses_or_costs(
    client, operator, field, value
):
    case = (await client.post(BASE, json={"document_id": operator[2].id})).json()
    response = await client.patch(f"{BASE}/{case['id']}", json={field: value})
    assert response.status_code == 403
    unchanged = (await client.get(f"{BASE}/{case['id']}")).json()
    assert unchanged[field] == case[field]


async def test_foreign_documents_cases_and_assignments_are_inaccessible(
    client, operator
):
    _, other, own, foreign, foreign_case = operator
    assert (
        await client.post(BASE, json={"document_id": foreign.id})
    ).status_code == 404
    assert (
        await client.post(BASE, json={"document_id": own.id, "manager_id": other.id})
    ).status_code == 403
    assert (
        await client.post(BASE, json={"document_id": own.id, "editor_id": other.id})
    ).status_code == 403
    for suffix in ("", "/release-gates"):
        assert (
            await client.get(f"{BASE}/{foreign_case.id}{suffix}")
        ).status_code == 404
    assert (
        await client.patch(f"{BASE}/{foreign_case.id}", json={"intake_status": "ready"})
    ).status_code == 404
    assert (
        await client.post(f"{BASE}/{foreign_case.id}/release", json={})
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/admin/documents/{foreign.id}/download")
    ).status_code == 404
    assert (await client.get(BASE, params={"manager_id": other.id})).json()[
        "total"
    ] == 0
    case_id = (await client.post(BASE, json={"document_id": own.id})).json()["id"]
    assert (
        await client.patch(f"{BASE}/{case_id}", json={"manager_id": other.id})
    ).status_code == 403


async def test_internal_docx_and_both_detector_results_stay_bound_to_own_artifact(
    client, operator, db_session, monkeypatch
):
    _, _, own, _, foreign_case = operator
    case_id = (await client.post(BASE, json={"document_id": own.id})).json()["id"]
    own.status = "completed"
    own.completed_at = datetime.now(UTC)
    own.docx_path = f"documents/{own.id}/review.docx"
    docx_bytes = b"PK synthetic internal review DOCX for operator test"
    docx_sha256 = hashlib.sha256(docx_bytes).hexdigest()
    own.docx_sha256 = docx_sha256
    await db_session.commit()
    report_bytes = b"%PDF-1.7\nOwn Compilatio report\n%%EOF"
    report_path = "s3://tests/detector-reports/report.pdf"
    monkeypatch.setattr(
        StorageService, "upload_file", AsyncMock(return_value=report_path)
    )
    monkeypatch.setattr(
        StorageService,
        "download_file",
        AsyncMock(
            side_effect=lambda path: report_bytes if path == report_path else docx_bytes
        ),
    )
    monkeypatch.setattr(
        StorageService,
        "get_file_sha256",
        AsyncMock(
            side_effect=lambda path: (
                hashlib.sha256(report_bytes).hexdigest()
                if path == report_path
                else docx_sha256
            )
        ),
    )
    response = await client.post(f"/api/v1/admin/documents/{own.id}/download")
    assert response.status_code == 200, response.text
    assert "token=" in response.json()["download_url"]
    downloaded = await client.get(response.json()["download_url"])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == docx_bytes
    current = (await client.get(f"{BASE}/{case_id}")).json()
    fingerprint = current["document"]["artifact_bindings"]["docx"]["fingerprint_sha256"]
    uploaded = await client.post(
        f"{BASE}/{case_id}/detector-reports",
        data={"artifact_fingerprint_sha256": fingerprint},
        files={"file": ("Compilatio.pdf", report_bytes, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    report_id = uploaded.json()["id"]
    assert (await client.get(f"{BASE}/{case_id}/detector-reports")).json()[0][
        "id"
    ] == report_id
    assert (
        await client.get(f"{BASE}/{case_id}/detector-reports/{report_id}/file")
    ).content == report_bytes
    assert (
        await client.get(f"{BASE}/{foreign_case.id}/detector-reports")
    ).status_code == 404
    assert (
        await client.get(f"{BASE}/{foreign_case.id}/detector-reports/{report_id}/file")
    ).status_code == 404
    assert (
        await client.post(
            f"{BASE}/{foreign_case.id}/detector-reports",
            data={"artifact_fingerprint_sha256": fingerprint},
            files={"file": ("Compilatio.pdf", report_bytes, "application/pdf")},
        )
    ).status_code == 404
    review = {
        "artifact_fingerprint_sha256": fingerprint,
        "decision": "accepted",
        "reviewed_page_count": 18,
    }
    assert (
        await client.post(f"{BASE}/{case_id}/content-review", json=review)
    ).status_code == 200
    assert (
        await client.post(f"{BASE}/{foreign_case.id}/content-review", json=review)
    ).status_code == 404
    for gate in ("plagiarism_proxy", "ai_detection_proxy"):
        payload = {
            "detector_name": "Compilatio",
            "result_percent": 10,
            "decision": "passed",
            "artifact_format": "docx",
            "checked_at": datetime.now(UTC).isoformat(),
            "report_id": report_id,
            "artifact_fingerprint_sha256": fingerprint,
            "report_matches_artifact": True,
            "reason": "Checked unchanged review artifact",
        }
        result = await client.post(
            f"{BASE}/{case_id}/release-gates/{gate}/detector-result", json=payload
        )
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "passed"
        assert (
            await client.post(
                f"{BASE}/{foreign_case.id}/release-gates/{gate}/detector-result",
                json=payload,
            )
        ).status_code == 404
    monkeypatch.setattr(
        StorageService, "get_file_sha256", AsyncMock(return_value="b" * 64)
    )
    assert (
        await client.post(f"/api/v1/admin/documents/{own.id}/download")
    ).status_code == 409


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("get", "/api/v1/admin/users", None),
        ("get", "/api/v1/admin/documents", None),
        ("get", "/api/v1/admin/settings", None),
        ("post", "/api/v1/admin/users/1/make-admin", {"is_admin": True}),
        (
            "post",
            f"{BASE}/1/release-gates/section_quality/override",
            {"reason": "Attempting an operator override"},
        ),
    ],
)
async def test_production_operator_does_not_receive_administration(
    client, method, path, payload
):
    response = await client.request(method, path, json=payload)
    assert response.status_code == 403, response.text


async def test_unconfigured_and_inactive_accounts_fail_closed(
    client, operator, db_session, monkeypatch
):
    user = operator[0]
    monkeypatch.setattr(settings, "PRODUCTION_OPERATOR_USER_IDS", [])
    assert (await client.get(BASE)).status_code == 403
    assert (await client.get("/api/v1/auth/me")).json()[
        "can_access_production"
    ] is False
    monkeypatch.setattr(settings, "PRODUCTION_OPERATOR_USER_IDS", [user.id])
    user.is_active = False
    await db_session.commit()
    assert (await client.get(BASE)).status_code == 401
