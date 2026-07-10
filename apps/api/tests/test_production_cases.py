"""Phase 2 production case and release gate API coverage."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    ProductionCase,
)
from app.services.generation_contract import generation_contract_sha256
from app.services.storage_service import StorageService
from main import app

TEST_ARTIFACT_SHA256 = "a" * 64


@pytest.fixture(autouse=True)
def _stable_artifact_storage(monkeypatch):
    """Production-case tests use a deterministic stored artifact, not MinIO."""

    async def _get_file_sha256(_self, _path):
        return TEST_ARTIFACT_SHA256

    monkeypatch.setattr(StorageService, "get_file_sha256", _get_file_sha256)


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
            docx_sha256=TEST_ARTIFACT_SHA256 if completed else None,
            content="Generated thesis content." if completed else None,
            completed_at=datetime.utcnow() if completed else None,
            additional_requirements="Extracted UNIBO methodology requirements.",
            requirements_file_processed=True,
            citation_style="apa",
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
                    stage="retrieval",
                    event_type="source_pack_built",
                    payload={
                        "pack_size": 18,
                        "mean_on_topic_score": 0.52,
                        "underfilled": False,
                        "bilingual": True,
                    },
                ),
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
    was_completed = document.status == "completed"
    if was_completed:
        # A valid release case must predate generation. Temporarily model that
        # ordering, then attach the completed durable job below.
        async with AsyncSessionLocal() as session:
            stored_document = await session.get(Document, document.id)
            assert stored_document is not None
            stored_document.status = "draft"
            stored_document.completed_at = None
            await session.commit()

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
    body = response.json()

    if was_completed:
        async with AsyncSessionLocal() as session:
            stored_document = await session.get(Document, document.id)
            stored_case = await session.get(ProductionCase, body["id"])
            assert stored_document is not None
            assert stored_case is not None
            run_requirements = stored_case.requirements_text
            contract_sha256 = generation_contract_sha256(
                stored_document,
                stored_case,
                run_requirements,
            )
            completed_at = datetime.utcnow()
            session.add(
                AIGenerationJob(
                    user_id=stored_document.user_id,
                    document_id=stored_document.id,
                    job_type="full_document",
                    status="completed",
                    progress=100,
                    success=True,
                    request_payload={
                        "additional_requirements": run_requirements,
                        "generation_contract_sha256": contract_sha256,
                        "superseded_artifact_paths": [],
                    },
                    completed_at=completed_at,
                )
            )
            stored_document.status = "completed"
            stored_document.completed_at = completed_at
            await session.commit()
        document.status = "completed"
        document.completed_at = completed_at

        refreshed = await client.get(
            f"/api/v1/admin/production-cases/{body['id']}",
            headers=_auth_headers(admin),
        )
        assert refreshed.status_code == 200, refreshed.text
        body = refreshed.json()

    return body


@pytest.mark.asyncio
async def test_case_creation_is_rejected_after_generation_wins_document_lock(client):
    """A racing case must not be saved after a job that omitted its requirements."""
    admin = await _create_user(
        email="prod-admin-case-race@example.com",
        is_admin=True,
        is_super_admin=True,
    )
    customer = await _create_user(email="prod-client-case-race@example.com")
    document = await _create_document(int(customer.id))

    async with AsyncSessionLocal() as session:
        locked_document = await session.get(Document, document.id)
        assert locked_document is not None
        locked_document.status = "generating"
        session.add(
            AIGenerationJob(
                user_id=customer.id,
                document_id=document.id,
                job_type="full_document",
                status="queued",
            )
        )
        await session.commit()

    response = await client.post(
        "/api/v1/admin/production-cases",
        json={
            "document_id": document.id,
            "manager_id": admin.id,
            "citation_style": "apa",
            "requirements_text": "These requirements arrived in the losing race.",
        },
        headers=_auth_headers(admin),
    )

    assert response.status_code == 409
    assert "requirements would not be included" in response.json()["detail"]
    async with AsyncSessionLocal() as session:
        saved_case = (
            await session.execute(
                select(ProductionCase).where(ProductionCase.document_id == document.id)
            )
        ).scalar_one_or_none()
    assert saved_case is None


@pytest.mark.asyncio
async def test_case_requirements_cannot_be_attached_after_artifact_completion(client):
    admin = await _create_user(
        email="prod-admin-late-case@example.com",
        is_admin=True,
        is_super_admin=True,
    )
    customer = await _create_user(email="prod-client-late-case@example.com")
    document = await _create_document(int(customer.id), completed=True)

    response = await client.post(
        "/api/v1/admin/production-cases",
        json={
            "document_id": document.id,
            "citation_style": "apa",
            "requirements_text": "Requirements arriving after generation.",
        },
        headers=_auth_headers(admin),
    )

    assert response.status_code == 409
    assert "cannot be attached after generation" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_case_starts_with_blocking_no_data_release_gates(client):
    admin = await _create_user(
        email="prod-admin-1@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-1@example.com")
    document = await _create_document(int(customer.id), completed=True)

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
        "generation_contract",
        "citation_verification",
        "claim_support",
        "section_quality",
        "plagiarism_proxy",
        "ai_detection_proxy",
        "editorial_review",
        "delivery_package",
        "source_availability",
    }
    statuses = {gate["gate_key"]: gate["status"] for gate in gates}
    assert statuses["delivery_package"] == "passed"
    assert statuses["generation_contract"] == "passed"
    assert all(
        gate_status == "no_data"
        for gate_key, gate_status in statuses.items()
        if gate_key not in {"delivery_package", "generation_contract"}
    )

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
async def test_new_editor_task_invalidates_old_editorial_override(client):
    admin = await _create_user(
        email="prod-admin-stale-editorial@example.com",
        is_admin=True,
        is_super_admin=True,
    )
    customer = await _create_user(email="prod-client-stale-editorial@example.com")
    editor = await _create_user(email="prod-editor-stale-editorial@example.com")
    document = await _create_document(int(customer.id))
    case = await _create_case(client, admin, document)

    override = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "editorial_review/override",
        json={"reason": "Earlier manual editorial review was accepted."},
        headers=_auth_headers(admin),
    )
    assert override.status_code == 200, override.text
    assert override.json()["status"] == "overridden"

    task = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/editor-tasks",
        json={
            "production_case_id": case["id"],
            "assigned_editor_id": editor.id,
            "source_gate": "editorial_review",
            "title": "New critical issue after the earlier override",
        },
        headers=_auth_headers(admin),
    )
    assert task.status_code == 200, task.text

    gate = await _get_gate(client, admin, int(case["id"]), "editorial_review")
    assert gate["status"] == "failed"
    assert gate["override_reason"] is None


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
            "detector_name": "Compilatio",
            "result_percent": 18.2,
            "decision": "failed",
            "artifact_format": "docx",
            "checked_at": datetime.utcnow().isoformat(),
            "report_ref": "docs/phase1-runs/RUN-001.md",
            "reason": "External plagiarism proxy report for the Phase 1 run.",
        },
        headers=_auth_headers(admin),
    )
    assert failed_response.status_code == 200, failed_response.text
    failed_gate = failed_response.json()
    assert failed_gate["status"] == "failed"
    assert failed_gate["evidence"]["detector_name"] == "Compilatio"
    assert failed_gate["evidence"]["decision"] == "failed"
    assert failed_gate["evidence"]["artifact_format"] == "docx"
    assert failed_gate["evidence"]["artifact_identifier"].startswith(
        f"document-{document.id}-docx-"
    )
    assert len(failed_gate["evidence"]["artifact_fingerprint_sha256"]) == 64
    assert failed_gate["evidence"]["binding_status"] == "current"
    assert "threshold_percent" not in failed_gate["evidence"]

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Attempt with failed detector result."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 409
    assert "plagiarism_proxy" in release_response.json()["detail"]["blockers"]


@pytest.mark.asyncio
async def test_detector_decision_is_bound_to_current_server_artifact(client):
    admin = await _create_user(
        email="prod-admin-artifact-binding@example.com",
        is_admin=True,
        is_super_admin=True,
    )
    customer = await _create_user(email="prod-client-artifact-binding@example.com")
    document = await _create_document(int(customer.id), completed=True)
    case = await _create_case(client, admin, document)
    current_binding = case["document"]["artifact_bindings"]["docx"]
    assert current_binding["identifier"].startswith(f"document-{document.id}-docx-")
    assert len(current_binding["fingerprint_sha256"]) == 64

    response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "ai_detection_proxy/detector-result",
        json={
            "detector_name": "Compilatio",
            "result_percent": 99.0,
            "decision": "passed",
            "artifact_format": "docx",
            "checked_at": datetime.utcnow().isoformat(),
            "report_ref": "docs/phase1-runs/RUN-ARTIFACT.md",
            "reason": "Release manager reviewed the report and accepted this artifact.",
        },
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200, response.text
    gate = response.json()
    assert gate["status"] == "passed"
    recorded_identifier = gate["evidence"]["artifact_identifier"]
    assert gate["evidence"]["decision_by_id"] == admin.id

    async with AsyncSessionLocal() as session:
        current_document = await session.get(Document, document.id)
        assert current_document is not None
        current_document.content = "A newly generated artifact with different content."
        current_document.docx_path = "/exports/agency-thesis-v2.docx"
        current_document.docx_sha256 = "b" * 64
        await session.commit()

    stale_gate = await _get_gate(client, admin, int(case["id"]), "ai_detection_proxy")
    assert stale_gate["status"] == "no_data"
    assert stale_gate["evidence"]["binding_status"] == "stale"
    assert stale_gate["evidence"]["artifact_identifier"] == recorded_identifier
    assert stale_gate["evidence"]["current_artifact_identifier"] != recorded_identifier


@pytest.mark.asyncio
async def test_detector_rejects_file_replaced_under_same_path(client, monkeypatch):
    admin = await _create_user(
        email="prod-admin-mutated-artifact@example.com",
        is_admin=True,
        is_super_admin=True,
    )
    customer = await _create_user(email="prod-client-mutated-artifact@example.com")
    document = await _create_document(int(customer.id), completed=True)
    case = await _create_case(client, admin, document)

    async def _mutated_sha256(_self, _path):
        return "f" * 64

    monkeypatch.setattr(StorageService, "get_file_sha256", _mutated_sha256)
    response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "ai_detection_proxy/detector-result",
        json={
            "detector_name": "Compilatio",
            "result_percent": 5.0,
            "decision": "passed",
            "artifact_format": "docx",
            "checked_at": datetime.utcnow().isoformat(),
            "report_ref": "docs/phase1-runs/RUN-MUTATED.md",
            "reason": "Release manager reviewed the external report.",
        },
        headers=_auth_headers(admin),
    )
    assert response.status_code == 409
    assert "stored artifact bytes" in response.json()["detail"]


@pytest.mark.asyncio
async def test_detector_contract_rejects_caller_controlled_threshold(client):
    admin = await _create_user(
        email="prod-admin-detector-contract@example.com",
        is_admin=True,
        is_super_admin=True,
    )
    customer = await _create_user(email="prod-client-detector-contract@example.com")
    document = await _create_document(int(customer.id), completed=True)
    case = await _create_case(client, admin, document)

    diagnostic_only_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "ai_detection_proxy/detector-result",
        json={
            "detector_name": "GPTZero",
            "result_percent": 2.0,
            "decision": "passed",
            "artifact_format": "docx",
            "checked_at": datetime.utcnow().isoformat(),
            "report_ref": "docs/phase1-runs/RUN-DIAGNOSTIC.md",
            "reason": "Diagnostic score must not authorize an Italian release.",
        },
        headers=_auth_headers(admin),
    )
    assert diagnostic_only_response.status_code == 409
    assert "diagnostic only" in diagnostic_only_response.json()["detail"]

    response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "ai_detection_proxy/detector-result",
        json={
            "detector_name": "Compilatio",
            "result_percent": 24.0,
            "threshold_percent": 35.0,
            "decision": "passed",
            "artifact_format": "docx",
            "checked_at": datetime.utcnow().isoformat(),
            "report_ref": "docs/phase1-runs/RUN-THRESHOLD.md",
            "reason": "Release manager explicitly reviewed the detector report.",
        },
        headers=_auth_headers(admin),
    )
    assert response.status_code == 422

    missing_artifact_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "ai_detection_proxy/detector-result",
        json={
            "detector_name": "Compilatio",
            "result_percent": 24.0,
            "decision": "passed",
            "artifact_format": "pdf",
            "checked_at": datetime.utcnow().isoformat(),
            "report_ref": "docs/phase1-runs/RUN-NO-PDF.md",
            "reason": "Release manager explicitly reviewed the detector report.",
        },
        headers=_auth_headers(admin),
    )
    assert missing_artifact_response.status_code == 409


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
            "detector_name": "Compilatio",
            "result_percent": 8.4,
            "decision": "passed",
            "artifact_format": "docx",
        },
        "ai_detection_proxy": {
            "detector_name": "Compilatio",
            "result_percent": 22.0,
            "decision": "passed",
            "artifact_format": "docx",
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


@pytest.mark.asyncio
async def test_release_requires_both_detector_decisions_on_same_artifact(client):
    admin = await _create_user(
        email="prod-admin-one-artifact@example.com",
        is_admin=True,
        is_super_admin=True,
    )
    customer = await _create_user(email="prod-client-one-artifact@example.com")
    document = await _create_document(int(customer.id), completed=True)
    async with AsyncSessionLocal() as session:
        stored_document = await session.get(Document, document.id)
        assert stored_document is not None
        stored_document.pdf_path = "/exports/agency-thesis.pdf"
        stored_document.pdf_sha256 = TEST_ARTIFACT_SHA256
        await session.commit()
    await _add_provenance(int(document.id))
    case = await _create_case(client, admin, document)

    editorial_override = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "editorial_review/override",
        json={"reason": "Final editorial review was completed and recorded."},
        headers=_auth_headers(admin),
    )
    assert editorial_override.status_code == 200, editorial_override.text

    for gate_key, artifact_format in (
        ("plagiarism_proxy", "docx"),
        ("ai_detection_proxy", "pdf"),
    ):
        response = await client.post(
            f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
            f"{gate_key}/detector-result",
            json={
                "detector_name": "Compilatio",
                "result_percent": 5.0,
                "decision": "passed",
                "artifact_format": artifact_format,
                "checked_at": datetime.utcnow().isoformat(),
                "report_ref": "docs/phase1-runs/RUN-ONE-ARTIFACT.md",
                "reason": "External report is bound to this exact artifact.",
            },
            headers=_auth_headers(admin),
        )
        assert response.status_code == 200, response.text

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Must not release mixed detector artifacts."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 409
    assert "same delivery artifact" in release_response.json()["detail"]


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
    # Healthy source base so source_availability is not among the blockers.
    await _add_event(
        int(document.id),
        "retrieval",
        "source_pack_built",
        {"pack_size": 20, "underfilled": False, "bilingual": False},
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
        ("plagiarism_proxy", "Compilatio"),
        ("ai_detection_proxy", "Compilatio"),
    ):
        detector_response = await client.post(
            f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
            f"{gate_key}/detector-result",
            json={
                "detector_name": name,
                "result_percent": 5.0,
                "decision": "passed",
                "artifact_format": "docx",
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


@pytest.mark.asyncio
async def test_source_availability_gate_passed_and_warning_and_failed(client):
    """The honest source-base gate (doc-8 fix): underfilled pack -> warning,
    empty pack -> failed, healthy pack -> passed. The relaxed threshold must
    face the manager, not hide in a log."""
    admin = await _create_user(
        email="prod-admin-src1@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-src1@example.com")

    # Healthy pack -> passed.
    healthy_doc = await _create_document(int(customer.id), completed=True)
    await _add_event(
        int(healthy_doc.id),
        "retrieval",
        "source_pack_built",
        {"pack_size": 18, "underfilled": False, "bilingual": True},
    )
    healthy_case = await _create_case(client, admin, healthy_doc)
    gate = await _get_gate(client, admin, healthy_case["id"], "source_availability")
    assert gate["status"] == "passed"
    assert "18" in gate["summary"]
    assert gate["blocking"] is True
    assert gate["override_allowed"] is True

    # Underfilled pack (threshold silently relaxed) -> warning.
    thin_doc = await _create_document(int(customer.id), completed=True)
    await _add_event(
        int(thin_doc.id),
        "retrieval",
        "source_pack_built",
        {"pack_size": 5, "underfilled": True, "bilingual": True},
    )
    thin_case = await _create_case(client, admin, thin_doc)
    gate = await _get_gate(client, admin, thin_case["id"], "source_availability")
    assert gate["status"] == "warning"
    assert "relaxed" in gate["summary"]
    assert gate["evidence"]["underfilled"] is True

    # Empty pack -> failed (generation ran closed-book).
    empty_doc = await _create_document(int(customer.id), completed=True)
    await _add_event(
        int(empty_doc.id),
        "retrieval",
        "source_pack_built",
        {"pack_size": 0, "underfilled": True, "bilingual": False},
    )
    empty_case = await _create_case(client, admin, empty_doc)
    gate = await _get_gate(client, admin, empty_case["id"], "source_availability")
    assert gate["status"] == "failed"
    assert "closed-book" in gate["summary"]


@pytest.mark.asyncio
async def test_source_availability_gate_prefers_rebuilt_event_and_blocks_release(
    client,
):
    """The post-outline rebuild is what sections actually cite, so it wins over
    the initial build; a warning-state gate blocks release until overridden."""
    admin = await _create_user(
        email="prod-admin-src2@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-src2@example.com")
    document = await _create_document(int(customer.id), completed=True)

    # Initial build was healthy, but the rebuild (what sections cite) was thin.
    await _add_event(
        int(document.id),
        "retrieval",
        "source_pack_built",
        {"pack_size": 20, "underfilled": False, "bilingual": True},
    )
    await _add_event(
        int(document.id),
        "retrieval",
        "source_pack_rebuilt",
        {"pack_size": 4, "underfilled": True, "bilingual": True},
    )
    case = await _create_case(client, admin, document)

    gate = await _get_gate(client, admin, case["id"], "source_availability")
    assert gate["status"] == "warning"
    assert gate["evidence"]["pack_size"] == 4

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Attempt with thin source base."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 409
    assert "source_availability" in release_response.json()["detail"]["blockers"]

    # The audited override is the resolution path.
    override = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release-gates/"
        "source_availability/override",
        json={"reason": "Manager reviewed the 4 pack sources manually."},
        headers=_auth_headers(admin),
    )
    assert override.status_code == 200, override.text
    assert override.json()["status"] == "overridden"
    assert override.json()["gate_key"] == "source_availability"


@pytest.mark.asyncio
async def test_source_availability_gate_no_data_blocks_release(client):
    """No source-pack event (grounding off / legacy document) -> no_data, which
    blocks release until an audited override — consistent with the other gates."""
    admin = await _create_user(
        email="prod-admin-src3@example.com", is_admin=True, is_super_admin=True
    )
    customer = await _create_user(email="prod-client-src3@example.com")
    document = await _create_document(int(customer.id), completed=True)
    case = await _create_case(client, admin, document)

    gate = await _get_gate(client, admin, case["id"], "source_availability")
    assert gate["status"] == "no_data"

    release_response = await client.post(
        f"/api/v1/admin/production-cases/{case['id']}/release",
        json={"notes": "Attempt without source-pack evidence."},
        headers=_auth_headers(admin),
    )
    assert release_response.status_code == 409
    assert "source_availability" in release_response.json()["detail"]["blockers"]
