"""Regression coverage for single-owner full-document generation jobs."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex
from starlette.requests import Request

from app.api.v1.endpoints import generate as generate_endpoint
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentSection,
    ProductionCase,
)
from app.schemas.document import AsyncGenerationRequest

ACTIVE_JOB_INDEX = "uq_ai_generation_jobs_active_document_job_type"
SECTION_INDEX = "uq_document_sections_document_section_index"


async def _create_user_and_document(db_session, *, email: str) -> tuple[User, Document]:
    user = User(
        email=email,
        full_name="Single Owner Test",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    document = Document(
        user_id=user.id,
        title="Single owner thesis",
        topic="Concurrency control",
        status="draft",
    )
    db_session.add(document)
    await db_session.flush()
    return user, document


def test_active_job_partial_unique_index_is_in_model_metadata():
    index = next(
        index
        for index in AIGenerationJob.__table__.indexes
        if index.name == ACTIVE_JOB_INDEX
    )

    postgres_ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    sqlite_ddl = str(CreateIndex(index).compile(dialect=sqlite.dialect()))

    assert "CREATE UNIQUE INDEX" in postgres_ddl
    assert "(document_id, job_type)" in postgres_ddl
    assert "WHERE status IN ('queued', 'running')" in postgres_ddl
    # Tests use SQLite. It must enforce the same partial invariant instead of
    # accidentally turning the index into an unconditional unique constraint.
    assert "CREATE UNIQUE INDEX" in sqlite_ddl
    assert "WHERE status IN ('queued', 'running')" in sqlite_ddl


def test_postgres_migration_creates_matching_partial_unique_index():
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "015_active_generation_job_unique_index.sql"
    ).read_text(encoding="utf-8")

    normalized = " ".join(migration.split())
    assert f"CREATE UNIQUE INDEX IF NOT EXISTS {ACTIVE_JOB_INDEX}" in normalized
    assert "ON ai_generation_jobs (document_id, job_type)" in normalized
    assert "WHERE status IN ('queued', 'running')" in normalized


def test_fencing_migration_adds_token_quarantine_and_section_uniqueness():
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "022_generation_fencing_and_section_uniqueness.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(migration.split())

    assert "ADD COLUMN IF NOT EXISTS lease_token VARCHAR(64)" in normalized
    assert "status IN ('queued', 'running')" in normalized
    assert "release_status = 'blocked'" in normalized
    assert f"CREATE UNIQUE INDEX IF NOT EXISTS {SECTION_INDEX}" in normalized
    assert "ON document_sections (document_id, section_index)" in normalized


@pytest.mark.asyncio
async def test_database_rejects_two_active_jobs_of_same_type(db_session):
    user, document = await _create_user_and_document(
        db_session, email="single-owner-active@example.com"
    )
    db_session.add(
        AIGenerationJob(
            user_id=user.id,
            document_id=document.id,
            job_type="full_document",
            status="queued",
        )
    )
    await db_session.commit()

    db_session.add(
        AIGenerationJob(
            user_id=user.id,
            document_id=document.id,
            job_type="full_document",
            status="running",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_database_allows_job_history_after_active_job_finishes(db_session):
    user, document = await _create_user_and_document(
        db_session, email="single-owner-history@example.com"
    )
    db_session.add_all(
        [
            AIGenerationJob(
                user_id=user.id,
                document_id=document.id,
                job_type="full_document",
                status="completed",
            ),
            AIGenerationJob(
                user_id=user.id,
                document_id=document.id,
                job_type="full_document",
                status="failed",
            ),
        ]
    )

    await db_session.commit()


@pytest.mark.asyncio
async def test_database_rejects_duplicate_document_section_index(db_session):
    _, document = await _create_user_and_document(
        db_session, email="unique-section-index@example.com"
    )
    db_session.add(
        DocumentSection(
            document_id=document.id,
            title="Introduzione",
            section_index=1,
        )
    )
    await db_session.commit()
    db_session.add(
        DocumentSection(
            document_id=document.id,
            title="Duplicate introduction",
            section_index=1,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarsResult:
    """Empty scalars() result — e.g. the uploaded-sources digest query."""

    def __init__(self, values=()):
        self._values = list(values)

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


def _generation_handler():
    return getattr(
        generate_endpoint.generate_full_document,
        "__wrapped__",
        generate_endpoint.generate_full_document,
    )


@pytest.mark.asyncio
async def test_generation_rejects_user_with_pending_deletion_before_document_lock(
    monkeypatch,
):
    current_user = User(id=7, email="deleting@example.com")
    current_user.deletion_requested_at = datetime.utcnow()
    document = Document(
        id=15,
        user_id=7,
        title="Deletion race",
        topic="Concurrency",
        status="draft",
    )
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_ScalarResult(current_user)])
    db.commit = AsyncMock()

    monkeypatch.setattr(
        generate_endpoint.DocumentService,
        "check_document_ownership",
        AsyncMock(return_value=document),
    )

    with pytest.raises(HTTPException) as exc_info:
        await _generation_handler()(
            request=Request({"type": "http", "method": "POST", "path": "/"}),
            req_data=AsyncGenerationRequest(document_id=15),
            background_tasks=BackgroundTasks(),
            current_user=current_user,
            db=db,
        )

    assert exc_info.value.status_code == 409
    assert "deletion is pending" in exc_info.value.detail
    assert len(db.execute.await_args_list) == 1
    assert "FROM users" in str(db.execute.await_args_list[0].args[0])
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_request_returns_active_job_when_document_is_generating(
    monkeypatch,
):
    document = Document(
        id=16,
        user_id=7,
        title="Idempotency test",
        topic="Concurrency",
        status="generating",
    )
    active_job = AIGenerationJob(
        id=90,
        user_id=7,
        document_id=16,
        job_type="full_document",
        status="queued",
    )
    current_user = User(id=7, email="repeat@example.com")

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarResult(current_user),  # per-user quota lock
            _ScalarResult(document),
            _ScalarResult(None),  # no production case
            _ScalarResult(active_job),
        ]
    )
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    monkeypatch.setattr(
        generate_endpoint.DocumentService,
        "check_document_ownership",
        AsyncMock(return_value=document),
    )
    generation_gate = AsyncMock(return_value=None)
    monkeypatch.setattr(generate_endpoint, "_enforce_generation_gate", generation_gate)

    response = await _generation_handler()(
        request=Request({"type": "http", "method": "POST", "path": "/"}),
        req_data=AsyncGenerationRequest(document_id=16),
        background_tasks=BackgroundTasks(),
        current_user=current_user,
        db=db,
    )

    assert response.job_id == 90
    assert response.status == "queued"
    generation_gate.assert_not_awaited()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_race_returns_competing_active_job(monkeypatch):
    document = Document(
        id=17,
        user_id=7,
        title="Race test",
        topic="Concurrency",
        status="draft",
        ai_provider="anthropic",
        ai_model="claude-opus-4-8",
    )
    competing_job = AIGenerationJob(
        id=91,
        user_id=7,
        document_id=17,
        job_type="full_document",
        status="running",
        progress=25,
    )
    production_case = ProductionCase(
        id=191,
        document_id=17,
        client_user_id=7,
        citation_style="apa",
    )
    current_user = User(id=7, email="race@example.com")

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarResult(current_user),
            _ScalarResult(document),
            _ScalarResult(production_case),
            _ScalarResult(None),
            _ScalarsResult([]),  # uploaded-sources blockers (no uploads)
            _ScalarsResult([]),  # uploaded-sources digest (no uploads)
            _ScalarResult(competing_job),
        ]
    )
    db.flush = AsyncMock(
        side_effect=IntegrityError(
            "INSERT INTO ai_generation_jobs ...", {}, Exception("duplicate key")
        )
    )
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    monkeypatch.setattr(
        generate_endpoint.DocumentService,
        "check_document_ownership",
        AsyncMock(return_value=document),
    )
    monkeypatch.setattr(
        generate_endpoint, "_enforce_generation_gate", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        generate_endpoint,
        "_invalidate_previous_generation_evidence",
        AsyncMock(return_value=None),
    )

    background_tasks = BackgroundTasks()
    request = Request({"type": "http", "method": "POST", "path": "/"})

    response = await _generation_handler()(
        request=request,
        req_data=AsyncGenerationRequest(document_id=17),
        background_tasks=background_tasks,
        current_user=current_user,
        db=db,
    )

    assert response.job_id == 91
    assert response.status == "running"
    assert response.check_url == "/api/v1/jobs/91/status"
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    assert background_tasks.tasks == []


@pytest.mark.asyncio
async def test_generation_locks_shared_user_budget_then_rereads_case(monkeypatch):
    """Different documents share the user lock; case requirements cannot race it."""
    document = Document(
        id=18,
        user_id=7,
        title="Quota and case lock test",
        topic="Concurrency",
        status="draft",
        target_pages=1,
        ai_provider="anthropic",
        ai_model="claude-opus-4-8",
    )
    production_case = ProductionCase(
        id=44,
        document_id=18,
        client_user_id=7,
        citation_style="apa",
        requirements_text="Follow the locked university methodology.",
    )
    current_user = User(id=7, email="quota-lock@example.com")

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarResult(current_user),
            _ScalarResult(document),
            _ScalarResult(production_case),
            _ScalarResult(None),
            _ScalarsResult([]),  # uploaded-sources blockers (no uploads)
            _ScalarsResult([]),  # uploaded-sources digest (no uploads)
        ]
    )
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)

    async def _flush() -> None:
        job = next(item for item in added if isinstance(item, AIGenerationJob))
        job.id = 92

    db.flush = AsyncMock(side_effect=_flush)
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    monkeypatch.setattr(
        generate_endpoint.DocumentService,
        "check_document_ownership",
        AsyncMock(return_value=document),
    )
    monkeypatch.setattr(
        generate_endpoint, "_enforce_generation_gate", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        generate_endpoint,
        "_invalidate_previous_generation_evidence",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(generate_endpoint.settings, "MVP_FREE_GENERATION_ENABLED", True)

    response = await _generation_handler()(
        request=Request({"type": "http", "method": "POST", "path": "/"}),
        req_data=AsyncGenerationRequest(
            document_id=18,
            requirements="Add a one-page executive summary.",
        ),
        background_tasks=BackgroundTasks(),
        current_user=current_user,
        db=db,
    )

    statements = [str(call.args[0]) for call in db.execute.await_args_list[:4]]
    assert "FROM users" in statements[0]
    assert "FOR UPDATE" in statements[0]
    assert "FROM documents" in statements[1]
    assert "FOR UPDATE" in statements[1]
    assert "FROM production_cases" in statements[2]
    assert "FOR UPDATE" in statements[2]
    assert "FROM ai_generation_jobs" in statements[3]

    job = next(item for item in added if isinstance(item, AIGenerationJob))
    requirements = job.request_payload["additional_requirements"]
    assert "Follow the locked university methodology." in requirements
    assert "Add a one-page executive summary." in requirements
    assert response.job_id == 92
    db.commit.assert_awaited_once()
