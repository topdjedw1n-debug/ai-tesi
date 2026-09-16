"""Saved job timing is readable without paying or mutating execution state."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api.v1.endpoints.jobs import get_document_job_status
from app.models.auth import User
from app.models.document import DocumentProvenance
from tests.test_generation_worker import _seed_job


@pytest.mark.asyncio
async def test_status_exposes_persisted_queue_and_worker_times_without_mutation(
    db_session,
):
    doc, job = await _seed_job(db_session, email="job-timing@example.com")
    now = datetime.now(UTC)
    job.started_at = now - timedelta(minutes=5)
    job.available_at = now - timedelta(seconds=35)
    job.heartbeat_at = now - timedelta(seconds=7)
    job.lease_expires_at = now + timedelta(seconds=113)
    await db_session.commit()
    owner = await db_session.get(User, job.user_id)
    event_count = await db_session.scalar(select(func.count(DocumentProvenance.id)))
    before = (job.status, job.attempt_count, job.total_tokens)

    result = await get_document_job_status(doc.id, owner, db_session)

    assert result.job_id == job.id
    assert result.started_at == job.started_at
    assert result.available_at == job.available_at
    assert result.heartbeat_at == job.heartbeat_at
    assert result.lease_expires_at == job.lease_expires_at
    assert result.observed_at >= now
    assert (
        await db_session.scalar(select(func.count(DocumentProvenance.id)))
        == event_count
    )
    assert (job.status, job.attempt_count, job.total_tokens) == before


@pytest.mark.asyncio
async def test_status_lists_the_warnings_of_the_latest_v2_job_in_words(db_session):
    """The manager reads every warning of the run with its text and detail,
    not a count (idle session 16.09.2026, point 3); rows of other jobs and
    other event types stay out; a legacy job has no list."""
    from app.services.executor_v2.warnings import warning

    doc, job = await _seed_job(db_session, email="job-warnings@example.com")
    job.request_payload = {**job.request_payload, "executor_version": 2}
    rows = [
        warning("catalogue_unavailable", "sources", detail="semantic_scholar"),
        warning(
            "plan_material_gap",
            "outline",
            section_index=3,
            detail="Casi aziendali: у пакеті немає кейсів",
        ),
    ]
    for payload in rows:
        db_session.add(
            DocumentProvenance(
                document_id=doc.id,
                stage="provider",
                event_type="generation_warning",
                payload={"job_id": job.id, "document_id": doc.id, **payload},
            )
        )
    db_session.add(
        DocumentProvenance(
            document_id=doc.id,
            stage="provider",
            event_type="generation_warning",
            payload={"job_id": job.id + 1, "document_id": doc.id, **rows[0]},
        )
    )
    db_session.add(
        DocumentProvenance(
            document_id=doc.id,
            stage="provider",
            event_type="generation_dependency",
            payload={"job_id": job.id, "kind": "executor_search", "outcome": "failed"},
        )
    )
    await db_session.commit()
    owner = await db_session.get(User, job.user_id)

    result = await get_document_job_status(doc.id, owner, db_session)

    assert [(w["code"], w["detail"], w["section_label"]) for w in result.warnings] == [
        ("catalogue_unavailable", "semantic_scholar", "Загальні зауваження"),
        ("plan_material_gap", "Casi aziendali: у пакеті немає кейсів", "Розділ 3"),
    ]
    assert result.warnings[0]["message_uk"] == "Каталог джерел не відповідав."
    assert all(w["id"] and w["severity"] == "warning" for w in result.warnings)

    job.request_payload = {
        k: v for k, v in job.request_payload.items() if k != "executor_version"
    }
    await db_session.commit()
    assert (await get_document_job_status(doc.id, owner, db_session)).warnings == []
