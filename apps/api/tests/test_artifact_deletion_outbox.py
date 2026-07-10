"""Durable retry queue for storage deletions (audit 2026-07-10).

Before the outbox, a failed MinIO delete of a superseded/unbound blob was
only logged — the file stayed in storage forever while the DB claimed the
artifact was gone."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.models.document import ArtifactDeletionOutbox
from app.services.generation_worker import (
    clear_artifact_deletion_entries,
    enqueue_artifact_deletions,
    process_artifact_deletion_outbox,
    utc_now,
)


@pytest.mark.asyncio
async def test_enqueue_dedups_and_survives_commit(db_session):
    added = await enqueue_artifact_deletions(
        db_session,
        ["s3://b/doc/1.docx", "s3://b/doc/1.docx", "s3://b/doc/1.pdf", ""],
        reason="superseded",
    )
    assert added == 2
    # Re-enqueueing the same paths is a no-op, not an error.
    added_again = await enqueue_artifact_deletions(
        db_session, ["s3://b/doc/1.docx"], reason="superseded"
    )
    assert added_again == 0
    await db_session.commit()

    rows = (await db_session.execute(select(ArtifactDeletionOutbox))).scalars().all()
    assert sorted(r.file_path for r in rows) == [
        "s3://b/doc/1.docx",
        "s3://b/doc/1.pdf",
    ]
    assert all(r.reason == "superseded" for r in rows)


@pytest.mark.asyncio
async def test_sweep_confirmed_deletion_clears_row(db_session):
    await enqueue_artifact_deletions(db_session, ["s3://b/doc/2.docx"])
    await db_session.commit()

    storage = MagicMock()
    storage.delete_file = AsyncMock(return_value=True)
    processed, confirmed = await process_artifact_deletion_outbox(
        db_session, storage=storage, now=utc_now() + timedelta(seconds=1)
    )
    assert (processed, confirmed) == (1, 1)
    storage.delete_file.assert_awaited_once_with("s3://b/doc/2.docx")

    remaining = (
        (await db_session.execute(select(ArtifactDeletionOutbox))).scalars().all()
    )
    assert remaining == []


@pytest.mark.asyncio
async def test_sweep_failure_backs_off_and_keeps_row(db_session):
    await enqueue_artifact_deletions(db_session, ["s3://b/doc/3.docx"])
    await db_session.commit()

    storage = MagicMock()
    storage.delete_file = AsyncMock(side_effect=RuntimeError("minio down"))
    sweep_time = utc_now() + timedelta(seconds=1)
    processed, confirmed = await process_artifact_deletion_outbox(
        db_session, storage=storage, now=sweep_time
    )
    assert (processed, confirmed) == (1, 0)

    row = (await db_session.execute(select(ArtifactDeletionOutbox))).scalar_one()
    assert row.attempts == 1
    assert "minio down" in (row.last_error or "")
    next_at = row.next_attempt_at
    if next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=sweep_time.tzinfo)
    assert next_at > sweep_time

    # Not due yet: an immediate second sweep must skip it.
    processed2, _ = await process_artifact_deletion_outbox(
        db_session, storage=storage, now=sweep_time
    )
    assert processed2 == 0


@pytest.mark.asyncio
async def test_unconfirmed_deletion_counts_as_failure(db_session):
    """storage.delete_file returning False (unconfirmed) must not clear."""
    await enqueue_artifact_deletions(db_session, ["s3://b/doc/4.docx"])
    await db_session.commit()

    storage = MagicMock()
    storage.delete_file = AsyncMock(return_value=False)
    processed, confirmed = await process_artifact_deletion_outbox(
        db_session, storage=storage, now=utc_now() + timedelta(seconds=1)
    )
    assert (processed, confirmed) == (1, 0)
    row = (await db_session.execute(select(ArtifactDeletionOutbox))).scalar_one()
    assert "did not confirm" in (row.last_error or "")


@pytest.mark.asyncio
async def test_clear_entries_removes_confirmed_paths(db_session):
    await enqueue_artifact_deletions(
        db_session, ["s3://b/doc/5.docx", "s3://b/doc/5.pdf"]
    )
    await db_session.commit()

    await clear_artifact_deletion_entries(db_session, ["s3://b/doc/5.docx"])
    remaining = (
        (await db_session.execute(select(ArtifactDeletionOutbox))).scalars().all()
    )
    assert [r.file_path for r in remaining] == ["s3://b/doc/5.pdf"]


def test_invalidation_and_poll_loop_are_wired():
    """Pin the wiring: evidence invalidation enqueues in-transaction, the
    worker poll loop sweeps, and the export fence enqueues on cleanup
    failure."""
    import inspect

    from app.api.v1.endpoints import generate as generate_endpoint
    from app.services import background_jobs as bj
    from app.services import generation_worker as gw

    invalidate_src = inspect.getsource(
        generate_endpoint._invalidate_previous_generation_evidence
    )
    assert "enqueue_artifact_deletions" in invalidate_src

    poll_src = inspect.getsource(gw.GenerationWorker.poll_once)
    assert "process_artifact_deletion_outbox" in poll_src

    fence_src = inspect.getsource(bj._export_document_with_fence)
    assert "_enqueue_deletion_outbox_best_effort" in fence_src
