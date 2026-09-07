"""ISSUE-005: storage I/O must not block the API/worker event loop.

Found by /qa on 2026-09-07.
Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
"""

import asyncio
import hashlib
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import background_jobs
from app.services.storage_service import StorageService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "args", "sdk_method"),
    [
        ("upload_file", ("qa.docx", b"bytes"), "put_object"),
        ("download_file", ("qa.docx",), "get_object"),
        ("delete_file", ("qa.docx",), "remove_object"),
        ("file_exists", ("qa.docx",), "stat_object"),
        ("get_file_size", ("qa.docx",), "stat_object"),
        ("get_file_sha256", ("qa.docx",), "get_object"),
        ("get_presigned_url", ("qa.docx",), "presigned_get_object"),
    ],
)
async def test_storage_wait_leaves_event_loop_available(method, args, sdk_method):
    started, release = threading.Event(), threading.Event()
    response = MagicMock()
    response.read.return_value = b"bytes"
    response.stream.return_value = [b"bytes"]

    def blocked(*_args, **_kwargs):
        started.set()
        if not release.wait(2):
            raise TimeoutError("event loop did not release the simulated storage wait")
        if sdk_method == "get_object":
            return response
        if sdk_method == "stat_object":
            return SimpleNamespace(size=5)
        return "http://local/qa.docx"

    storage = StorageService()
    storage._client = MagicMock()
    getattr(storage._client, sdk_method).side_effect = blocked
    task = asyncio.create_task(getattr(storage, method)(*args))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 1), 1.5)
        assert not task.done(), "unrelated async work must run while storage is blocked"
    finally:
        release.set()
    result = await task
    if method == "get_file_sha256":
        assert result == hashlib.sha256(b"bytes").hexdigest()
    if sdk_method == "get_object":
        response.close.assert_called_once()
        response.release_conn.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("delete_ok", [True, False])
async def test_cancelled_export_waits_for_upload_then_discards_unbound_file(
    monkeypatch, delete_ok
):
    uploading, uploaded = asyncio.Event(), asyncio.Event()

    async def export_document(**_kwargs):
        uploading.set()
        await uploaded.wait()
        return {"storage_path": "s3://qa/unbound.docx", "artifact_sha256": "a" * 64}

    delete = AsyncMock(return_value=delete_ok)
    persist = AsyncMock()
    outbox = AsyncMock()
    monkeypatch.setattr(StorageService, "delete_file", delete)
    monkeypatch.setattr(background_jobs, "persist_generation_artifact", persist)
    monkeypatch.setattr(background_jobs, "_enqueue_deletion_outbox_best_effort", outbox)
    task = asyncio.create_task(
        background_jobs._export_document_with_fence(
            MagicMock(),
            document_service=SimpleNamespace(export_document=export_document),
            document_id=1,
            user_id=1,
            job_id=1,
            lease_owner="worker",
            lease_token="lease",
        )
    )
    await uploading.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()  # a shutdown may follow the user's cancellation
    await asyncio.sleep(0)
    assert not task.done()
    uploaded.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    persist.assert_not_awaited()
    delete.assert_awaited_once_with("s3://qa/unbound.docx")
    if delete_ok:
        outbox.assert_not_awaited()
    else:
        outbox.assert_awaited_once_with("s3://qa/unbound.docx", "unbound")


@pytest.mark.asyncio
async def test_shutdown_during_cancel_cleanup_still_finishes_deletion(monkeypatch):
    uploading, uploaded = asyncio.Event(), asyncio.Event()
    deleting, deleted = asyncio.Event(), asyncio.Event()

    async def export_document(**_kwargs):
        uploading.set()
        await uploaded.wait()
        return {"storage_path": "s3://qa/unbound.docx", "artifact_sha256": "a" * 64}

    async def delete(_path):
        deleting.set()
        await deleted.wait()
        return True

    monkeypatch.setattr(StorageService, "delete_file", AsyncMock(side_effect=delete))
    persist = AsyncMock()
    monkeypatch.setattr(background_jobs, "persist_generation_artifact", persist)
    task = asyncio.create_task(
        background_jobs._export_document_with_fence(
            MagicMock(),
            document_service=SimpleNamespace(export_document=export_document),
            document_id=1,
            user_id=1,
            job_id=1,
            lease_owner="worker",
            lease_token="lease",
        )
    )
    await uploading.wait()
    task.cancel()
    uploaded.set()
    await deleting.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    deleted.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_read_is_nonblocking_and_closes_connection():
    started, release = threading.Event(), threading.Event()
    response = MagicMock()

    def read(_size):
        started.set()
        if not release.wait(2):
            raise TimeoutError("stream blocked the event loop")
        return b"bytes"

    response.read.side_effect = read
    storage = StorageService()
    storage._client = MagicMock()
    storage._client.get_object.return_value = response
    stream = storage.download_file_stream("qa.docx")
    task = asyncio.create_task(anext(stream))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 1), 1.5)
        assert not task.done()
    finally:
        release.set()
    assert await task == b"bytes"
    await stream.aclose()
    response.close.assert_called_once()
    response.release_conn.assert_called_once()


@pytest.mark.asyncio
async def test_cancellation_during_commit_never_deletes_a_bound_artifact(monkeypatch):
    committed, returning = asyncio.Event(), asyncio.Event()

    async def persist(*_args, **_kwargs):
        committed.set()
        await returning.wait()
        return None

    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(StorageService, "delete_file", delete)
    monkeypatch.setattr(background_jobs, "persist_generation_artifact", persist)
    service = SimpleNamespace(
        export_document=AsyncMock(
            return_value={
                "storage_path": "s3://qa/bound.docx",
                "artifact_sha256": "a" * 64,
            }
        )
    )
    task = asyncio.create_task(
        background_jobs._export_document_with_fence(
            MagicMock(),
            document_service=service,
            document_id=1,
            user_id=1,
            job_id=1,
            lease_owner="worker",
            lease_token="lease",
        )
    )
    await committed.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    returning.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    delete.assert_not_awaited()
