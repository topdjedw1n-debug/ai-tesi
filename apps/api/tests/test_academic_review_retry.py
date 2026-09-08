"""Review-only remediation: explicit calls, idempotency, staleness and spend."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.auth import User
from app.models.document import AIGenerationJob, Document, DocumentProvenance
from app.services.academic_review import review_binding
from app.services.academic_review_retry import RETRY_STARTED, retry_academic_review
from app.services.source_verification_stage import load_source_pack
from tests import test_production_cases as fixtures
from tests.test_academic_quality import verdict

client = fixtures.client
_stable_artifact_storage = fixtures._stable_artifact_storage


async def seed(client):
    admin = await fixtures._create_user(
        email=f"retry-{uuid4()}@example.com", is_admin=True, is_super_admin=True
    )
    doc = await fixtures._create_document(admin.id, completed=True)
    await fixtures._add_provenance(doc.id)
    case = await fixtures._create_case(client, admin, doc)
    async with AsyncSessionLocal() as db:
        current = await db.get(Document, doc.id)
        current.content = (
            "Comparison of study designs and populations. Results differ by setting."
        )
        current.outline = {"sections": [{"title": f"Chapter {i}"} for i in range(4)]}
        pack = await load_source_pack(db, doc.id)
        job = (
            await db.execute(
                select(AIGenerationJob).where(AIGenerationJob.document_id == doc.id)
            )
        ).scalar_one()
        binding = review_binding(current, job, pack.sha256(), kind="whole")
        db.add_all(
            [
                DocumentProvenance(
                    document_id=doc.id,
                    stage="quality",
                    event_type="academic_review",
                    payload={
                        "binding": binding,
                        "kind": "whole",
                        "status": "unchecked",
                        "reason": "Timeout",
                    },
                ),
                DocumentProvenance(
                    document_id=doc.id,
                    stage="export",
                    event_type="academic_review_artifact",
                    payload={
                        "binding": binding,
                        "docx_sha256": current.docx_sha256,
                        "docx_path": current.docx_path,
                    },
                ),
                DocumentProvenance(
                    document_id=doc.id,
                    stage="retrieval",
                    event_type="source_pack_preflight",
                    payload={
                        "sha256": pack.sha256(),
                        "retrieval_trace": [{"provider": "fixture", "query": "care"}],
                    },
                ),
            ]
        )
        await db.commit()
        original = (current.content, current.docx_path, current.docx_sha256)
    return admin, doc, case, original


@pytest.mark.asyncio
async def test_same_request_is_free_and_content_and_file_do_not_change(
    client, monkeypatch
):
    admin, doc, case, original = await seed(client)
    services = []

    class Reviewer:
        def __init__(self, db, usage_tracker, **kwargs):
            self.usage = usage_tracker
            services.append(self)

        async def call_with_fallback(self, *args, **kwargs):
            async with AsyncSessionLocal() as observer:
                event = (
                    (
                        await observer.execute(
                            select(DocumentProvenance).where(
                                DocumentProvenance.event_type == RETRY_STARTED
                            )
                        )
                    )
                    .scalars()
                    .all()[-1]
                )
                assert event.payload["attempt_id"]
            self.usage.add("openai", "gpt-4", 100, 50)
            return verdict()

    monkeypatch.setattr("app.services.academic_review_retry.AIService", Reviewer)
    request_id = str(uuid4())
    url = f"/api/v1/admin/production-cases/{case['id']}/academic-review/retry"
    response = await client.post(
        url, json={"attempt_id": request_id}, headers=fixtures._auth_headers(admin)
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "passed"
    again = await client.post(
        url, json={"attempt_id": request_id}, headers=fixtures._auth_headers(admin)
    )
    assert again.status_code == 200 and again.json() == response.json()
    assert len(services) == 1
    denied = await client.post(
        url, json={"attempt_id": str(uuid4())}, headers=fixtures._auth_headers(admin)
    )
    assert denied.status_code == 409
    async with AsyncSessionLocal() as db:
        current = await db.get(Document, doc.id)
        assert (current.content, current.docx_path, current.docx_sha256) == original
        job = (
            await db.execute(
                select(AIGenerationJob).where(AIGenerationJob.document_id == doc.id)
            )
        ).scalar_one()
        assert job.total_tokens == 150


@pytest.mark.asyncio
async def test_active_attempt_blocks_another_id_and_replays_without_ai(client):
    admin, doc, case, _ = await seed(client)
    retry_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        previous = (
            await db.execute(
                select(DocumentProvenance)
                .where(
                    DocumentProvenance.document_id == doc.id,
                    DocumentProvenance.event_type == "academic_review",
                )
                .order_by(DocumentProvenance.id.desc())
                .limit(1)
            )
        ).scalar_one()
        db.add(
            DocumentProvenance(
                document_id=doc.id,
                stage="quality",
                event_type=RETRY_STARTED,
                payload={
                    **previous.payload,
                    "status": "pending",
                    "attempt_id": retry_id,
                },
            )
        )
        await db.commit()
        ai = MagicMock()
        ai.call_with_fallback = AsyncMock()
        same = await retry_academic_review(
            db, case["id"], retry_id, admin.id, ai_service=ai
        )
        assert same["status"] == "pending"
        with pytest.raises(HTTPException, match="") as error:
            await retry_academic_review(
                db, case["id"], str(uuid4()), admin.id, ai_service=ai
            )
        assert error.value.status_code == 409
        ai.call_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_text_while_model_runs_cannot_receive_pass(client):
    admin, doc, case, _ = await seed(client)

    async def change_during_review(*args, **kwargs):
        async with AsyncSessionLocal() as other:
            current = await other.get(Document, doc.id)
            current.content += " Changed concurrently."
            await other.commit()
        return verdict()

    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(side_effect=change_during_review)
    async with AsyncSessionLocal() as db:
        result = await retry_academic_review(
            db, case["id"], str(uuid4()), admin.id, ai_service=ai
        )
        assert result["status"] == "unchecked"
        event = (
            await db.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.document_id == doc.id,
                    DocumentProvenance.event_type == "academic_review_retry_discarded",
                )
            )
        ).scalar_one()
        assert event.payload["status"] == "unchecked"


@pytest.mark.asyncio
async def test_timeout_replay_does_not_pay_again_but_new_explicit_id_can_retry(client):
    admin, doc, case, original = await seed(client)
    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(side_effect=[TimeoutError(), verdict()])
    request_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        first = await retry_academic_review(
            db, case["id"], request_id, admin.id, ai_service=ai
        )
        assert first["status"] == "unchecked"
        again = await retry_academic_review(
            db, case["id"], request_id, admin.id, ai_service=ai
        )
        assert again == first and ai.call_with_fallback.await_count == 1
        second = await retry_academic_review(
            db, case["id"], str(uuid4()), admin.id, ai_service=ai
        )
        assert second["status"] == "passed" and ai.call_with_fallback.await_count == 2


@pytest.mark.asyncio
async def test_superseded_attempt_cannot_publish_a_review(client):
    admin, doc, case, _ = await seed(client)
    attempt_b, attempt_c = str(uuid4()), str(uuid4())

    async def replace_attempt(*args, **kwargs):
        async with AsyncSessionLocal() as other:
            started = (
                await other.execute(
                    select(DocumentProvenance).where(
                        DocumentProvenance.document_id == doc.id,
                        DocumentProvenance.event_type == RETRY_STARTED,
                    )
                )
            ).scalar_one()
            other.add(
                DocumentProvenance(
                    document_id=doc.id,
                    stage="quality",
                    event_type=RETRY_STARTED,
                    payload={**started.payload, "attempt_id": attempt_c},
                )
            )
            await other.commit()
        return verdict()

    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(side_effect=replace_attempt)
    async with AsyncSessionLocal() as db:
        result = await retry_academic_review(
            db, case["id"], attempt_b, admin.id, ai_service=ai
        )
        assert result["status"] == "unchecked"
        events = (
            (
                await db.execute(
                    select(DocumentProvenance).where(
                        DocumentProvenance.document_id == doc.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        published = [e for e in events if e.payload.get("attempt_id") == attempt_b]
        assert [e.event_type for e in published] == [
            RETRY_STARTED,
            "academic_review_retry_discarded",
        ]


@pytest.mark.asyncio
async def test_expired_start_replays_free_and_allows_new_explicit_attempt(client):
    admin, doc, case, _ = await seed(client)
    expired_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        previous = (
            await db.execute(
                select(DocumentProvenance)
                .where(
                    DocumentProvenance.document_id == doc.id,
                    DocumentProvenance.event_type == "academic_review",
                )
                .order_by(DocumentProvenance.id.desc())
                .limit(1)
            )
        ).scalar_one()
        db.add(
            DocumentProvenance(
                document_id=doc.id,
                stage="quality",
                event_type=RETRY_STARTED,
                created_at=datetime.now(UTC) - timedelta(minutes=3),
                payload={
                    **previous.payload,
                    "status": "pending",
                    "attempt_id": expired_id,
                },
            )
        )
        await db.commit()
        ai = MagicMock()
        ai.call_with_fallback = AsyncMock(return_value=verdict())
        replay = await retry_academic_review(
            db, case["id"], expired_id, admin.id, ai_service=ai
        )
        assert replay["status"] == "unchecked"
        ai.call_with_fallback.assert_not_awaited()
        result = await retry_academic_review(
            db, case["id"], str(uuid4()), admin.id, ai_service=ai
        )
        assert result["status"] == "passed"
        assert ai.call_with_fallback.await_count == 1


@pytest.mark.asyncio
async def test_operator_can_retry_only_own_work_and_only_while_configured(
    client, monkeypatch
):
    owner, _, own_case, _ = await seed(client)
    _, _, foreign_case, _ = await seed(client)
    async with AsyncSessionLocal() as db:
        user = await db.get(User, owner.id)
        user.is_admin = False
        user.is_super_admin = False
        await db.commit()
    monkeypatch.setattr(settings, "PRODUCTION_OPERATOR_USER_IDS", [owner.id])
    call = AsyncMock(return_value=verdict())
    monkeypatch.setattr(
        "app.services.academic_review_retry.AIService.call_with_fallback", call
    )

    async def request(case):
        return await client.post(
            f"/api/v1/admin/production-cases/{case['id']}/academic-review/retry",
            json={"attempt_id": str(uuid4())},
            headers=fixtures._auth_headers(owner),
        )

    own = await request(own_case)
    assert own.status_code == 200, own.text
    assert own.json()["status"] == "passed"
    assert (await request(foreign_case)).status_code == 404
    monkeypatch.setattr(settings, "PRODUCTION_OPERATOR_USER_IDS", [])
    assert (await request(own_case)).status_code == 403
    assert call.await_count == 1
