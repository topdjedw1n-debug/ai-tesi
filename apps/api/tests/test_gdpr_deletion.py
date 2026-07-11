"""Regression tests for truthful GDPR deletion and admin retries."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, call, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app.api.v1.endpoints.admin_documents import retry_document_generation
from app.core.database import AsyncSessionLocal
from app.core.exceptions import APIException, ValidationError
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentOutline,
    DocumentSection,
    DocumentSource,
    ProductionCase,
    ReleaseGateResult,
)
from app.services.gdpr_service import GDPRService
from main import app


def _admin_request(document_id: int) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": f"/api/v1/admin/documents/{document_id}/retry",
            "headers": [],
            "client": ("127.0.0.1", 1234),
        }
    )


async def _create_admin_and_owner(db_session, *, suffix: str) -> tuple[User, User]:
    admin = User(
        email=f"gdpr-retry-admin-{suffix}@example.com",
        full_name="Retry Admin",
        is_active=True,
        is_admin=True,
        is_super_admin=True,
    )
    owner = User(
        email=f"gdpr-retry-owner-{suffix}@example.com",
        full_name="Document Owner",
        is_active=True,
    )
    db_session.add_all([admin, owner])
    await db_session.flush()
    return admin, owner


def test_gdpr_user_routes_are_mounted() -> None:
    paths = {route.path for route in app.routes}

    assert "/api/v1/user/export-data" in paths
    assert "/api/v1/user/delete-account" in paths


@pytest.mark.asyncio
async def test_gdpr_user_routes_require_authentication() -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        export_response = await client.get("/api/v1/user/export-data")
        delete_response = await client.delete("/api/v1/user/delete-account")

    assert export_response.status_code == 401
    assert delete_response.status_code == 401


@pytest.mark.asyncio
async def test_delete_user_account_removes_files_before_database_records(db_session):
    user = User(email="gdpr-success@example.com", full_name="GDPR User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    document = Document(
        user_id=user.id,
        title="Personal Thesis",
        topic="Privacy",
        docx_path="s3://documents/personal.docx",
        pdf_path="s3://documents/personal.pdf",
        custom_requirements_file_path="s3://documents/methodology.pdf",
    )
    db_session.add(document)
    await db_session.flush()
    db_session.add(
        AIGenerationJob(
            user_id=user.id,
            document_id=document.id,
            job_type="full_document",
            status="completed",
            request_payload={
                "superseded_artifact_paths": ["s3://documents/previous-personal.docx"]
            },
        )
    )
    await db_session.commit()
    await db_session.refresh(document)
    document_id = document.id

    with patch(
        "app.services.storage_service.StorageService.delete_file",
        new_callable=AsyncMock,
        return_value=True,
    ) as delete_file:
        result = await GDPRService(db_session).delete_user_account(user.id)

    assert result["status"] == "account_deleted"
    assert result["files_deleted"] == 4
    assert delete_file.await_args_list == [
        call("s3://documents/personal.docx"),
        call("s3://documents/personal.pdf"),
        call("s3://documents/methodology.pdf"),
        call("s3://documents/previous-personal.docx"),
    ]
    assert await db_session.get(Document, document_id) is None
    await db_session.refresh(user)
    assert user.email == f"deleted_{user.id}@deleted.com"
    assert user.is_active is False


@pytest.mark.asyncio
async def test_delete_user_account_fails_closed_when_storage_deletion_fails(
    db_session,
):
    user = User(email="gdpr-failure@example.com", full_name="GDPR User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = int(user.id)
    original_email = user.email

    document = Document(
        user_id=user.id,
        title="Personal Thesis",
        topic="Privacy",
        docx_path="s3://documents/still-personal.docx",
    )
    db_session.add(document)
    await db_session.flush()
    completed_job = AIGenerationJob(
        user_id=user.id,
        document_id=document.id,
        job_type="full_document",
        status="completed",
    )
    db_session.add(completed_job)
    await db_session.commit()
    await db_session.refresh(document)
    document_id = document.id
    completed_job_id = int(completed_job.id)

    with patch(
        "app.services.storage_service.StorageService.delete_file",
        new_callable=AsyncMock,
        side_effect=RuntimeError("storage unavailable"),
    ):
        with pytest.raises(ValidationError, match="storage unavailable"):
            await GDPRService(db_session).delete_user_account(user_id)

    assert await db_session.get(Document, document_id) is not None
    persisted_user = await db_session.get(User, user_id)
    assert persisted_user is not None
    assert persisted_user.email == original_email
    assert persisted_user.is_active is True
    assert persisted_user.deletion_requested_at is not None

    persisted_job = await db_session.get(AIGenerationJob, completed_job_id)
    assert persisted_job is not None
    persisted_job.status = "queued"
    with pytest.raises(IntegrityError, match="account deletion requested"):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_delete_user_account_keeps_durable_marker_while_job_is_active(
    db_session,
):
    user = User(email="gdpr-active@example.com", full_name="GDPR User")
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Generating Thesis",
        topic="Privacy",
        status="generating",
        docx_path="s3://documents/not-yet-final.docx",
    )
    db_session.add(document)
    await db_session.flush()
    job = AIGenerationJob(
        user_id=user.id,
        document_id=document.id,
        job_type="full_document",
        status="running",
    )
    db_session.add(job)
    await db_session.commit()
    user_id = int(user.id)
    job_id = int(job.id)
    executed_statements: list[str] = []
    execute = db_session.execute

    async def record_execute(statement, *args, **kwargs):
        executed_statements.append(str(statement))
        return await execute(statement, *args, **kwargs)

    with (
        patch.object(db_session, "execute", side_effect=record_execute),
        patch(
            "app.services.storage_service.StorageService.delete_file",
            new_callable=AsyncMock,
            return_value=True,
        ) as delete_file,
    ):
        with pytest.raises(ValidationError, match="generation is active"):
            await GDPRService(db_session).delete_user_account(user_id)

    delete_file.assert_not_awaited()
    assert any("FROM ai_generation_jobs" in sql for sql in executed_statements)
    assert not any("FROM documents" in sql for sql in executed_statements)
    persisted_user = await db_session.get(User, user_id)
    persisted_job = await db_session.get(AIGenerationJob, job_id)
    assert persisted_user is not None
    assert persisted_user.deletion_requested_at is not None
    assert persisted_user.is_active is True
    assert persisted_job is not None
    assert persisted_job.status == "running"


@pytest.mark.asyncio
async def test_delete_user_account_blocks_job_created_after_file_snapshot(db_session):
    user = User(email="gdpr-race@example.com", full_name="GDPR User")
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Race Thesis",
        topic="Privacy",
        status="completed",
        docx_path="s3://documents/race.docx",
    )
    db_session.add(document)
    await db_session.commit()
    user_id = int(user.id)
    document_id = int(document.id)
    observed_marker = False

    async def attempt_competing_enqueue(_path: str) -> bool:
        nonlocal observed_marker
        async with AsyncSessionLocal() as competing_session:
            competing_user = await competing_session.get(User, user_id)
            assert competing_user is not None
            observed_marker = competing_user.deletion_requested_at is not None
            competing_session.add(
                AIGenerationJob(
                    user_id=user_id,
                    document_id=document_id,
                    job_type="full_document",
                    status="queued",
                )
            )
            with pytest.raises(IntegrityError, match="account deletion requested"):
                await competing_session.commit()
            await competing_session.rollback()
        return True

    with patch(
        "app.services.storage_service.StorageService.delete_file",
        new_callable=AsyncMock,
        side_effect=attempt_competing_enqueue,
    ):
        result = await GDPRService(db_session).delete_user_account(user_id)

    assert result["status"] == "account_deleted"
    assert observed_marker is True
    assert await db_session.get(Document, document_id) is None
    job_count = (
        await db_session.execute(
            select(func.count(AIGenerationJob.id)).where(
                AIGenerationJob.user_id == user_id
            )
        )
    ).scalar_one()
    assert job_count == 0


def test_gdpr_deletion_marker_migration_guards_new_and_reactivated_jobs() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "023_user_deletion_generation_guard.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(migration.split())

    assert "ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMPTZ" in normalized
    assert "FOR KEY SHARE" in normalized
    assert "BEFORE INSERT ON ai_generation_jobs" in normalized
    assert "BEFORE UPDATE OF user_id, status ON ai_generation_jobs" in normalized
    assert "OLD.status NOT IN ('queued', 'running')" in normalized


@pytest.mark.asyncio
@pytest.mark.parametrize("document_status", ["completed", "failed", "failed_quality"])
async def test_admin_retry_invalidates_evidence_and_enqueues_real_job_atomically(
    db_session,
    document_status: str,
):
    admin, owner = await _create_admin_and_owner(db_session, suffix=document_status)
    document = Document(
        user_id=owner.id,
        title="Retry Thesis",
        topic="Durable retry",
        status=document_status,
        additional_requirements="Use the document-specific constraints",
        requirements_file_processed=True,
        citation_style="apa",
        outline={"sections": ["Old"]},
        content="Old generated content",
        docx_path=f"s3://documents/{document_status}.docx",
        pdf_path=f"s3://documents/{document_status}.pdf",
        docx_sha256="a" * 64,
        pdf_sha256="b" * 64,
        completed_at=datetime.now(UTC),
    )
    db_session.add(document)
    await db_session.flush()
    section = DocumentSection(
        document_id=document.id,
        title="Old section",
        section_index=0,
        status="completed",
        content="Old evidence-bound section",
    )
    outline = DocumentOutline(
        document_id=document.id,
        outline_data={"sections": ["Old"]},
    )
    source = DocumentSource(
        document_id=document.id,
        title="Old source",
        verification_status="verified",
    )
    production_case = ProductionCase(
        document_id=document.id,
        client_user_id=owner.id,
        requirements_text="Follow the university methodology",
        release_status="released",
        delivery_status="delivered",
        editorial_status="approved",
        released_docx_path=document.docx_path,
        released_pdf_path=document.pdf_path,
        released_docx_sha256=document.docx_sha256,
        released_pdf_sha256=document.pdf_sha256,
        released_at=datetime.now(UTC),
    )
    db_session.add_all([section, outline, source, production_case])
    await db_session.flush()
    gate = ReleaseGateResult(
        production_case_id=production_case.id,
        gate_key="citation_verification",
        status="passed",
    )
    db_session.add(gate)
    await db_session.commit()
    document_id = int(document.id)
    owner_id = int(owner.id)
    production_case_id = int(production_case.id)

    with patch(
        "app.services.storage_service.StorageService.delete_file",
        new_callable=AsyncMock,
        return_value=True,
    ) as delete_file:
        result = await retry_document_generation(
            document_id=document_id,
            request=_admin_request(document_id),
            current_user=admin,
            db=db_session,
        )

    assert result["status"] == "queued"
    assert isinstance(result["job_id"], int)
    assert result["check_url"] == f"/api/v1/jobs/{result['job_id']}/status"
    assert delete_file.await_args_list == [
        call(f"s3://documents/{document_status}.docx"),
        call(f"s3://documents/{document_status}.pdf"),
    ]

    db_session.expire_all()
    persisted_document = await db_session.get(Document, document_id)
    job = await db_session.get(AIGenerationJob, result["job_id"])
    persisted_case = await db_session.get(ProductionCase, production_case_id)
    assert persisted_document is not None
    assert persisted_document.status == "generating"
    assert persisted_document.content is None
    assert persisted_document.outline is None
    assert persisted_document.docx_path is None
    assert persisted_document.pdf_path is None
    assert persisted_document.docx_sha256 is None
    assert persisted_document.pdf_sha256 is None
    assert job is not None
    assert job.status == "queued"
    assert job.user_id == owner_id
    assert job.request_payload["additional_requirements"] == (
        "Follow the university methodology"
    )
    assert persisted_document.additional_requirements == (
        "Use the document-specific constraints"
    )
    assert persisted_case is not None
    assert persisted_case.release_status == "blocked"
    assert persisted_case.delivery_status == "not_ready"
    assert persisted_case.editorial_status == "not_started"
    assert persisted_case.released_docx_path is None
    assert persisted_case.released_pdf_path is None

    for model in (DocumentSection, DocumentOutline, DocumentSource, ReleaseGateResult):
        predicate = (
            model.production_case_id == production_case_id
            if model is ReleaseGateResult
            else model.document_id == document_id
        )
        count = (
            await db_session.execute(select(func.count(model.id)).where(predicate))
        ).scalar_one()
        assert count == 0


@pytest.mark.asyncio
async def test_admin_retry_rejects_active_job_without_invalidating_artifacts(
    db_session,
):
    admin, owner = await _create_admin_and_owner(db_session, suffix="active")
    document = Document(
        user_id=owner.id,
        title="Active Retry Thesis",
        topic="Durable retry",
        status="failed",
        docx_path="s3://documents/keep-active.docx",
    )
    db_session.add(document)
    await db_session.flush()
    active_job = AIGenerationJob(
        user_id=owner.id,
        document_id=document.id,
        job_type="full_document",
        status="queued",
    )
    db_session.add(active_job)
    await db_session.commit()
    document_id = int(document.id)
    active_job_id = int(active_job.id)

    with patch(
        "app.services.storage_service.StorageService.delete_file",
        new_callable=AsyncMock,
        return_value=True,
    ) as delete_file:
        with pytest.raises(APIException) as error:
            await retry_document_generation(
                document_id=document_id,
                request=_admin_request(document_id),
                current_user=admin,
                db=db_session,
            )

    assert error.value.status_code == 409
    assert error.value.error_code == "GENERATION_ALREADY_ACTIVE"
    delete_file.assert_not_awaited()
    db_session.expire_all()
    persisted_document = await db_session.get(Document, document_id)
    jobs = (
        (
            await db_session.execute(
                select(AIGenerationJob).where(
                    AIGenerationJob.document_id == document_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert persisted_document is not None
    assert persisted_document.docx_path == "s3://documents/keep-active.docx"
    assert len(jobs) == 1
    assert jobs[0].id == active_job_id


@pytest.mark.asyncio
async def test_admin_retry_rejects_account_with_pending_gdpr_deletion(db_session):
    admin, owner = await _create_admin_and_owner(db_session, suffix="deleting")
    owner.deletion_requested_at = datetime.now(UTC)
    document = Document(
        user_id=owner.id,
        title="Deleting Owner Thesis",
        topic="Privacy",
        status="failed",
    )
    db_session.add(document)
    await db_session.commit()
    document_id = int(document.id)

    with pytest.raises(APIException) as error:
        await retry_document_generation(
            document_id=document_id,
            request=_admin_request(document_id),
            current_user=admin,
            db=db_session,
        )

    assert error.value.status_code == 409
    assert error.value.error_code == "ACCOUNT_DELETION_PENDING"
    job_count = (
        await db_session.execute(
            select(func.count(AIGenerationJob.id)).where(
                AIGenerationJob.document_id == document_id
            )
        )
    ).scalar_one()
    assert job_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requirements_file_processed", "requirements", "citation_style", "error_code"),
    [
        # Universal task contract (2026-07-11): no methodology AND no
        # confirmed assumptions -> not ready; unsupported style -> not ready.
        (False, "Parsed methodology", "apa", "TASK_CONTRACT_NOT_READY"),
        (True, "", "apa", "TASK_CONTRACT_NOT_READY"),
        (True, "Parsed methodology", "vancouver", "TASK_CONTRACT_NOT_READY"),
    ],
)
async def test_admin_retry_rejects_job_the_worker_would_quarantine(
    db_session,
    requirements_file_processed: bool,
    requirements: str,
    citation_style: str,
    error_code: str,
):
    admin, owner = await _create_admin_and_owner(
        db_session, suffix=f"contract-{error_code}-{citation_style}"
    )
    document = Document(
        user_id=owner.id,
        title="Invalid Contract Retry",
        topic="Truthful queueing",
        status="failed",
        requirements_file_processed=requirements_file_processed,
        additional_requirements=requirements,
        citation_style=citation_style,
    )
    db_session.add(document)
    await db_session.commit()
    document_id = int(document.id)

    with pytest.raises(APIException) as error:
        await retry_document_generation(
            document_id=document_id,
            request=_admin_request(document_id),
            current_user=admin,
            db=db_session,
        )

    assert error.value.status_code == 409
    assert error.value.error_code == error_code
    job_count = (
        await db_session.execute(
            select(func.count(AIGenerationJob.id)).where(
                AIGenerationJob.document_id == document_id
            )
        )
    ).scalar_one()
    assert job_count == 0


@pytest.mark.asyncio
async def test_admin_retry_obeys_generation_page_budget(db_session):
    admin, owner = await _create_admin_and_owner(db_session, suffix="page-budget")
    document = Document(
        user_id=owner.id,
        title="Oversized Retry",
        topic="Budget enforcement",
        status="failed",
        target_pages=10_000,
        requirements_file_processed=True,
        additional_requirements="Parsed methodology",
        citation_style="apa",
    )
    db_session.add(document)
    await db_session.commit()
    document_id = int(document.id)

    with pytest.raises(APIException) as error:
        await retry_document_generation(
            document_id=document_id,
            request=_admin_request(document_id),
            current_user=admin,
            db=db_session,
        )

    assert error.value.status_code == 400
    assert error.value.error_code == "GENERATION_GATE_BLOCKED"
    job_count = (
        await db_session.execute(
            select(func.count(AIGenerationJob.id)).where(
                AIGenerationJob.document_id == document_id
            )
        )
    ).scalar_one()
    assert job_count == 0


@pytest.mark.asyncio
async def test_admin_retry_keeps_committed_job_when_deferred_cleanup_fails(
    db_session,
):
    admin, owner = await _create_admin_and_owner(db_session, suffix="rollback")
    document = Document(
        user_id=owner.id,
        title="Rollback Retry Thesis",
        topic="Atomic retry",
        status="failed",
        additional_requirements="Use the processed methodology",
        requirements_file_processed=True,
        citation_style="apa",
        docx_path="s3://documents/retry-rollback.docx",
        docx_sha256="c" * 64,
    )
    db_session.add(document)
    await db_session.flush()
    section = DocumentSection(
        document_id=document.id,
        title="Evidence that must survive",
        section_index=0,
        status="completed",
    )
    db_session.add(section)
    await db_session.commit()
    document_id = int(document.id)
    section_id = int(section.id)

    with patch(
        "app.services.storage_service.StorageService.delete_file",
        new_callable=AsyncMock,
        side_effect=RuntimeError("storage unavailable"),
    ):
        result = await retry_document_generation(
            document_id=document_id,
            request=_admin_request(document_id),
            current_user=admin,
            db=db_session,
        )

    assert result["status"] == "queued"
    db_session.expire_all()
    persisted_document = await db_session.get(Document, document_id)
    persisted_section = await db_session.get(DocumentSection, section_id)
    persisted_job = (
        await db_session.execute(
            select(AIGenerationJob).where(AIGenerationJob.document_id == document_id)
        )
    ).scalar_one()
    assert persisted_document is not None
    assert persisted_document.status == "generating"
    assert persisted_document.docx_path is None
    assert persisted_document.docx_sha256 is None
    assert persisted_section is None
    assert persisted_job.status == "queued"
    assert persisted_job.request_payload["superseded_artifact_paths"] == [
        "s3://documents/retry-rollback.docx"
    ]
