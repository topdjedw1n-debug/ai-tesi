"""Real cancel for generation jobs: terminal, fenced, non-resurrectable."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request

from app.api.v1.endpoints import generate as generate_endpoint
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentSection,
    ProductionCase,
)
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_worker import (
    GenerationLeaseLostError,
    cancel_active_generation_job,
    claim_next_generation_job,
    persist_generation_section,
    reschedule_or_fail_generation_job,
    write_generation_usage_monotonic,
)


async def _seed_cancellable_job(
    db_session,
    *,
    email: str,
    with_release: bool = False,
) -> tuple[Document, AIGenerationJob, ProductionCase]:
    user = User(email=email, full_name="Cancel Test", is_active=True)
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Cancellable generation",
        topic="Cancelling a long-running academic generation",
        status="generating",
        additional_requirements="Extracted UNIBO methodology text",
        requirements_file_processed=True,
        citation_style="apa",
    )
    db_session.add(document)
    await db_session.flush()
    production_case = ProductionCase(
        document_id=document.id,
        client_user_id=user.id,
        citation_style="apa",
    )
    if with_release:
        production_case.release_status = "released"
        production_case.released_docx_path = "documents/old.docx"
        production_case.released_docx_sha256 = "a" * 64
    db_session.add(production_case)
    await db_session.flush()
    run_requirements = "Use the persisted methodic"
    job = AIGenerationJob(
        user_id=user.id,
        document_id=document.id,
        job_type="full_document",
        status="queued",
        attempt_count=0,
        max_attempts=3,
        request_payload={
            "additional_requirements": run_requirements,
            "generation_contract_sha256": generation_contract_sha256(
                document, production_case, run_requirements
            ),
        },
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return document, job, production_case


@pytest.mark.asyncio
async def test_cancel_queued_job_is_terminal(db_session):
    """A cancelled queued job is never claimed again and fails the document."""
    document, job, case = await _seed_cancellable_job(
        db_session, email="cancel-queued@example.com", with_release=True
    )

    cancelled_id = await cancel_active_generation_job(
        db_session, document_id=int(document.id), cancelled_by="user:1"
    )
    assert cancelled_id == job.id

    await db_session.refresh(job)
    assert job.status == "cancelled"
    assert job.success is False
    assert "Cancelled by user:1" in (job.error_message or "")
    assert job.lease_owner is None
    assert job.lease_token is None

    await db_session.refresh(document)
    assert document.status == "failed"

    await db_session.refresh(case)
    assert case.release_status == "blocked"
    assert case.released_docx_path is None
    assert case.released_docx_sha256 is None

    # The claim path must not resurrect the cancelled row.
    claimed = await claim_next_generation_job(db_session, worker_id="worker-b")
    assert claimed is None


@pytest.mark.asyncio
async def test_cancel_running_job_fences_stale_owner(db_session):
    """Cancelling a running job revokes the lease: the still-alive executor
    loses every fenced write and its retry path reports the lease as lost."""
    document, job, _case = await _seed_cancellable_job(
        db_session, email="cancel-running@example.com"
    )
    document_id = int(document.id)
    job_id = int(job.id)

    claimed = await claim_next_generation_job(db_session, worker_id="worker-a")
    assert claimed is not None and claimed.id == job_id

    cancelled_id = await cancel_active_generation_job(
        db_session, document_id=document_id, cancelled_by="user:1"
    )
    assert cancelled_id == job_id

    with pytest.raises(GenerationLeaseLostError):
        await persist_generation_section(
            db_session,
            job_id=claimed.id,
            worker_id=claimed.lease_owner,
            lease_token=claimed.lease_token,
            document_id=document_id,
            section_index=0,
            values={
                "title": "Introduzione",
                "content": "Testo della sezione.",
                "word_count": 3,
                "status": "completed",
            },
        )

    sections = (
        (
            await db_session.execute(
                select(DocumentSection).where(
                    DocumentSection.document_id == document_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert sections == []

    decision = await reschedule_or_fail_generation_job(
        db_session,
        job_id=claimed.id,
        worker_id=claimed.lease_owner,
        lease_token=claimed.lease_token,
        error=RuntimeError("executor noticed the revoked lease"),
        terminal=False,
    )
    assert decision == "lost"

    job_status = (
        await db_session.execute(
            select(AIGenerationJob.status).where(AIGenerationJob.id == job_id)
        )
    ).scalar_one()
    assert job_status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_without_active_job_returns_none(db_session):
    user = User(email="cancel-none@example.com", full_name="No Job", is_active=True)
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id, title="Idle", topic="No active job", status="draft"
    )
    db_session.add(document)
    await db_session.commit()

    cancelled_id = await cancel_active_generation_job(
        db_session, document_id=int(document.id), cancelled_by="user:1"
    )
    assert cancelled_id is None


def _cancel_handler():
    return getattr(
        generate_endpoint.cancel_full_document_generation,
        "__wrapped__",
        generate_endpoint.cancel_full_document_generation,
    )


def _http_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/"})


@pytest.mark.asyncio
async def test_cancel_endpoint_conflict_when_no_active_job(monkeypatch):
    current_user = User(id=7, email="cancel-endpoint@example.com")
    monkeypatch.setattr(
        generate_endpoint.DocumentService,
        "check_document_ownership",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        generate_endpoint,
        "cancel_active_generation_job",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await _cancel_handler()(
            request=_http_request(),
            document_id=15,
            current_user=current_user,
            db=MagicMock(),
        )

    assert exc_info.value.status_code == 409
    assert "No active generation job" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cancel_endpoint_returns_cancelled_job(monkeypatch):
    current_user = User(id=7, email="cancel-endpoint-ok@example.com")
    monkeypatch.setattr(
        generate_endpoint.DocumentService,
        "check_document_ownership",
        AsyncMock(return_value=None),
    )
    cancel_mock = AsyncMock(return_value=42)
    monkeypatch.setattr(generate_endpoint, "cancel_active_generation_job", cancel_mock)

    response = await _cancel_handler()(
        request=_http_request(),
        document_id=15,
        current_user=current_user,
        db=MagicMock(),
    )

    assert response == {
        "job_id": 42,
        "status": "cancelled",
        "document_status": "failed",
    }
    cancel_mock.assert_awaited_once()
    assert cancel_mock.await_args.kwargs["document_id"] == 15
    assert cancel_mock.await_args.kwargs["cancelled_by"] == "user:7"


@pytest.mark.asyncio
async def test_cancelled_job_still_accounts_in_flight_spend(db_session):
    """GPT audit 2026-07-10: tokens spent on the in-flight section must not
    vanish when the run is cancelled — the fenced usage write matches zero
    rows after cancel, so the monotonic variant must land the spend."""
    document, job, _case = await _seed_cancellable_job(
        db_session, email="cancel-spend@example.com"
    )
    document_id = int(document.id)
    job_id = int(job.id)

    claimed = await claim_next_generation_job(db_session, worker_id="worker-a")
    assert claimed is not None

    cancelled_id = await cancel_active_generation_job(
        db_session, document_id=document_id, cancelled_by="user:1"
    )
    assert cancelled_id == job_id

    # The dying executor persists what it already spent on the unfinished
    # section — keyed by job id alone, no lease required.
    advanced = await write_generation_usage_monotonic(
        db_session, job_id=job_id, total_tokens=1234, cost_cents=7
    )
    assert advanced is True

    row = (
        await db_session.execute(
            select(
                AIGenerationJob.status,
                AIGenerationJob.total_tokens,
                AIGenerationJob.cost_cents,
            ).where(AIGenerationJob.id == job_id)
        )
    ).one()
    assert row.status == "cancelled"
    assert row.total_tokens == 1234
    assert row.cost_cents == 7


@pytest.mark.asyncio
async def test_monotonic_usage_never_decreases(db_session):
    """A replacement owner's larger totals must never be clobbered."""
    document, job, _case = await _seed_cancellable_job(
        db_session, email="cancel-monotonic@example.com"
    )
    job_id = int(job.id)

    assert await write_generation_usage_monotonic(
        db_session, job_id=job_id, total_tokens=2000, cost_cents=11
    )
    # A stale, smaller write must be a no-op.
    assert not await write_generation_usage_monotonic(
        db_session, job_id=job_id, total_tokens=1500, cost_cents=8
    )

    row = (
        await db_session.execute(
            select(AIGenerationJob.total_tokens, AIGenerationJob.cost_cents).where(
                AIGenerationJob.id == job_id
            )
        )
    ).one()
    assert row.total_tokens == 2000
    assert row.cost_cents == 11


def test_pipeline_wires_monotonic_usage_on_cancel_paths():
    """Pin the wiring: the pipeline's CancelledError handler and the
    lease-lost failure branch must use the monotonic writer (the fenced one
    silently drops the spend there)."""
    import inspect

    from app.services import background_jobs as bj

    # The pipeline lives in generate_full_document; generate_full_document_async
    # is the durable-worker wrapper whose own CancelledError handler releases
    # the lease AFTER the pipeline's handler has persisted the spend.
    source = inspect.getsource(bj.BackgroundJobService.generate_full_document)
    cancel_block = source.split("except asyncio.CancelledError:")[1].split(
        "except Exception as e:"
    )[0]
    assert "write_job_usage_monotonic" in cancel_block

    # The generic failure handler is the LAST `except Exception as e:` in the
    # pipeline (earlier ones handle outline/section-local failures).
    failure_block = source.rsplit("except Exception as e:", 1)[1]
    assert "isinstance(e, GenerationLeaseLostError)" in failure_block
    assert "write_job_usage_monotonic" in failure_block
