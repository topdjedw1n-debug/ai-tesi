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
