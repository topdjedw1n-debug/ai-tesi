"""The v2 specification's closed vocabulary, recording and offline execution contract."""

import ast
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    DocumentSection,
    ProductionCase,
)
from app.services.executor_v2.budgets import POLICY, model_call
from app.services.executor_v2.run import Context, prepare
from app.services.executor_v2.warnings import (
    STOP_CODES,
    WARNING_CODES,
    ExecutionStop,
    status_fields,
)
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_operations import journal_usage
from app.services.generation_policy import RecordingPersistenceError
from app.services.generation_worker import (
    cancel_active_generation_job,
    claim_next_generation_job,
    complete_generation_job,
)
from app.services.replay_dependencies import recording_context
from app.services.task_contract import task_contract_sha256

PACKAGE = Path(__file__).parents[1] / "app/services/executor_v2"
NODES = [
    {
        "title": "Sleep",
        "required": True,
        "terms_local": ["sonno"],
        "terms_en": ["sleep"],
        "children": [],
    }
]
PLAN = {
    "sections": [
        {
            "title": "Sleep",
            "purpose": "Explain sleep",
            "main_points": ["Compare evidence"],
            "scope_ids": ["scope-1"],
            "evidence_keys": [],
            "target_words": 500,
        }
    ]
}


def response(text, truncated=False):
    return SimpleNamespace(
        id=str(uuid4()),
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="max_tokens" if truncated else "end_turn",
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    async def denied(*args, **kwargs):
        raise AssertionError("Offline tests must never use HTTP")

    monkeypatch.setattr(httpx.AsyncClient, "send", denied)


async def seed(db, *, requirements="", confirmed=True):
    user = User(email=f"executor-{uuid4().hex}@example.test", is_active=True)
    db.add(user)
    await db.flush()
    doc = Document(
        user_id=user.id,
        title="Sleep",
        topic="Sleep in nursing",
        work_type="tesi_magistrale",
        language="it",
        target_pages=2,
        citation_style="apa",
        status="queued",
        additional_requirements=requirements,
        requirements_file_processed=False,
    )
    db.add(doc)
    await db.flush()
    if confirmed:
        doc.contract_confirmed_sha256 = task_contract_sha256(doc)
    case = ProductionCase(
        document_id=doc.id,
        client_user_id=user.id,
        citation_style="apa",
        generation_status="queued",
    )
    db.add(case)
    await db.flush()
    payload = {
        "executor_version": 2,
        "additional_requirements": requirements,
        "generation_contract_sha256": generation_contract_sha256(
            doc, case, requirements
        ),
    }
    row = AIGenerationJob(
        user_id=user.id,
        document_id=doc.id,
        job_type="full_document",
        ai_provider="anthropic",
        ai_model=POLICY["model"],
        status="queued",
        request_payload=payload,
        max_attempts=1,
    )
    db.add(row)
    await db.commit()
    claimed = await claim_next_generation_job(
        db, worker_id="offline", lease_seconds=300
    )
    assert claimed is not None
    return claimed, user, doc, case


def mock_sources(monkeypatch, *, readable=True):
    from app.services.executor_v2 import sources

    # Mock the adapter under its recorder: dependency records still persist.
    async def search_impl(provider, query):
        return [
            {
                "title": f"Sleep evidence {i}",
                "authors": ["Rossi, Maria"],
                "year": 2024,
                "doi": f"10.1234/sleep{i}",
                "abstract": "Sleep nursing findings." if readable else None,
                "provider": provider,
            }
            for i in (1, 2)
        ]

    async def verify_impl(candidate):
        return {**candidate, "status": "verified", "provider": "crossref"}

    from app.services.replay_dependencies import recorded_dependency

    monkeypatch.setattr(
        sources, "search", recorded_dependency("executor_search")(search_impl)
    )
    monkeypatch.setattr(
        sources, "verify", recorded_dependency("executor_verify")(verify_impl)
    )


def test_spec_guardrails():
    assert 0 < POLICY["heartbeat_seconds"] <= 60
    files = list(PACKAGE.glob("*.py"))
    assert sum(len(p.read_text().splitlines()) for p in files) <= 1500
    for path in files:
        tree = ast.parse(path.read_text())
        for n in ast.walk(tree):
            assert not (
                isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id == "settings"
                and n.attr.endswith("_ENABLED")
            )
            assert not (
                isinstance(n, ast.If) and ast.unparse(n.test).startswith("settings.")
            )
    assert STOP_CODES == {
        "provider_access",
        "provider_unusable_response",
        "storage_or_db",
    }
    assert set(WARNING_CODES) == {
        "source_coverage_gap",
        "source_no_readable_text",
        "standard_reference_used",
        "outline_scope_unmapped",
        "output_truncated_retried",
        "citation_unresolved",
        "length_off_target",
        "reference_replaced",
        "review_negative",
        "review_note",
        "detector_unchecked",
        "placeholder_text",
    }
    from app.services.background_jobs import BackgroundJobService

    assert not hasattr(BackgroundJobService, "generate_full_document")


@pytest.mark.asyncio
async def test_s1_s3_recorded_truncation_and_coverage(db_session, monkeypatch):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.provider = AsyncMock(
        side_effect=[
            response(json.dumps({"nodes": NODES})),
            response('{"sections":', True),
            response(json.dumps(PLAN)),
        ]
    )
    mock_sources(monkeypatch, readable=False)
    token = recording_context.set(ctx.recording)
    try:
        pack, outline = await prepare(ctx)
    finally:
        recording_context.reset(token)
    assert len(pack.sources) == 2
    assert sum(s["target_words"] for s in outline) == 500
    assert [s["section_index"] for s in outline] == [1]
    assert {
        "source_coverage_gap",
        "source_no_readable_text",
        "output_truncated_retried",
    } <= {w["code"] for w in ctx.warnings}
    assert ctx.provider.await_args_list[-1].kwargs["max_tokens"] == 16000
    events = list((await db_session.execute(select(DocumentProvenance))).scalars())
    assert (
        len([e for e in events if e.event_type == "generation_provider_attempt"]) == 6
    )
    assert {
        e.payload["step"] for e in events if e.event_type == "executor_step_completed"
    } == {"S1", "S2", "S3"}
    totals, unknown = await journal_usage(db_session, claimed.document_id, claimed.id)
    assert totals.total_tokens == 450 and unknown == 0
    db_session.expire_all()
    row = await db_session.get(AIGenerationJob, claimed.id)
    assert status_fields(row)["sections_total"] == 1


@pytest.mark.asyncio
async def test_completion_without_recording_rejected(db_session):
    claimed, _, _, _ = await seed(db_session)
    with pytest.raises(RecordingPersistenceError):
        await complete_generation_job(
            db_session,
            job_id=claimed.id,
            worker_id=claimed.lease_owner,
            lease_token=claimed.lease_token,
        )
    await db_session.rollback()
    row = await db_session.get(AIGenerationJob, claimed.id)
    assert row.status == "running"


@pytest.mark.asyncio
async def test_cancel_during_held_provider_records_late_reply_without_section(
    db_session,
):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    entered, release = asyncio.Event(), asyncio.Event()

    async def held(**request):
        entered.set()
        await release.wait()
        return response("late text")

    ctx.provider = held
    task = asyncio.create_task(
        model_call(ctx, "brief", budget=1000, purpose="S4", section_index=1)
    )
    await asyncio.wait_for(entered.wait(), timeout=2)
    await asyncio.wait_for(
        cancel_active_generation_job(
            db_session, document_id=claimed.document_id, cancelled_by="test"
        ),
        timeout=2,
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    from app.services.executor_v2.budgets import _PENDING

    await asyncio.gather(*list(_PENDING))
    db_session.expire_all()
    row = await db_session.get(AIGenerationJob, claimed.id)
    doc = await db_session.get(Document, claimed.document_id)
    assert row.status == doc.status == "cancelled"
    assert row.error_message is None
    assert not list((await db_session.execute(select(DocumentSection))).scalars())
    receipts = list(
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "generation_provider_attempt"
                )
            )
        ).scalars()
    )
    assert [e.payload["outcome"] for e in receipts] == ["started", "received"]


@pytest.mark.asyncio
async def test_active_duplicate_is_409_even_same_intent(db_session):
    from fastapi import HTTPException

    from app.api.v1.endpoints.generate import enqueue_full_document
    from app.schemas.document import AsyncGenerationRequest

    claimed, user, _, _ = await seed(db_session)
    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            await enqueue_full_document(
                AsyncGenerationRequest(
                    document_id=claimed.document_id, intent_id="identical-intent"
                ),
                user,
                db_session,
            )
        assert error.value.status_code == 409
        await db_session.rollback()
        user = await db_session.get(User, claimed.user_id)
    assert len(list((await db_session.execute(select(AIGenerationJob))).scalars())) == 1


@pytest.mark.asyncio
async def test_methodology_does_not_bypass_confirmation(db_session):
    from fastapi import HTTPException

    from app.api.v1.endpoints.generate import _enforce_generation_gate
    from app.services.task_contract import contract_confirmation_error

    doc = Document(
        topic="Sleep in nursing",
        work_type="tesi_magistrale",
        language="it",
        target_pages=2,
        citation_style="apa",
        requirements_file_processed=True,
        additional_requirements="Methodology text",
    )
    assert contract_confirmation_error(doc)
    with pytest.raises(HTTPException) as error:
        await _enforce_generation_gate(db_session, doc, 1)
    assert error.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_kind", ["cancelled", "provider_access", "internal_error"]
)
async def test_new_attempt_snapshots_previous_materials(
    db_session, monkeypatch, terminal_kind
):
    from app.api.v1.endpoints import generate
    from app.models.document import DocumentSource
    from app.schemas.document import AsyncGenerationRequest
    from app.services.generation_recovery import terminal_fingerprint

    claimed, user, doc, _ = await seed(db_session)
    if terminal_kind == "cancelled":
        await cancel_active_generation_job(
            db_session, document_id=claimed.document_id, cancelled_by="test"
        )
    else:
        from app.services.generation_worker import fail_executor_job

        await fail_executor_job(
            db_session,
            **Context(claimed).fence,
            stop=ExecutionStop(terminal_kind, "Власник має відновити доступ.").stop,
        )

    row = await db_session.get(AIGenerationJob, claimed.id)
    await db_session.refresh(row)
    doc = await db_session.get(Document, claimed.document_id)
    await db_session.refresh(doc)
    doc.outline = {"sections": [{"title": "Previous plan"}]}
    db_session.add(
        DocumentSection(
            document_id=doc.id,
            section_index=1,
            title="Previous",
            content="Preserve this exact text.",
            word_count=4,
            status="completed",
        )
    )
    db_session.add(
        DocumentSource(
            document_id=doc.id,
            title="Previous source",
            authors=["Rossi"],
            verification_status="verified",
        )
    )
    await db_session.commit()
    old = {c.name: copy.deepcopy(getattr(row, c.name)) for c in row.__table__.columns}
    fingerprint = terminal_fingerprint(row)
    monkeypatch.setattr(generate, "_enforce_generation_gate", AsyncMock())
    result = await generate.enqueue_full_document(
        AsyncGenerationRequest(
            document_id=doc.id,
            mode="new_version",
            confirm_replace=True,
            intent_id="replacement-1",
            replacement_reason="Retry cancelled work",
            expected_fingerprint=fingerprint,
        ),
        user,
        db_session,
    )
    assert result.job_id != claimed.id
    db_session.expire_all()
    previous = await db_session.get(AIGenerationJob, claimed.id)
    assert {
        c.name: getattr(previous, c.name) for c in previous.__table__.columns
    } == old
    snapshot = (
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "generation_previous_snapshot"
                )
            )
        )
        .scalar_one()
        .payload
    )
    assert snapshot["previous_job_id"] == claimed.id
    assert snapshot["sections"][0]["content"] == "Preserve this exact text."
    assert snapshot["sources"][0]["title"] == "Previous source"
    assert snapshot["outline"]["sections"][0]["title"] == "Previous plan"
    new = await db_session.get(AIGenerationJob, result.job_id)
    assert new.status == "queued" and new.ai_model == POLICY["model"]
    assert (await db_session.get(Document, claimed.document_id)).status == "queued"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text, expected_placeholder",
    [
        ("Da   verificare.", "da   verificare"),
        ("La fonte è SOGGETTA A VERIFICA.", "soggetta a verifica"),
        ("An editorial [citation needed] remains.", "[citation needed]"),
        ("[TODO]: finish the text.", "todo"),
        (
            "La letteratura disponibile non consente di stabilire un nesso causale. Metodo e metodologia.",
            None,
        ),
    ],
)
async def test_offline_docx_warnings_and_exact_replay(
    db_session, monkeypatch, tmp_path, text, expected_placeholder
):
    from datetime import timedelta
    from io import BytesIO
    from zipfile import ZipFile

    from app.services.academic_context import digest
    from app.services.executor_v2.run import run
    from app.services.generation_worker import ClaimedGenerationJob, utc_now
    from app.services.model_recording import ReplayTape, replay_models
    from app.services.replay_snapshot import row_data
    from app.services.storage_service import StorageService

    claimed, _, _, _ = await seed(db_session)
    mock_sources(monkeypatch)
    key = (
        "K"
        + digest({"doi": "10.1234/sleep1", "title": "Sleep evidence 1", "year": 2024})[
            :12
        ]
    )
    plan = copy.deepcopy(PLAN)
    plan["sections"][0]["evidence_keys"] = [key]
    replies = [
        response(json.dumps({"nodes": NODES})),
        response('{"sections":', True),
        response(json.dumps(plan)),
        response(
            f"# Sleep\n\nEvidence **supports** a finding [{key}]. Unsupported marker [UNKNOWN] and [STD:D.M.739/1994]. {text}"
        ),
        response('{"verdict":"FAIL","notes":"Section is short."}'),
    ]

    async def provider(self, **request):
        if len(replies) == 2:
            prompt = request["messages"][0]["content"]
            assert "Never include editorial placeholders" in prompt
            assert "la letteratura disponibile non consente di" in prompt
            assert all(phrase in prompt for phrase in POLICY["placeholder_phrases"])
        return replies.pop(0)

    monkeypatch.setattr(Context, "provider", provider)
    artifacts = []

    async def upload(self, name, data, content_type):
        artifacts.append(data)
        return "s3://local-test/" + name

    monkeypatch.setattr(StorageService, "upload_file", upload)
    result = await asyncio.wait_for(run(claimed), timeout=5)
    db_session.expire_all()
    row = await db_session.get(AIGenerationJob, claimed.id)
    assert row.status == "completed", row.request_payload
    assert result is not None
    placeholders = [w for w in result["warnings"] if w["code"] == "placeholder_text"]
    if expected_placeholder:
        assert len(placeholders) == 1
        assert placeholders[0]["detail"] == expected_placeholder
        assert placeholders[0]["stage"] == "assembling"
        assert placeholders[0]["section_index"] == 1
        assert (
            placeholders[0]["severity"] == "warning" and placeholders[0]["message_uk"]
        )
    else:
        assert placeholders == []
    assert set(result) == {
        "docx",
        "sections",
        "bibliography",
        "sources",
        "usage",
        "recording_id",
        "warnings",
    }
    assert {
        "output_truncated_retried",
        "citation_unresolved",
        "length_off_target",
        "review_negative",
    } <= {w["code"] for w in result["warnings"]}
    assert result["bibliography"][0]["verified"] is True
    assert result["bibliography"][0]["verification_provider"] == "crossref"
    assert len(result["usage"]["calls"]) == 5
    with ZipFile(BytesIO(artifacts[0])) as docx:
        xml = docx.read("word/document.xml").decode()
        assert (
            "[UNKNOWN]" not in xml
            and "[STD:" not in xml
            and key not in xml
            and "**supports**" not in xml
        )
        assert "Rossi" in xml
    (tmp_path / "offline.docx").write_bytes(artifacts[0])
    events = [
        row_data(e)
        for e in (await db_session.execute(select(DocumentProvenance))).scalars()
    ]
    tape = ReplayTape.from_events(events, job_id=claimed.id)

    # Replay happens on an isolated test DB; recorded calls/dependencies are
    # copied from this first run and the model/network transports are forbidden.
    async def forbidden(self, **request):
        raise AssertionError("Replay contacted the model")

    monkeypatch.setattr(Context, "provider", forbidden)
    row.status = "running"
    row.lease_owner = "replay"
    row.lease_token = "replay-token"
    row.lease_expires_at = utc_now() + timedelta(seconds=300)
    row.request_payload = {**row.request_payload, "execution": {}}
    await db_session.commit()
    replay_job = ClaimedGenerationJob(
        claimed.id,
        claimed.document_id,
        claimed.user_id,
        "replay",
        "replay-token",
        1,
        1,
        claimed.request_payload,
    )
    with replay_models(tape):
        replayed = await asyncio.wait_for(run(replay_job), timeout=5)
        tape.assert_complete()
    assert replayed is not None
    assert artifacts[0] == artifacts[1]
    assert result["docx"]["sha256"] == replayed["docx"]["sha256"]
    assert [
        (w["section_index"], w["detail"])
        for w in replayed["warnings"]
        if w["code"] == "placeholder_text"
    ] == [(w["section_index"], w["detail"]) for w in placeholders]


@pytest.mark.asyncio
async def test_search_transport_failure_warns_and_continues(db_session, monkeypatch):
    from app.services.executor_v2 import sources
    from app.services.replay_dependencies import recorded_dependency

    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.provider = AsyncMock(
        side_effect=[response(json.dumps({"nodes": NODES})), response(json.dumps(PLAN))]
    )

    async def failed(provider, query):
        raise httpx.ConnectError("Recorded outage")

    monkeypatch.setattr(
        sources, "search", recorded_dependency("executor_search")(failed)
    )
    token = recording_context.set(ctx.recording)
    try:
        pack, outline = await prepare(ctx)
    finally:
        recording_context.reset(token)
    assert not pack.sources and outline
    assert ctx.warnings[0]["code"] == "source_coverage_gap"


def test_missing_year_and_institutional_author_apa():
    from app.services.ai_pipeline.citation_formatter import (
        CitationFormatter,
        SourceDocument,
    )

    assert (
        CitationFormatter.format_intext(["World Health Organization"], None)
        == "(World Health Organization, n.d.)"
    )
    assert (
        CitationFormatter.format_intext(
            ["Rossi, Maria", "Bianchi, Anna", "Verdi, Luca"], None
        )
        == "(Rossi et al., n.d.)"
    )
    assert "World Health Organization (n.d.)." in CitationFormatter.format_reference(
        SourceDocument(
            title="Guideline", authors=["World Health Organization"], year=None
        )
    )


@pytest.mark.asyncio
async def test_run_cancels_held_writer_and_records_late_receipt(
    db_session, monkeypatch
):
    import time

    from app.services.executor_v2.budgets import _PENDING
    from app.services.executor_v2.run import run

    claimed, _, _, case = await seed(db_session)
    case_id = case.id
    mock_sources(monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()
    replies = [response(json.dumps({"nodes": NODES})), response(json.dumps(PLAN))]

    async def provider(self, **request):
        if replies:
            return replies.pop(0)
        entered.set()
        await release.wait()
        return response("Late writer result must never become a section.")

    monkeypatch.setattr(Context, "provider", provider)
    monkeypatch.setitem(POLICY, "heartbeat_seconds", 0.05)
    task = asyncio.create_task(run(claimed))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        started = time.monotonic()
        await cancel_active_generation_job(
            db_session, document_id=claimed.document_id, cancelled_by="manager"
        )
        assert await asyncio.wait_for(task, timeout=2) is None
        assert time.monotonic() - started < 60
        assert not release.is_set()
    finally:
        release.set()
        await asyncio.gather(*list(_PENDING), return_exceptions=True)
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    db_session.expire_all()
    job = await db_session.get(AIGenerationJob, claimed.id)
    assert (
        job.status
        == (await db_session.get(Document, claimed.document_id)).status
        == "cancelled"
    )
    assert (
        await db_session.get(ProductionCase, case_id)
    ).generation_status == "cancelled"
    assert status_fields(job)["stop"] is None and job.error_message is None
    assert not list((await db_session.execute(select(DocumentSection))).scalars())
    events = list(
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.event_type == "generation_provider_attempt"
                )
            )
        ).scalars()
    )
    assert len(events) == 6 and events[-1].payload["outcome"] == "received"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure, expected, attempts",
    [
        ("access", "provider_access", 1),
        ("temporary", "provider_unusable_response", 3),
        ("recording", "storage_or_db", 0),
        ("bug", "internal_error", 0),
    ],
)
async def test_run_technical_stops_and_case_projection(
    db_session, monkeypatch, failure, expected, attempts
):
    import anthropic

    from app.services.executor_v2 import budgets
    from app.services.executor_v2.run import run

    claimed, _, _, case = await seed(db_session)
    case_id = case.id
    calls = []

    async def provider(self, **request):
        calls.append(request)
        code = 401 if failure == "access" else 429
        raise anthropic.APIStatusError(
            "recorded transport error",
            response=httpx.Response(
                code, request=httpx.Request("POST", "https://offline.invalid")
            ),
            body={},
        )

    monkeypatch.setattr(Context, "provider", provider)
    monkeypatch.setitem(POLICY, "retry_seconds", (0, 0, 0))
    terminal_writes = []
    if failure == "recording":
        import importlib

        runner = importlib.import_module("app.services.executor_v2.run")
        persist_stop = runner.fail_executor_job

        async def transient_recording_failure(*args, **kwargs):
            terminal_writes.append(kwargs["stop"]["code"])
            if len(terminal_writes) == 1:
                raise RecordingPersistenceError(
                    "Terminal receipt temporarily unavailable"
                )
            return await persist_stop(*args, **kwargs)

        monkeypatch.setattr(runner, "fail_executor_job", transient_recording_failure)

        async def broken(*args, **kwargs):
            raise RecordingPersistenceError("No durable request receipt")

        monkeypatch.setattr(budgets, "recorded_provider_call", broken)
    elif failure == "bug":

        async def broken(self):
            raise ValueError("a real programming defect")

        monkeypatch.setattr(Context, "initialize", broken)
    assert await asyncio.wait_for(run(claimed), timeout=5) is None
    if failure == "recording":
        assert terminal_writes == ["storage_or_db", "storage_or_db"]
    db_session.expire_all()
    job = await db_session.get(AIGenerationJob, claimed.id)
    stop = status_fields(job)["stop"]
    assert len(calls) == attempts
    assert (
        job.status
        == (await db_session.get(Document, claimed.document_id)).status
        == "failed"
    )
    assert (await db_session.get(ProductionCase, case_id)).generation_status == "failed"
    assert stop["code"] == expected and job.error_message == stop["message_uk"]
    assert stop["next_action"] == {
        "provider_access": "retry_after_owner",
        "internal_error": "contact_owner",
    }.get(expected, "retry_now")


@pytest.mark.asyncio
async def test_v2_worker_crash_has_structured_stop(db_session):
    from datetime import timedelta

    from app.services.generation_worker import fail_exhausted_generation_jobs, utc_now

    claimed, _, _, _ = await seed(db_session)
    row = await db_session.get(AIGenerationJob, claimed.id)
    row.lease_expires_at = utc_now() - timedelta(seconds=1)
    await db_session.commit()
    assert await fail_exhausted_generation_jobs(db_session) == 1
    await db_session.refresh(row)
    assert status_fields(row)["stop"]["code"] == "storage_or_db"
    assert row.error_message == status_fields(row)["stop"]["message_uk"]


@pytest.mark.asyncio
async def test_document_api_accepts_v2_terminal_and_queue_states(db_session):
    from app.schemas.document import DocumentResponse
    from app.services.document_service import DocumentService

    claimed, _, _, _ = await seed(db_session)
    await cancel_active_generation_job(
        db_session, document_id=claimed.document_id, cancelled_by="test"
    )
    doc = await db_session.get(Document, claimed.document_id)
    doc.target_pages = 3
    await db_session.commit()
    detail = await DocumentService(db_session).get_document(
        claimed.document_id, claimed.user_id
    )
    parsed = DocumentResponse.model_validate(detail)
    assert parsed.status_label == "Скасовано" and parsed.executor_version == 2
    result = await DocumentService(db_session).get_user_documents(claimed.user_id)
    assert result["documents"][0]["status_label"] == "Скасовано"


def test_nested_dependency_replay_and_missing_record():
    from app.services.model_recording import ReplayIncomplete, ReplayTape

    tape = ReplayTape(
        [],
        dependencies=[
            {
                "kind": "search",
                "input_fingerprint": "outer",
                "dependency_id": "a",
                "response": ["recorded"],
            },
            {
                "kind": "http",
                "input_fingerprint": "inner",
                "dependency_id": "b",
                "parent_dependency_id": "a",
                "response": {},
            },
        ],
    )
    assert tape.dependency("search", "outer")["response"] == ["recorded"]
    tape.assert_complete()
    with pytest.raises(ReplayIncomplete):
        tape.dependency("missing", "record")


@pytest.mark.asyncio
async def test_book_catalogue_and_who_metadata_are_verified_not_assumed(monkeypatch):
    from app.services.citation_verifier import CitationVerifier, SourceInput

    verifier = CitationVerifier(cache_enabled=False)
    book = SourceInput(
        title="Fundamentals of Nursing",
        authors=["Potter, Patricia"],
        year=2021,
        source_type="book",
    )
    fetch = AsyncMock(
        return_value=(
            "ok",
            httpx.Response(
                200,
                json={
                    "docs": [
                        {
                            "title": book.title,
                            "author_name": book.authors,
                            "first_publish_year": 2021,
                        }
                    ]
                },
            ),
        )
    )
    monkeypatch.setattr(verifier, "_fetch", fetch)
    result = await verifier.verify_catalogue(book)
    assert result.to_dict()["status"] == "verified" and result.provider == "openlibrary"
    wrong = SourceInput(
        title=book.title, authors=["An unrelated author"], year=2021, source_type="book"
    )
    assert await verifier.verify_catalogue(wrong) is None
    who = SourceInput(
        title="Newborn care guideline",
        authors=["World Health Organization"],
        year=None,
        source_type="guideline",
        url="https://www.who.int/publications/newborn",
    )
    fetch.return_value = (
        "ok",
        httpx.Response(
            200,
            text='<meta name="citation_title" content="Newborn care guideline"><meta name="citation_author" content="World Health Organization">',
        ),
    )
    result = await verifier.verify_catalogue(who)
    assert result.provider == "who" and result.year is None
    who.url = "https://who.int.attacker.invalid/publication"
    count = fetch.await_count
    assert await verifier.verify_catalogue(who) is None and fetch.await_count == count


@pytest.mark.asyncio
async def test_missing_writer_receipt_blocks_completion_after_docx(
    db_session, monkeypatch
):
    from app.services import generation_operations
    from app.services.executor_v2.run import run
    from app.services.storage_service import StorageService

    claimed, _, _, _ = await seed(db_session)
    mock_sources(monkeypatch)
    replies = [
        response(json.dumps({"nodes": NODES})),
        response(json.dumps(PLAN)),
        response("A concise section with its limitations."),
        response('{"verdict":"PASS","notes":""}'),
    ]

    async def provider(self, **request):
        return replies.pop(0)

    original = generation_operations._append

    async def lose_receipt(context, payload, **kwargs):
        if payload.get("stage") == "S4" and payload.get("outcome") == "received":
            return
        await original(context, payload, **kwargs)

    monkeypatch.setattr(Context, "provider", provider)
    monkeypatch.setattr(generation_operations, "_append", lose_receipt)
    upload = AsyncMock(return_value="s3://offline/preserved.docx")
    monkeypatch.setattr(StorageService, "upload_file", upload)
    assert await run(claimed) is None
    db_session.expire_all()
    job = await db_session.get(AIGenerationJob, claimed.id)
    doc = await db_session.get(Document, claimed.document_id)
    assert upload.await_count == 1 and doc.docx_path
    assert (
        job.status == "failed" and status_fields(job)["stop"]["code"] == "storage_or_db"
    )
