"""Phase 2 production case and release gate API coverage."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.auth import User
from app.models.document import Document, DocumentProvenance
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        ac.headers.update(
            {
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        yield ac


async def _create_user(
    *,
    email: str,
    is_admin: bool = False,
    is_super_admin: bool = False,
) -> User:
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            full_name=email.split("@")[0],
            is_active=True,
            is_verified=True,
            is_admin=is_admin,
            is_super_admin=is_super_admin,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _create_document(user_id: int, *, completed: bool = False) -> Document:
    async with AsyncSessionLocal() as session:
        document = Document(
            user_id=user_id,
            title="Agency Thesis",
            topic="AI governance in higher education",
            language="en",
            target_pages=20,
            status="completed" if completed else "draft",
            docx_path="/exports/agency-thesis.docx" if completed else None,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document


async def _add_provenance(document_id: int) -> None:
    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                DocumentProvenance(
                    document_id=document_id,
                    stage="verification",
                    event_type="citation_gate",
                    payload={"passed": True, "policy": "strict"},
                ),
                DocumentProvenance(
                    document_id=document_id,
                    stage="verification",
                    event_type="claim_check_summary",
                    payload={
                        "total_claims": 4,
                        "checked": 4,
                        "counts": {"supported": 4, "unsupported": 0},
                    },
                ),
                DocumentProvenance(
                    document_id=document_id,
                    stage="quality",
                    event_type="quality_gate",
                    payload={"passed": True, "section": "Introduction"},
                ),
            ]
        )
        await session.commit()


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(int(user.id))}"}


async def _create_case(client: AsyncClient, admin: User, document: Document) -> dict:
    response = await client.post(
        "/api/v1/admin/production-cases",
        json={
            "document_id": document.id,
            "manager_id": admin.id,
            "deadline_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "citation_style": "apa",
            "requirements_text": "Use peer-reviewed sources and retain QA evidence.",
        },
        headers=_auth_headers(admin),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_admin_case_starts_with_blocking_no_data_release_gates(client):
    admin = await _create_user(
        email="prod-admin-1@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-1@example.com")
    document = await _create_document(int(customer.id))

    case = await _create_case(client, admin, document)
    assert case["document_id"] == document.id
    assert case["payment_status"] == "not_required"

    gates_response = await client.get(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates",
        headers=_auth_headers(admin),
    )
    assert gates_response.status_code == 200
    gates = gates_response.json()
    assert {gate["gate_key"] for gate in gates} == {
        "citation_verification",
        "claim_support",
        "section_quality",
        "plagiarism_proxy",
        "ai_detection_proxy",
        "editorial_review",
        "delivery_package",
    }
    assert all(gate["status"] == "no_data" for gate in gates)

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Attempt before evidence."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 409
    assert "citation_verification" in release_response.json()["detail"]["blockers"]


@pytest.mark.asyncio
async def test_override_rules_are_enforced_and_audited(client):
    admin = await _create_user(
        email="prod-admin-2@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-2@example.com")
    document = await _create_document(int(customer.id))
    case = await _create_case(client, admin, document)

    forbidden_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "citation_verification/override",
        json={"reason": "Manual citation review passed."},
        headers=_auth_headers(admin),
    )
    assert forbidden_response.status_code == 400

    detector_override_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "plagiarism_proxy/override",
        json={"reason": "External plagiarism report is attached to the run report."},
        headers=_auth_headers(admin),
    )
    assert detector_override_response.status_code == 400

    override_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "claim_support/override",
        json={"reason": "Manager reviewed the claim support report manually."},
        headers=_auth_headers(admin),
    )
    assert override_response.status_code == 200, override_response.text
    gate = override_response.json()
    assert gate["gate_key"] == "claim_support"
    assert gate["status"] == "overridden"
    assert gate["override_reason"]


@pytest.mark.asyncio
async def test_editor_tasks_are_assigned_only_and_track_human_minutes(client):
    admin = await _create_user(
        email="prod-admin-3@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-3@example.com")
    editor = await _create_user(email="prod-editor-3@example.com")
    other_editor = await _create_user(email="prod-other-editor-3@example.com")
    document = await _create_document(int(customer.id), completed=True)
    case = await _create_case(client, admin, document)

    create_task_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/editor-tasks",
        json={
            "production_case_id": case["id"],
            "assigned_editor_id": editor.id,
            "source_gate": "section_quality",
            "finding_key": "intro-quality",
            "title": "Fix introduction evidence gap",
            "description": "Add source-backed context for the opening claim.",
        },
        headers=_auth_headers(admin),
    )
    assert create_task_response.status_code == 200, create_task_response.text
    task = create_task_response.json()

    editor_list_response = await client.get(
        "/api/v1/editor/tasks", headers=_auth_headers(editor)
    )
    assert editor_list_response.status_code == 200
    assert [item["id"] for item in editor_list_response.json()["tasks"]] == [task["id"]]

    other_get_response = await client.get(
        f"/api/v1/editor/tasks/{task['id']}", headers=_auth_headers(other_editor)
    )
    assert other_get_response.status_code == 403

    resolve_response = await client.post(
        f"/api/v1/editor/tasks/{task['id']}/resolve",
        json={
            "status": "resolved",
            "resolution_notes": "Added supported rewrite and checked citations.",
            "minutes_spent": 37,
        },
        headers=_auth_headers(editor),
    )
    assert resolve_response.status_code == 200, resolve_response.text
    assert resolve_response.json()["status"] == "resolved"

    case_response = await client.get(
        f"/api/v1/admin/production-cases/{case['id']}",
        headers=_auth_headers(admin),
    )
    assert case_response.status_code == 200
    updated_case = case_response.json()
    assert updated_case["human_minutes_used"] == 37
    assert updated_case["editorial_status"] == "completed"


@pytest.mark.asyncio
async def test_detector_results_are_structured_and_block_release_when_failed(client):
    admin = await _create_user(
        email="prod-admin-4@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-4@example.com")
    document = await _create_document(int(customer.id), completed=True)
    await _add_provenance(int(document.id))
    case = await _create_case(client, admin, document)

    failed_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "plagiarism_proxy/detector-result",
        json={
            "detector_name": "Plagiarism Proxy",
            "result_percent": 18.2,
            "threshold_percent": 15.0,
            "checked_at": datetime.utcnow().isoformat(),
            "report_ref": "docs/phase1-runs/RUN-001.md",
            "reason": "External plagiarism proxy report for the Phase 1 run.",
        },
        headers=_auth_headers(admin),
    )
    assert failed_response.status_code == 200, failed_response.text
    failed_gate = failed_response.json()
    assert failed_gate["status"] == "failed"
    assert failed_gate["evidence"]["detector_name"] == "Plagiarism Proxy"

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Attempt with failed detector result."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 409
    assert "plagiarism_proxy" in release_response.json()["detail"]["blockers"]


@pytest.mark.asyncio
async def test_release_requires_evidence_and_structured_detector_passes(client):
    admin = await _create_user(
        email="prod-admin-5@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-5@example.com")
    editor = await _create_user(email="prod-editor-5@example.com")
    document = await _create_document(int(customer.id), completed=True)
    await _add_provenance(int(document.id))
    case = await _create_case(client, admin, document)

    task_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/editor-tasks",
        json={
            "production_case_id": case["id"],
            "assigned_editor_id": editor.id,
            "source_gate": "editorial_review",
            "title": "Final editorial approval",
        },
        headers=_auth_headers(admin),
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["id"]
    resolve_response = await client.post(
        f"/api/v1/editor/tasks/{task_id}/resolve",
        json={
            "status": "resolved",
            "resolution_notes": "Final read complete.",
            "minutes_spent": 18,
        },
        headers=_auth_headers(editor),
    )
    assert resolve_response.status_code == 200

    detector_payloads = {
        "plagiarism_proxy": {
            "detector_name": "Plagiarism Proxy",
            "result_percent": 8.4,
            "threshold_percent": 15.0,
        },
        "ai_detection_proxy": {
            "detector_name": "GPTZero",
            "result_percent": 22.0,
            "threshold_percent": 35.0,
        },
    }
    for gate_key, detector_payload in detector_payloads.items():
        detector_response = await client.post(
            f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
            f"{gate_key}/detector-result",
            json={
                **detector_payload,
                "checked_at": datetime.utcnow().isoformat(),
                "report_ref": "docs/phase1-runs/RUN-001.md",
                "reason": "External detector proxy report is attached to the run report.",
            },
            headers=_auth_headers(admin),
        )
        assert detector_response.status_code == 200, detector_response.text
        assert detector_response.json()["status"] == "passed"

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Release approved after evidence review."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 200, release_response.text
    released_case = release_response.json()
    assert released_case["release_status"] == "released"
    assert released_case["delivery_status"] == "delivered"
