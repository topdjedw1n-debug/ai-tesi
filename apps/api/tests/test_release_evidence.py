"""M0-03: exact-DOCX evidence, hard thresholds and durable manager review."""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.core.database import AsyncSessionLocal, get_engine
from app.models.document import (
    Document,
    DocumentProvenance,
    ProductionCase,
    ReleaseGateResult,
)
from app.services.release_policy import MAX_REPORT_BYTES, REVIEW_EVENT
from app.services.storage_service import StorageService
from tests import test_production_cases as case_fixtures
from tests.test_production_cases import (
    _accept_review,
    _add_provenance,
    _auth_headers,
    _create_case,
    _create_document,
    _create_user,
    _get_gate,
    _report_payload,
)

_stable_artifact_storage = case_fixtures._stable_artifact_storage
client = case_fixtures.client

pytestmark = pytest.mark.asyncio
BASE = "/api/v1/admin/production-cases"
DOCX_BYTES = b"PK\x03\x04 isolated final DOCX bytes for delivery verification"


@pytest.fixture(scope="module", autouse=True)
def enforce_foreign_keys(_isolated_database):
    """Match PostgreSQL cascades; SQLite otherwise leaves orphan cases on delete."""
    engine = get_engine().sync_engine

    def enable(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine, "connect", enable)
    yield
    event.remove(engine, "connect", enable)


@pytest.fixture
async def work(client, monkeypatch, _stable_artifact_storage):
    return await make_work(client, monkeypatch, _stable_artifact_storage)


async def make_work(client, monkeypatch, reports):
    async def digest(_self, path):
        content = reports[path] if "/detector-reports/" in path else DOCX_BYTES
        return hashlib.sha256(content).hexdigest()

    async def download(_self, path):
        return reports[path] if "/detector-reports/" in path else DOCX_BYTES

    monkeypatch.setattr(StorageService, "get_file_sha256", digest)
    monkeypatch.setattr(StorageService, "download_file", download)
    monkeypatch.setattr(
        StorageService, "get_file_size", AsyncMock(return_value=len(DOCX_BYTES))
    )
    admin = await _create_user(
        email=f"m003-{uuid4().hex}@example.com", is_admin=True, is_super_admin=True
    )
    document = await _create_document(int(admin.id), completed=True)
    async with AsyncSessionLocal() as db:
        stored = await db.get(Document, document.id)
        stored.docx_sha256 = hashlib.sha256(DOCX_BYTES).hexdigest()
        stored.title = "Тестова робота — M0-03"
        await db.commit()
    await _add_provenance(int(document.id))
    case = await _create_case(client, admin, document)
    return admin, document, case


async def record(client, work, gate="plagiarism_proxy", percent=10, **changes):
    admin, _, case = work
    evidence = await _report_payload(client, admin, case)
    payload = {
        "detector_name": "Compilatio",
        "result_percent": percent,
        "decision": "passed",
        "artifact_format": "docx",
        "checked_at": datetime.utcnow().isoformat(),
        "reason": "Manager checked this exact DOCX in Compilatio.",
        **evidence,
        **changes,
    }
    return await client.post(
        f"{BASE}/{case['id']}/release-gates/{gate}/detector-result",
        json=payload,
        headers=_auth_headers(admin),
    )


async def ready(client, work):
    admin, _, case = work
    for key in ("plagiarism_proxy", "ai_detection_proxy"):
        response = await record(client, work, gate=key)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "passed"
    assert (await _accept_review(client, admin, case))["status"] == "passed"


async def release(client, work):
    admin, _, case = work
    return await client.post(
        f"{BASE}/{case['id']}/release", json={}, headers=_auth_headers(admin)
    )


@pytest.mark.parametrize("gate", ["plagiarism_proxy", "ai_detection_proxy"])
@pytest.mark.parametrize(
    "percent,expected",
    [
        (0, "passed"),
        (10, "passed"),
        (10.0001, "failed"),
        (22, "failed"),
        (100, "failed"),
    ],
)
async def test_exact_threshold_is_server_enforced(
    client, work, gate, percent, expected
):
    response = await record(client, work, gate=gate, percent=percent)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == expected
    assert response.json()["evidence"]["threshold_percent"] == 10


async def test_operator_may_reject_acceptable_percent(client, work):
    response = await record(client, work, percent=5, decision="failed")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


@pytest.mark.parametrize("percent", [True, "7", None, -1, 101])
async def test_invalid_percent_cannot_be_coerced_into_a_pass(client, work, percent):
    assert (await record(client, work, percent=percent)).status_code == 422


@pytest.mark.parametrize("action", ["document", "account"])
async def test_report_file_is_deleted_with_its_document(
    client, work, monkeypatch, _stable_artifact_storage, action
):
    from app.services.document_service import DocumentService
    from app.services.gdpr_service import GDPRService

    admin, document, case = work
    await _report_payload(client, admin, case)
    report_path = next(iter(_stable_artifact_storage))
    delete_file = AsyncMock(return_value=True)
    monkeypatch.setattr(StorageService, "delete_file", delete_file)
    async with AsyncSessionLocal() as db:
        if action == "document":
            await DocumentService(db).delete_document(int(document.id), int(admin.id))
        else:
            await GDPRService(db).delete_user_account(int(admin.id))
        assert await db.get(Document, document.id) is None
    assert report_path in [call.args[0] for call in delete_file.await_args_list]


async def test_complete_evidence_releases_and_downloads_exact_bytes(client, work):
    admin, document, case = work
    await ready(client, work)
    response = await release(client, work)
    assert response.status_code == 200, response.text
    assert response.json()["released_pdf_path"] is None
    token = await client.post(
        f"/api/v1/documents/{document.id}/export",
        json={"format": "docx"},
        headers=_auth_headers(admin),
    )
    assert token.status_code == 200, token.text
    downloaded = await client.get(token.json()["download_url"])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == DOCX_BYTES
    assert "filename*=UTF-8''" in downloaded.headers["content-disposition"]
    assert (
        hashlib.sha256(downloaded.content).hexdigest()
        == response.json()["released_docx_sha256"]
    )
    reports = await client.get(
        f"{BASE}/{case['id']}/detector-reports", headers=_auth_headers(admin)
    )
    assert len(reports.json()) == 2
    assert all("storage_path" not in report for report in reports.json())
    first = reports.json()[0]
    report_file = await client.get(
        f"{BASE}/{case['id']}/detector-reports/{first['id']}/file",
        headers=_auth_headers(admin),
    )
    assert report_file.status_code == 200
    assert hashlib.sha256(report_file.content).hexdigest() == first["report_sha256"]
    assert report_file.headers["cache-control"] == "no-store"


async def test_no_rewrite_is_required_even_when_every_other_gate_passes(client, work):
    for key in ("plagiarism_proxy", "ai_detection_proxy"):
        assert (await record(client, work, gate=key)).status_code == 200
    response = await release(client, work)
    assert response.status_code == 409
    assert response.json()["detail"]["blockers"] == ["editorial_review"]


async def test_file_swap_after_hashing_cannot_change_downloaded_bytes(
    client, work, monkeypatch
):
    admin, document, _ = work
    await ready(client, work)
    assert (await release(client, work)).status_code == 200
    token = (
        await client.post(
            f"/api/v1/documents/{document.id}/export",
            json={"format": "docx"},
            headers=_auth_headers(admin),
        )
    ).json()["download_url"]
    monkeypatch.setattr(
        StorageService,
        "download_file",
        AsyncMock(return_value=b"substituted bytes after hashing"),
    )
    response = await client.get(token)
    assert response.status_code == 409
    assert "під час завантаження" in response.json()["detail"]


async def test_rewrite_failure_is_durable_and_invalidates_old_download(client, work):
    admin, document, case = work
    await ready(client, work)
    assert (await release(client, work)).status_code == 200
    token = (
        await client.post(
            f"/api/v1/documents/{document.id}/export",
            json={"format": "docx"},
            headers=_auth_headers(admin),
        )
    ).json()["download_url"]
    payload = {
        "artifact_fingerprint_sha256": case["document"]["artifact_bindings"]["docx"][
            "fingerprint_sha256"
        ],
        "decision": "rewritten",
        "reason": "Human content rewrite was needed to make this work usable.",
    }
    response = await client.post(
        f"{BASE}/{case['id']}/content-review",
        json=payload,
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    payload["decision"] = "accepted"
    payload["reviewed_page_count"] = 18
    assert (
        await client.post(
            f"{BASE}/{case['id']}/content-review",
            json=payload,
            headers=_auth_headers(admin),
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"{BASE}/{case['id']}",
            json={"human_minutes_used": 0},
            headers=_auth_headers(admin),
        )
    ).status_code == 200
    assert (await release(client, work)).status_code == 409
    assert (await client.get(token)).status_code == 409
    async with AsyncSessionLocal() as db:
        events = (
            (
                await db.execute(
                    select(DocumentProvenance).where(
                        DocumentProvenance.document_id == document.id,
                        DocumentProvenance.event_type == REVIEW_EVENT,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert [event.payload["decision"] for event in events] == [
            "accepted",
            "rewritten",
        ]
        stored = await db.get(Document, document.id)
        stored.completed_at += timedelta(seconds=1)
        await db.commit()
    assert (await _get_gate(client, admin, case["id"], "editorial_review"))[
        "status"
    ] == "no_data"


async def test_replaced_artifact_rejects_old_open_form_and_report(client, work):
    admin, document, case = work
    evidence = await _report_payload(client, admin, case)
    async with AsyncSessionLocal() as db:
        stored = await db.get(Document, document.id)
        stored.completed_at += timedelta(seconds=1)
        await db.commit()
    response = await client.post(
        f"{BASE}/{case['id']}/content-review",
        json={
            "artifact_fingerprint_sha256": evidence["artifact_fingerprint_sha256"],
            "decision": "accepted",
            "reviewed_page_count": 18,
        },
        headers=_auth_headers(admin),
    )
    assert response.status_code == 409
    assert "DOCX змінився" in response.json()["detail"]
    new_case = (
        await client.get(f"{BASE}/{case['id']}", headers=_auth_headers(admin))
    ).json()
    response = await record(
        client, (admin, document, new_case), report_id=evidence["report_id"]
    )
    assert response.status_code == 409
    assert "попередньої версії" in response.json()["detail"]


@pytest.mark.parametrize(
    "mode", ["missing", "changed", "legacy_pass", "manual_pass", "old_override"]
)
async def test_invalid_evidence_cannot_keep_existing_release(
    client, work, _stable_artifact_storage, mode
):
    admin, document, case = work
    await ready(client, work)
    assert (await release(client, work)).status_code == 200
    token = (
        await client.post(
            f"/api/v1/documents/{document.id}/export",
            json={"format": "docx"},
            headers=_auth_headers(admin),
        )
    ).json()["download_url"]
    if mode in {"missing", "changed"}:
        path = next(iter(_stable_artifact_storage))
        if mode == "missing":
            del _stable_artifact_storage[path]
        else:
            _stable_artifact_storage[path] = b"changed report"
    else:
        async with AsyncSessionLocal() as db:
            gate = (
                await db.execute(
                    select(ReleaseGateResult).where(
                        ReleaseGateResult.production_case_id == case["id"],
                        ReleaseGateResult.gate_key == "plagiarism_proxy",
                    )
                )
            ).scalar_one()
            evidence = dict(gate.evidence)
            if mode == "legacy_pass":
                evidence.pop("policy_version")
            else:
                evidence["result_percent"] = 22
            gate.evidence = evidence
            gate.status = "passed"
            if mode == "old_override":
                gate.override_reason = (
                    "Historic admin exception must not bypass current rules."
                )
            await db.commit()
    assert (await client.get(token)).status_code == 409
    async with AsyncSessionLocal() as db:
        stored_case = await db.get(ProductionCase, case["id"])
        assert stored_case.release_status == "blocked"
        assert stored_case.released_docx_path is None


async def test_foreign_report_and_plain_reference_cannot_authorize(client, work):
    admin, document, case = work
    other = await _create_document(int(admin.id), completed=True)
    async with AsyncSessionLocal() as db:
        stored = await db.get(Document, other.id)
        stored.docx_sha256 = hashlib.sha256(DOCX_BYTES).hexdigest()
        await db.commit()
    other_case = await _create_case(client, admin, other)
    foreign = await _report_payload(client, admin, other_case)
    assert (
        await record(client, work, report_id=foreign["report_id"])
    ).status_code == 409
    assert (
        await record(client, work, report_ref="docs/phase1-runs/RUN-001.md")
    ).status_code == 422
    assert (
        await record(client, work, report_matches_artifact=False)
    ).status_code == 422
    assert (await record(client, work, report_id=999999)).status_code == 409


@pytest.mark.parametrize("format", ["pdf", "txt"])
async def test_non_docx_proof_cannot_authorize_release(client, work, format):
    assert (await record(client, work, artifact_format=format)).status_code == 422
    assert (await release(client, work)).status_code == 409


@pytest.mark.parametrize(
    "content,expected",
    [
        (b"", 413),
        (b"<html>not a report</html>", 415),
        (b"%PDF-" + b"x" * MAX_REPORT_BYTES, 413),
    ],
)
async def test_report_upload_rejects_empty_unsupported_and_oversized_files(
    client, work, content, expected
):
    admin, _, case = work
    response = await client.post(
        f"{BASE}/{case['id']}/detector-reports",
        data={
            "artifact_fingerprint_sha256": case["document"]["artifact_bindings"][
                "docx"
            ]["fingerprint_sha256"]
        },
        files={"file": ("report.pdf", content, "application/pdf")},
        headers=_auth_headers(admin),
    )
    assert response.status_code == expected


async def test_nonfinite_percent_is_invalid_schema():
    from pydantic import ValidationError

    from app.schemas.production import ManualDetectorResultRequest

    for number in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            ManualDetectorResultRequest(
                detector_name="Compilatio",
                result_percent=number,
                decision="passed",
                artifact_format="docx",
                artifact_fingerprint_sha256="a" * 64,
                report_id=1,
                report_matches_artifact=True,
                checked_at=datetime.utcnow(),
                reason="A nonfinite result cannot authorize release.",
            )


async def test_academic_gate_cannot_be_overridden_or_omitted(client, work):
    from sqlalchemy import delete

    admin, document, case = work
    await ready(client, work)
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(DocumentProvenance).where(
                DocumentProvenance.document_id == document.id,
                DocumentProvenance.event_type == "academic_review",
            )
        )
        await db.commit()
    denied = await client.post(
        f"{BASE}/{case['id']}/release-gates/academic_quality/override",
        json={"reason": "Attempt to bypass missing academic review"},
        headers=_auth_headers(admin),
    )
    assert denied.status_code == 400
    response = await release(client, work)
    assert response.status_code == 409
    assert "academic_quality" in response.json()["detail"]["blockers"]
