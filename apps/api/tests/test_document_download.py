"""Regression tests for truthful, content-bound document delivery."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.v1.endpoints.documents import (
    _delivery_response,
    _mask_unreleased_content,
    _require_released_artifact,
    download_document_secure,
    export_document,
)
from app.models.document import Document, ProductionCase
from app.schemas.document import ExportRequest
from app.services.production_case_service import ProductionCaseService

ARTIFACT_SHA256 = "a" * 64


def _result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _document() -> Document:
    return Document(
        id=42,
        user_id=7,
        title="Reviewed Thesis",
        topic="A sufficiently long academic research topic",
        status="completed",
        docx_path="s3://documents/7/42/reviewed.docx",
        docx_sha256=ARTIFACT_SHA256,
        completed_at=datetime(2026, 7, 10),
    )


def _released_case() -> ProductionCase:
    return ProductionCase(
        id=9,
        document_id=42,
        client_user_id=7,
        release_status="released",
        delivery_status="delivered",
        released_docx_path="s3://documents/7/42/reviewed.docx",
        released_docx_sha256=ARTIFACT_SHA256,
        release_version=3,
    )


@pytest.mark.asyncio
async def test_user_export_issues_token_for_reviewed_file_without_regenerating():
    document = _document()
    document_service = MagicMock()
    document_service.check_document_ownership = AsyncMock(return_value=document)
    document_service.export_document = AsyncMock()

    expected = {
        "download_url": "/api/v1/documents/download/file?token=bound",
        "expires_at": "2026-07-10T12:00:00",
        "file_size": 123,
        "format": "docx",
    }
    with (
        patch(
            "app.api.v1.endpoints.documents.DocumentService",
            return_value=document_service,
        ),
        patch(
            "app.api.v1.endpoints.documents._delivery_response",
            new=AsyncMock(return_value=expected),
        ) as delivery,
    ):
        response = await export_document(
            request=MagicMock(),
            document_id=42,
            export_request=ExportRequest(format="docx"),
            current_user=MagicMock(id=7),
            db=MagicMock(),
        )

    assert response == expected
    delivery.assert_awaited_once()
    document_service.export_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_path_without_content_fingerprint_is_blocked():
    document = _document()
    case = _released_case()
    case.released_docx_sha256 = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(case))
    db.commit = AsyncMock()

    with patch.object(
        ProductionCaseService,
        "get_release_gates",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _require_released_artifact(db, document, "docx")

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "no longer current" in exc_info.value.detail


@pytest.mark.asyncio
async def test_failed_document_cannot_keep_a_stale_release_open():
    document = _document()
    document.status = "failed"
    case = _released_case()
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(case))
    db.commit = AsyncMock()

    with patch.object(
        ProductionCaseService,
        "get_release_gates",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _require_released_artifact(db, document, "docx")

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "completed delivery state" in exc_info.value.detail
    assert case.release_status == "blocked"
    assert case.released_docx_path is None
    db.commit.assert_awaited_once()


def test_failed_document_content_is_masked_even_if_case_status_is_stale():
    result = {
        "status": "failed",
        "release_status": "released",
        "content": "must not leak",
        "sections": [{"content": "must not leak either"}],
    }

    masked = _mask_unreleased_content(result)

    assert masked["content"] is None
    assert masked["sections"][0]["content"] is None


@pytest.mark.asyncio
async def test_delivery_token_contains_release_path_version_and_hash():
    document = _document()
    case = _released_case()
    storage = MagicMock()
    storage.get_file_size = AsyncMock(return_value=456)

    with (
        patch(
            "app.api.v1.endpoints.documents._require_released_artifact",
            new=AsyncMock(return_value=(document.docx_path, case)),
        ),
        patch("app.api.v1.endpoints.documents.StorageService", return_value=storage),
        patch(
            "app.api.v1.endpoints.documents.create_download_token",
            return_value="bound-token",
        ) as create_token,
    ):
        response = await _delivery_response(
            MagicMock(), document, user_id=7, file_format="docx"
        )

    assert response["download_url"].endswith("token=bound-token")
    assert response["file_size"] == 456
    assert create_token.call_args.kwargs["file_path"] == document.docx_path
    assert create_token.call_args.kwargs["release_version"] == 3
    assert create_token.call_args.kwargs["file_sha256"] == ARTIFACT_SHA256


@pytest.mark.asyncio
async def test_secure_download_rejects_replaced_bytes_under_same_path():
    document = _document()
    case = _released_case()
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(document))
    storage = MagicMock()
    storage.get_file_sha256 = AsyncMock(return_value="b" * 64)

    payload = {
        "document_id": 42,
        "user_id": 7,
        "scope": "client_delivery",
        "file_format": "docx",
        "file_path": document.docx_path,
        "file_sha256": ARTIFACT_SHA256,
        "release_version": 3,
    }
    with (
        patch(
            "app.api.v1.endpoints.documents.verify_download_token",
            return_value=payload,
        ),
        patch(
            "app.api.v1.endpoints.documents._require_released_artifact",
            new=AsyncMock(return_value=(document.docx_path, case)),
        ),
        patch("app.api.v1.endpoints.documents.StorageService", return_value=storage),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await download_document_secure(token="signed", db=db)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "differs from the reviewed artifact" in exc_info.value.detail


@pytest.mark.asyncio
async def test_secure_download_rejects_old_release_version():
    document = _document()
    case = _released_case()
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(document))
    payload = {
        "document_id": 42,
        "user_id": 7,
        "scope": "client_delivery",
        "file_format": "docx",
        "file_path": document.docx_path,
        "file_sha256": ARTIFACT_SHA256,
        "release_version": 2,
    }
    with (
        patch(
            "app.api.v1.endpoints.documents.verify_download_token",
            return_value=payload,
        ),
        patch(
            "app.api.v1.endpoints.documents._require_released_artifact",
            new=AsyncMock(return_value=(document.docx_path, case)),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await download_document_secure(token="old", db=db)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "earlier release" in exc_info.value.detail


@pytest.mark.asyncio
async def test_valid_secure_download_is_private_and_not_cached():
    document = _document()
    case = _released_case()
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(document))
    storage = MagicMock()
    storage.get_file_sha256 = AsyncMock(return_value=ARTIFACT_SHA256)

    async def _stream():
        yield b"reviewed bytes"

    storage.download_file_stream.return_value = _stream()
    payload = {
        "document_id": 42,
        "user_id": 7,
        "scope": "client_delivery",
        "file_format": "docx",
        "file_path": document.docx_path,
        "file_sha256": ARTIFACT_SHA256,
        "release_version": 3,
    }
    with (
        patch(
            "app.api.v1.endpoints.documents.verify_download_token",
            return_value=payload,
        ),
        patch(
            "app.api.v1.endpoints.documents._require_released_artifact",
            new=AsyncMock(return_value=(document.docx_path, case)),
        ),
        patch("app.api.v1.endpoints.documents.StorageService", return_value=storage),
    ):
        response = await download_document_secure(token="current", db=db)

    assert isinstance(response, StreamingResponse)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.media_type.endswith("wordprocessingml.document")
