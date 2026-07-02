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
                    payload={"passed": True, "status": "passed", "policy": "strict"},
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
                    # New honest shape: explicit status + per-check breakdown
                    # (a scoreless legacy payload would derive "unchecked")
                    payload={
                        "passed": True,
                        "status": "passed",
                        "section_index": 1,
                        "grammar_score": 95.0,
                        "plagiarism_score": 5.0,
                        "ai_detection_score": 20.0,
                        "quality_score": 85.0,
                        "checks": {
                            "grammar": {"status": "passed", "score": 95.0},
                            "plagiarism": {"status": "passed", "score": 5.0},
                            "ai_detection": {
                                "status": "passed",
                                "score": 20.0,
                                "provider": "gptzero",
                            },
                        },
                    },
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

    # citation_verification is overridable since Stage B: the audited
    # override is the intended resolution for mark_only "warning" states
    citation_override_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "citation_verification/override",
        json={"reason": "Manual citation review passed."},
        headers=_auth_headers(admin),
    )
    assert (
        citation_override_response.status_code == 200
    ), citation_override_response.text
    assert citation_override_response.json()["status"] == "overridden"

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


async def _add_event(document_id: int, stage: str, event_type: str, payload: dict):
    async with AsyncSessionLocal() as session:
        session.add(
            DocumentProvenance(
                document_id=document_id,
                stage=stage,
                event_type=event_type,
                payload=payload,
            )
        )
        await session.commit()


async def _get_gate(client: AsyncClient, admin: User, case_id: int, gate_key: str):
    response = await client.get(
        f"/api/v1/admin/production-cases/{case_id}/release-gates",
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    return next(g for g in response.json() if g["gate_key"] == gate_key)


@pytest.mark.asyncio
async def test_section_quality_gate_unchecked_from_new_event(client):
    """A quality_gate event with status='unchecked' surfaces as an unchecked
    gate — not passed, not no_data."""
    admin = await _create_user(
        email="prod-admin-b1a@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-b1a@example.com")
    document = await _create_document(int(customer.id), completed=True)
    await _add_event(
        int(document.id),
        "quality",
        "quality_gate",
        {
            "section_index": 1,
            "passed": False,
            "status": "unchecked",
            "checks": {
                "grammar": {"status": "passed", "score": 95.0},
                "plagiarism": {"status": "passed", "score": 5.0},
                "ai_detection": {
                    "status": "unchecked",
                    "score": None,
                    "reason": "AI detection is disabled",
                    "provider": "none",
                },
            },
        },
    )
    case = await _create_case(client, admin, document)

    gate = await _get_gate(client, admin, case["id"], "section_quality")
    assert gate["status"] == "unchecked"
    assert gate["evidence"]["unchecked"] == 1
    assert "unchecked" in gate["summary"]


@pytest.mark.asyncio
async def test_section_quality_gate_unchecked_from_legacy_events(client):
    """Legacy fail-open events (passed=True but null scores or gates
    disabled) are reinterpreted as unchecked at read time."""
    admin = await _create_user(
        email="prod-admin-b1b@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-b1b@example.com")
    document = await _create_document(int(customer.id), completed=True)
    # Legacy shape 1: provider silently failed -> null score, passed=True
    await _add_event(
        int(document.id),
        "quality",
        "quality_gate",
        {
            "section_index": 1,
            "passed": True,
            "gates_enabled": True,
            "grammar_score": None,
            "plagiarism_score": 5.0,
            "ai_detection_score": 20.0,
            "quality_score": 80.0,
        },
    )
    # Legacy shape 2: gates disabled entirely
    await _add_event(
        int(document.id),
        "quality",
        "quality_gate",
        {
            "section_index": 2,
            "passed": True,
            "gates_enabled": False,
            "grammar_score": 95.0,
            "plagiarism_score": 5.0,
            "ai_detection_score": 20.0,
            "quality_score": 80.0,
        },
    )
    case = await _create_case(client, admin, document)

    gate = await _get_gate(client, admin, case["id"], "section_quality")
    assert gate["status"] == "unchecked"
    assert gate["evidence"] == {"total": 2, "failed": 0, "unchecked": 2}


@pytest.mark.asyncio
async def test_citation_gate_warning_for_mark_only_not_found(client):
    """mark_only + not_found sources must show 'warning', never 'passed' —
    both for new events (explicit status) and legacy ones (derived)."""
    admin = await _create_user(
        email="prod-admin-b1c@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-b1c@example.com")

    # Legacy event: passed=True, no status key
    legacy_doc = await _create_document(int(customer.id), completed=True)
    await _add_event(
        int(legacy_doc.id),
        "verification",
        "citation_gate",
        {
            "passed": True,
            "policy": "mark_only",
            "counts": {"verified": 3, "not_found": 2},
            "not_found_count": 2,
            "not_found_titles": ["Phantom A", "Phantom B"],
        },
    )
    legacy_case = await _create_case(client, admin, legacy_doc)
    legacy_gate = await _get_gate(
        client, admin, legacy_case["id"], "citation_verification"
    )
    assert legacy_gate["status"] == "warning"
    assert "2" in legacy_gate["summary"]

    # New event: explicit status
    new_doc = await _create_document(int(customer.id), completed=True)
    await _add_event(
        int(new_doc.id),
        "verification",
        "citation_gate",
        {
            "passed": True,
            "status": "warning",
            "policy": "mark_only",
            "counts": {"verified": 3, "not_found": 1},
            "not_found_count": 1,
            "not_found_titles": ["Phantom C"],
        },
    )
    new_case = await _create_case(client, admin, new_doc)
    new_gate = await _get_gate(client, admin, new_case["id"], "citation_verification")
    assert new_gate["status"] == "warning"


@pytest.mark.asyncio
async def test_release_blocked_by_unchecked_and_warning_until_override(client):
    """unchecked/warning gates block release like failures; an audited
    override is the resolution path."""
    admin = await _create_user(
        email="prod-admin-b1d@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-b1d@example.com")
    editor = await _create_user(email="prod-editor-b1d@example.com")
    document = await _create_document(int(customer.id), completed=True)

    # citation gate -> warning; quality gate -> unchecked; claims -> passed
    await _add_event(
        int(document.id),
        "verification",
        "citation_gate",
        {
            "passed": True,
            "status": "warning",
            "policy": "mark_only",
            "counts": {"not_found": 1},
            "not_found_count": 1,
            "not_found_titles": ["Phantom"],
        },
    )
    await _add_event(
        int(document.id),
        "quality",
        "quality_gate",
        {"section_index": 1, "passed": False, "status": "unchecked"},
    )
    await _add_event(
        int(document.id),
        "verification",
        "claim_check_summary",
        {
            "total_claims": 4,
            "checked": 4,
            "counts": {"supported": 4, "unsupported": 0},
        },
    )
    case = await _create_case(client, admin, document)

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Attempt with unchecked evidence."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 409
    blockers = release_response.json()["detail"]["blockers"]
    assert "citation_verification" in blockers  # warning blocks
    assert "section_quality" in blockers  # unchecked blocks

    # Overrides with audited reasons clear the two Stage B blockers
    for gate_key, reason in (
        (
            "citation_verification",
            "Manager verified the two flagged sources manually.",
        ),
        ("section_quality", "Checks re-run manually; scores attached to run report."),
    ):
        override = await client.post(
            f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
            f"{gate_key}/override",
            json={"reason": reason},
            headers=_auth_headers(admin),
        )
        assert override.status_code == 200, override.text
        assert override.json()["status"] == "overridden"

    # Satisfy the remaining blocking gates (editorial + detectors)
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
    resolve_response = await client.post(
        f"/api/v1/editor/tasks/{task_response.json()['id']}/resolve",
        json={
            "status": "resolved",
            "resolution_notes": "Final read complete.",
            "minutes_spent": 5,
        },
        headers=_auth_headers(editor),
    )
    assert resolve_response.status_code == 200
    for gate_key, name in (
        ("plagiarism_proxy", "Plagiarism Proxy"),
        ("ai_detection_proxy", "GPTZero"),
    ):
        detector_response = await client.post(
            f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
            f"{gate_key}/detector-result",
            json={
                "detector_name": name,
                "result_percent": 5.0,
                "threshold_percent": 15.0,
                "checked_at": datetime.utcnow().isoformat(),
                "report_ref": "docs/phase1-runs/RUN-001.md",
                "reason": "External detector proxy report attached.",
            },
            headers=_auth_headers(admin),
        )
        assert detector_response.status_code == 200

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Released after audited overrides."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 200, release_response.text
    assert release_response.json()["release_status"] == "released"


@pytest.mark.asyncio
async def test_claim_support_warning_when_zero_claims_extracted(client):
    """A claim_check_summary with total_claims=0 must show 'warning', not
    'passed' — the audit ran but had nothing to verify, which for a
    finished thesis means the citations were not recognised."""
    admin = await _create_user(
        email="prod-admin-claims0@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-claims0@example.com")

    doc = await _create_document(int(customer.id), completed=True)
    await _add_event(
        int(doc.id),
        "verification",
        "claim_check_summary",
        {"total_claims": 0, "checked": 0, "counts": {}},
    )
    case = await _create_case(client, admin, doc)
    gate = await _get_gate(client, admin, case["id"], "claim_support")
    assert gate["status"] == "warning"
    assert "manually" in gate["summary"]
