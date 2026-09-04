"""Exercise actual gateway auth, tenant boundaries and durable paid enqueue."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.auth import User
from app.models.document import AIGenerationJob, Document, DocumentProvenance
from app.models.operator_bot import OperatorBotAction, OperatorSupportRequest
from main import app

ROOT = "/api/v1/operator-bot"
SECRET = "operator-only-test-credential-1234567890"


@pytest.fixture
async def setup_bot(db_session, monkeypatch):
    first = User(email="operator@test.example", is_active=True)
    other = User(email="other@test.example", is_active=True)
    db_session.add_all([first, other])
    await db_session.flush()
    docs = [
        Document(
            user_id=u.id,
            title="Bot test",
            topic="Artificial intelligence in higher education",
            language="it",
            target_pages=10,
            status="draft",
            work_type="essay",
            citation_style="apa",
        )
        for u in (first, other)
    ]
    db_session.add_all(docs)
    await db_session.commit()
    monkeypatch.setattr(settings, "OPERATOR_BOT_SECRET", SECRET)
    monkeypatch.setattr(
        settings, "OPERATOR_BOT_USERS", {"12345": first.id, "67890": other.id}
    )
    monkeypatch.setattr(settings, "UNLIMITED_GENERATION_USER_IDS", [first.id])
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_DAILY_USER_LIMIT", 0)
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", 0)
    monkeypatch.setattr(settings, "GLOBAL_DAILY_TOKEN_LIMIT", 0)
    monkeypatch.setattr(settings, "METHODOLOGY_REQUIRED_FOR_GENERATION", False)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 50)
    return first.id, other.id, docs[0].id, docs[1].id


@pytest.fixture
async def client():
    async with AsyncClient(
        app=app,
        base_url="http://test",
        headers={
            "X-Operator-Bot-Key": SECRET,
            "X-Telegram-User-Id": "12345",
            "X-CSRF-Token": "operator-test-csrf-header",
        },
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_gateway_fails_closed_and_no_admin_authority(
    client, setup_bot, monkeypatch
):
    assert (await client.get(ROOT + "/me")).status_code == 200
    assert (
        await client.get(ROOT + "/me", headers={"X-Telegram-User-Id": "999"})
    ).status_code == 403
    assert (
        await client.get(ROOT + "/me", headers={"X-Operator-Bot-Key": "wrong"})
    ).status_code == 401
    # The service key is not a JWT and cannot reach normal user/admin APIs.
    assert (await client.get("/api/v1/documents/")).status_code == 401
    monkeypatch.setattr(settings, "OPERATOR_BOT_SECRET", None)
    assert (await client.get(ROOT + "/me")).status_code == 401


@pytest.mark.asyncio
async def test_ownership_all_read_and_write_paths(client, setup_bot):
    _, _, own, other = setup_bot
    assert [
        d["id"] for d in (await client.get(ROOT + "/documents")).json()["documents"]
    ] == [own]
    assert (await client.get(f"{ROOT}/documents/{other}")).status_code == 404
    assert (
        await client.post(f"{ROOT}/documents/{other}/prepare", json={})
    ).status_code == 404
    assert (
        await client.post(
            ROOT + "/support-requests",
            json={
                "request_id": "a" * 32,
                "document_id": other,
                "summary": "Investigate failure",
            },
        )
    ).status_code == 404
    assert (
        await client.post(f"{ROOT}/documents/{own}/prepare", json={"user_id": 2})
    ).status_code == 422


@pytest.mark.asyncio
async def test_confirm_unlimited_exactly_once_even_after_job_finishes(
    client, setup_bot
):
    _, _, doc_id, _ = setup_bot
    prepared = await client.post(f"{ROOT}/documents/{doc_id}/prepare", json={})
    assert prepared.status_code == 200, prepared.text
    action_id = prepared.json()["action_id"]
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(AIGenerationJob.id)))).scalar() == 0
    result = await client.post(f"{ROOT}/actions/{action_id}/confirm", json={})
    assert result.status_code == 200, result.text
    job_id = result.json()["job_id"]
    async with AsyncSessionLocal() as db:
        job = await db.get(AIGenerationJob, job_id)
        job.status = "failed"
        doc = await db.get(Document, doc_id)
        doc.status = "failed"
        await db.commit()
    again = await client.post(f"{ROOT}/actions/{action_id}/confirm", json={})
    assert again.status_code == 200
    assert again.json()["job_id"] == job_id
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(AIGenerationJob.id)))).scalar() == 1
        action = await db.get(OperatorBotAction, action_id)
        assert action.result["job_id"] == job_id
        events = (
            (
                await db.execute(
                    select(DocumentProvenance).where(
                        DocumentProvenance.event_type == "task_contract_confirmed"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1 and events[0].payload["channel"] == "telegram"


@pytest.mark.asyncio
async def test_stale_or_cross_user_confirmation_never_runs(client, setup_bot):
    _, _, doc_id, _ = setup_bot
    prepared = (await client.post(f"{ROOT}/documents/{doc_id}/prepare", json={})).json()
    path = f"{ROOT}/actions/{prepared['action_id']}/confirm"
    assert (
        await client.post(path, json={}, headers={"X-Telegram-User-Id": "67890"})
    ).status_code == 404
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        doc.target_pages = 20
        await db.commit()
    assert (await client.post(path, json={})).status_code == 409
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(AIGenerationJob.id)))).scalar() == 0


@pytest.mark.asyncio
async def test_expired_and_revoked_access(client, setup_bot):
    uid, _, doc_id, _ = setup_bot
    prepared = (await client.post(f"{ROOT}/documents/{doc_id}/prepare", json={})).json()
    path = f"{ROOT}/actions/{prepared['action_id']}/confirm"
    async with AsyncSessionLocal() as db:
        action = await db.get(OperatorBotAction, prepared["action_id"])
        action.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    assert (await client.post(path, json={})).status_code == 409
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uid)
        user.is_active = False
        await db.commit()
    assert (await client.get(ROOT + "/me")).status_code == 403
    assert (await client.post(path, json={})).status_code == 403


@pytest.mark.asyncio
async def test_non_exempt_user_keeps_quota(client, setup_bot):
    _, _, _, other = setup_bot
    headers = {"X-Telegram-User-Id": "67890"}
    result = await client.post(
        f"{ROOT}/documents/{other}/prepare", json={}, headers=headers
    )
    action = result.json()["action_id"]
    result = await client.post(
        f"{ROOT}/actions/{action}/confirm", json={}, headers=headers
    )
    assert result.status_code == 429, result.text
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(AIGenerationJob.id)))).scalar() == 0
        assert (await db.get(Document, other)).contract_confirmed_sha256 is None


@pytest.mark.asyncio
async def test_unlimited_does_not_bypass_scope_or_quality(client, setup_bot):
    _, _, doc_id, _ = setup_bot
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        doc.target_pages = 100
        await db.commit()
    action = (await client.post(f"{ROOT}/documents/{doc_id}/prepare", json={})).json()[
        "action_id"
    ]
    response = await client.post(f"{ROOT}/actions/{action}/confirm", json={})
    assert response.status_code == 400
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        doc.target_pages = 10
        doc.citation_style = "unsupported"
        await db.commit()
    action = (await client.post(f"{ROOT}/documents/{doc_id}/prepare", json={})).json()[
        "action_id"
    ]
    assert (
        await client.post(f"{ROOT}/actions/{action}/confirm", json={})
    ).status_code == 409


@pytest.mark.asyncio
async def test_support_request_idempotent_and_diagnostic_redacted(client, setup_bot):
    uid, _, doc_id, _ = setup_bot
    async with AsyncSessionLocal() as db:
        db.add(
            AIGenerationJob(
                user_id=uid,
                document_id=doc_id,
                job_type="full_document",
                status="failed",
                error_message="grounding 0.2 < 0.8 token=secret-value https://host/file?signature=secret",
            )
        )
        await db.commit()
    payload = {
        "request_id": "b" * 32,
        "document_id": doc_id,
        "summary": "Please investigate grounding",
    }
    first = await client.post(ROOT + "/support-requests", json=payload)
    assert first.status_code == 200
    assert (
        await client.post(ROOT + "/support-requests", json=payload)
    ).status_code == 200
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(OperatorSupportRequest))).scalars().all()
        assert len(rows) == 1
        assert "secret" not in rows[0].evidence["job"]["error"]
    response = await client.post(f"{ROOT}/documents/{doc_id}/prepare", json={})
    assert response.status_code == 409  # Cannot silently rerun the same failure.


@pytest.mark.asyncio
async def test_proposal_is_preserved_without_granting_write_or_other_user_access(
    client, setup_bot
):
    _, _, doc_id, _ = setup_bot
    response = await client.post(
        ROOT + "/support-requests",
        json={
            "request_id": "c" * 32,
            "document_id": doc_id,
            "summary": "Proposed targeted correction",
            "proposed_changes": [
                {
                    "path": "apps/api/app/example.py",
                    "source_sha256": "a" * 64,
                    "patch": "--- a/example.py\n+++ b/example.py\n@@ -1 +1 @@\n-old\n+new\n",
                }
            ],
        },
    )
    assert response.status_code == 200 and response.json()["has_code_proposal"]
    async with AsyncSessionLocal() as db:
        row = await db.get(OperatorSupportRequest, "c" * 32)
        assert row.evidence["code_proposal"]["validation"] == "not_applied_or_tested"
    own = await client.get(ROOT + "/support-requests")
    assert len(own.json()["requests"]) == 1
    other = await client.get(
        ROOT + "/support-requests", headers={"X-Telegram-User-Id": "67890"}
    )
    assert not other.json()["requests"]


@pytest.mark.asyncio
async def test_job_status_requires_both_job_and_document_ownership(client, setup_bot):
    uid, other_uid, doc_id, other_id = setup_bot
    async with AsyncSessionLocal() as db:
        job = AIGenerationJob(
            user_id=other_uid,
            document_id=other_id,
            job_type="full_document",
            status="failed",
        )
        db.add(job)
        await db.commit()
        job_id = job.id
    assert (await client.get(f"{ROOT}/jobs/{job_id}")).status_code == 404
    assert (
        await client.get(
            f"{ROOT}/jobs/{job_id}", headers={"X-Telegram-User-Id": "67890"}
        )
    ).status_code == 200
