"""Recording/replay crosses the real SDK parsing and retry boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy import select

from app.models.document import DocumentProvenance
from app.services.ai_service import AIService
from app.services.cost_estimator import UsageTracker
from app.services.generation_operations import recorded_provider_call
from app.services.model_recording import (
    ReplayIncomplete,
    ReplayTape,
    json_value,
    operation_section,
    recorded_request,
    replay_models,
)
from tests.test_generation_worker import _seed_job


async def _tracker(db):
    doc, job = await _seed_job(db, email="recorded-model@example.com")
    usage = UsageTracker()
    usage.generation_context = {
        "document_id": doc.id,
        "job_id": job.id,
        "worker_attempt": 1,
    }
    return usage, job


async def _events(db):
    rows = (
        (
            await db.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.event_type == "generation_provider_attempt")
                .order_by(DocumentProvenance.id)
            )
        )
        .scalars()
        .all()
    )
    return [{"event_type": r.event_type, "payload": r.payload} for r in rows]


def _reply(text, stop="stop"):
    return SimpleNamespace(
        id="record-test",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text),
                finish_reason=stop,
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=200, completion_tokens=100, total_tokens=300
        ),
    )


@pytest.mark.asyncio
async def test_complete_unicode_request_and_rejected_response_survive_parsing(
    db_session, monkeypatch
):
    tracker, job = await _tracker(db_session)
    text = "вимога «мікробіота» " * 700
    response = _reply(text, "length")
    sdk = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=response))
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr("openai.AsyncOpenAI", MagicMock(return_value=sdk))
    monkeypatch.setattr(
        "app.services.ai_service.settings.OPENAI_API_KEY", "secret-not-in-record"
    )
    service = AIService(db_session, usage_tracker=tracker, max_retries=0)
    with pytest.raises(Exception):
        await service._call_openai("gpt-4", text)
    events = await _events(db_session)
    start, end = (e["payload"] for e in events)
    assert start["request"]["messages"][1]["content"] == text
    assert end["response"]["choices"][0]["message"]["content"] == text
    assert end["response"]["choices"][0]["finish_reason"] == "length"
    assert end["outcome"] == "received" and end["elapsed_seconds"] >= 0
    assert "secret-not-in-record" not in str(events)
    assert len(ReplayTape.from_events(events, job_id=job.id).records) == 1


@pytest.mark.asyncio
async def test_real_parser_replays_with_placeholder_and_no_sdk_call(
    db_session, monkeypatch
):
    tracker, job = await _tracker(db_session)
    sdk = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(return_value=_reply('{"answer": "neonato"}'))
            )
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr("openai.AsyncOpenAI", MagicMock(return_value=sdk))
    monkeypatch.setattr("app.services.ai_service.settings.OPENAI_API_KEY", "fixture")
    service = AIService(db_session, usage_tracker=tracker, max_retries=0)
    actual = await service._call_openai("gpt-4", "exact prompt")
    events = await _events(db_session)
    sdk.chat.completions.create.reset_mock()
    sdk.chat.completions.create.side_effect = AssertionError("Replay must not call SDK")
    monkeypatch.setattr(
        "app.services.ai_service.settings.OPENAI_API_KEY", "offline-placeholder"
    )
    tape = ReplayTape.from_events(events, job_id=job.id)
    with replay_models(tape):
        replayed = await service._call_openai("gpt-4", "exact prompt")
        tape.assert_complete()
    assert replayed == actual
    sdk.chat.completions.create.assert_not_called()
    assert await _events(db_session) == events  # historical receipt is untouched


@pytest.mark.asyncio
async def test_gap_and_changed_prompt_never_fall_back_or_claim_full_replay(db_session):
    tracker, job = await _tracker(db_session)
    request = {"messages": [{"role": "user", "content": "original"}]}
    await recorded_provider_call(
        AsyncMock(return_value=_reply("saved")),
        provider="openai",
        model="gpt-4",
        request=request,
        usage_tracker=tracker,
        purpose="review",
    )
    tape = ReplayTape.from_events(await _events(db_session), job_id=job.id)
    network = AsyncMock()
    with replay_models(tape):
        with pytest.raises(ReplayIncomplete, match="Request differs"):
            await recorded_provider_call(
                network,
                provider="openai",
                model="gpt-4",
                request={},
                usage_tracker=tracker,
                purpose="review",
            )
        with pytest.raises(ReplayIncomplete, match="not consumed"):
            tape.assert_complete()
        with pytest.raises(ReplayIncomplete, match="No model recording"):
            await recorded_provider_call(
                network,
                provider="openai",
                model="gpt-4",
                request=request,
                usage_tracker=tracker,
                purpose="section_generation",
            )
    network.assert_not_called()
    tape.allow_request_changes = True
    with replay_models(tape):
        await recorded_provider_call(
            network,
            provider="openai",
            model="gpt-4",
            request={},
            usage_tracker=tracker,
            purpose="review",
        )
    assert tape.consumed[0]["request_changed"] is True


@pytest.mark.asyncio
async def test_section_and_unknown_call_are_retained(db_session):
    tracker, job = await _tracker(db_session)
    token = operation_section.set(3)
    try:
        with pytest.raises(TimeoutError):
            await recorded_provider_call(
                AsyncMock(side_effect=TimeoutError("provider did not reply")),
                provider="anthropic",
                model="claude-opus-4-8",
                request={"system": "exact"},
                usage_tracker=tracker,
                purpose="section_generation",
            )
    finally:
        operation_section.reset(token)
    events = await _events(db_session)
    last = events[-1]["payload"]
    assert last["section_index"] == 3 and last["outcome"] == "failed"
    assert last["usage"] is None and last["error"]["type"] == "TimeoutError"
    tape = ReplayTape.from_events(events, job_id=job.id)
    assert tape.records[0]["request"] == {"system": "exact"}
    assert "response" not in tape.records[0]


def test_credentials_are_excluded_without_redacting_academic_text():
    request = {
        "api_key": "secret",
        "extra_headers": {"Authorization": "Bearer secret"},
        "messages": [{"role": "user", "content": "The API key concept"}],
        "max_tokens": 123,
    }
    assert recorded_request(request) == {
        "messages": request["messages"],
        "max_tokens": 123,
    }
    assert json_value(_reply("full"))["choices"][0]["message"]["content"] == "full"


@pytest.mark.asyncio
async def test_actual_sdk_object_and_429_replay_through_real_retry(
    db_session, monkeypatch
):
    from openai import RateLimitError
    from openai.types.chat import ChatCompletion

    tracker, job = await _tracker(db_session)
    response = ChatCompletion.model_validate(
        {
            "id": "chatcmpl-recorded",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"answer":"успіх"}'},
                }
            ],
            "usage": {
                "prompt_tokens": 210,
                "completion_tokens": 110,
                "total_tokens": 320,
            },
        }
    )
    error_response = httpx.Response(
        429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    )
    sdk = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    side_effect=[
                        RateLimitError(
                            "temporary rate limit",
                            response=error_response,
                            body={"error": {"code": "rate_limit_exceeded"}},
                        ),
                        response,
                    ]
                )
            )
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr("openai.AsyncOpenAI", MagicMock(return_value=sdk))
    monkeypatch.setattr(
        "app.services.ai_service.settings.OPENAI_API_KEY", "offline-placeholder"
    )
    service = AIService(db_session, usage_tracker=tracker, max_retries=1)
    service._openai_retry.delays = [0]
    expected = await service._call_openai("gpt-4", "Exact retry input")
    events = await _events(db_session)
    assert any(e["payload"].get("outcome") == "failed" for e in events)
    tape = ReplayTape.from_events(events, job_id=job.id)
    sdk.chat.completions.create.reset_mock()
    sdk.chat.completions.create.side_effect = AssertionError("live SDK call in replay")
    with replay_models(tape):
        actual = await service._call_openai("gpt-4", "Exact retry input")
        tape.assert_complete()
    assert expected == actual and len(tape.consumed) == 2
    sdk.chat.completions.create.assert_not_called()


def test_actual_anthropic_sdk_object_serializes_full_blocks():
    from anthropic.types import Message

    from app.services.model_recording import json_value

    reply = Message.model_validate(
        {
            "id": "msg-recorded",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-4-8",
            "content": [{"type": "text", "text": "Необрізана відповідь моделі."}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 201, "output_tokens": 31},
        }
    )
    assert json_value(reply)["content"][0]["text"] == "Необрізана відповідь моделі."


@pytest.mark.asyncio
async def test_record_storage_failure_is_a_technical_stop_before_paid_call(monkeypatch):
    from contextlib import asynccontextmanager

    from app.services.cost_estimator import UsageTracker
    from app.services.generation_operations import recorded_provider_call
    from app.services.generation_outcomes import failure_reason
    from app.services.generation_policy import RecordingPersistenceError

    @asynccontextmanager
    async def broken_session():
        yield SimpleNamespace(
            add=lambda row: None,
            commit=AsyncMock(side_effect=OSError("storage unavailable")),
        )

    monkeypatch.setattr(
        "app.services.generation_operations.database.AsyncSessionLocal", broken_session
    )
    tracker = UsageTracker()
    tracker.generation_context = {"document_id": 1, "job_id": 1, "worker_attempt": 1}
    call = AsyncMock()
    with pytest.raises(RecordingPersistenceError) as caught:
        await recorded_provider_call(
            call,
            provider="openai",
            model="gpt-4",
            request={},
            usage_tracker=tracker,
            purpose="outline",
        )
    assert failure_reason(caught.value) == "recording_storage_unavailable"
    call.assert_not_called()
