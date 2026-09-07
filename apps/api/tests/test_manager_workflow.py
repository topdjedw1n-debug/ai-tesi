"""M0-05: durable, owner-scoped manager state and release semantics."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.document import AIGenerationJob, DocumentProvenance
from app.services.release_policy import REVIEW_EVENT
from tests import test_release_evidence as evidence_fixtures
from tests.test_production_cases import (
    _auth_headers,
    _create_case,
    _create_document,
    _create_user,
)
from tests.test_release_evidence import (
    BASE,
    make_work,
    ready,
    release,
)

client = evidence_fixtures.client
_stable_artifact_storage = evidence_fixtures._stable_artifact_storage

pytestmark = pytest.mark.asyncio


async def test_document_links_to_its_existing_production_case(client):
    owner = await _create_user(
        email=f"m005-{uuid4().hex}", is_admin=True, is_super_admin=True
    )
    document = await _create_document(int(owner.id), completed=False)
    case = await _create_case(client, owner, document)
    response = await client.get(
        f"/api/v1/documents/{document.id}", headers=_auth_headers(owner)
    )
    assert response.status_code == 200, response.text
    assert response.json()["production_case_id"] == case["id"]


async def test_latest_job_status_survives_reload_and_excludes_foreign_work(client):
    owner = await _create_user(email=f"m005-{uuid4().hex}")
    stranger = await _create_user(email=f"m005-{uuid4().hex}")
    document = await _create_document(int(owner.id), completed=False)
    url = f"/api/v1/jobs/document/{document.id}/status"
    empty = await client.get(url, headers=_auth_headers(owner))
    assert empty.status_code == 200 and empty.json() is None
    async with AsyncSessionLocal() as db:
        db.add(
            AIGenerationJob(
                user_id=owner.id,
                document_id=document.id,
                job_type="full_document",
                status="failed",
                progress=12,
            )
        )
        await db.flush()
        active = AIGenerationJob(
            user_id=owner.id,
            document_id=document.id,
            job_type="full_document",
            status="queued",
            progress=47,
            error_message="Source retrieval providers were unavailable",
            attempt_count=1,
            max_attempts=3,
        )
        db.add(active)
        await db.flush()
        active_id = int(active.id)
        # A newer section job must not replace the full-document progress.
        db.add(
            AIGenerationJob(
                user_id=owner.id,
                document_id=document.id,
                job_type="section_generation",
                status="completed",
                progress=100,
            )
        )
        await db.commit()
    for _ in range(2):
        response = await client.get(url, headers=_auth_headers(owner))
        assert response.status_code == 200, response.text
        assert response.json()["job_id"] == active_id
        assert response.json()["status"] == "queued"
        assert response.json()["progress"] == 47
        assert response.json()["attempt_count"] == 1
        assert "unavailable" in response.json()["error_message"]
    assert (await client.get(url, headers=_auth_headers(stranger))).status_code == 404


async def test_release_means_file_ready_for_manager_not_client_handoff(
    client, monkeypatch, _stable_artifact_storage
):
    work = await make_work(client, monkeypatch, _stable_artifact_storage)
    await ready(client, work)
    response = await release(client, work)
    assert response.status_code == 200, response.text
    assert response.json()["release_status"] == "released"
    assert response.json()["delivery_status"] == "ready"
    assert response.json()["qa_status"] == "passed"
    owner, _, case = work
    rejected = await client.post(
        f"{BASE}/{case['id']}/content-review",
        headers=_auth_headers(owner),
        json={
            "artifact_fingerprint_sha256": case["document"]["artifact_bindings"][
                "docx"
            ]["fingerprint_sha256"],
            "decision": "rejected",
            "reason": "The rendered document does not meet the agreed requirements.",
        },
    )
    assert rejected.status_code == 200, rejected.text
    updated = await client.get(f"{BASE}/{case['id']}", headers=_auth_headers(owner))
    assert updated.json()["qa_status"] == "needs_review"
    assert updated.json()["release_status"] == "blocked"


async def test_rendered_docx_page_review_is_preserved_with_its_artifact(
    client, monkeypatch, _stable_artifact_storage
):
    owner, document, case = await make_work(
        client, monkeypatch, _stable_artifact_storage
    )
    fingerprint = case["document"]["artifact_bindings"]["docx"]["fingerprint_sha256"]
    response = await client.post(
        f"{BASE}/{case['id']}/content-review",
        headers=_auth_headers(owner),
        json={
            "artifact_fingerprint_sha256": fingerprint,
            "decision": "accepted",
            "reviewed_page_count": 18,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["evidence"]["reviewed_page_count"] == 18
    async with AsyncSessionLocal() as db:
        event = (
            await db.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.document_id == document.id,
                    DocumentProvenance.event_type == REVIEW_EVENT,
                )
            )
        ).scalar_one()
        assert event.payload["reviewed_page_count"] == 18
        assert event.payload["artifact_fingerprint_sha256"] == fingerprint


@pytest.mark.parametrize("page_count", [None, 0, 1.5, 1001])
async def test_acceptance_requires_a_valid_rendered_page_count(
    client, monkeypatch, _stable_artifact_storage, page_count
):
    owner, _, case = await make_work(client, monkeypatch, _stable_artifact_storage)
    response = await client.post(
        f"{BASE}/{case['id']}/content-review",
        headers=_auth_headers(owner),
        json={
            "artifact_fingerprint_sha256": case["document"]["artifact_bindings"][
                "docx"
            ]["fingerprint_sha256"],
            "decision": "accepted",
            "reviewed_page_count": page_count,
        },
    )
    assert response.status_code == 422, response.text
