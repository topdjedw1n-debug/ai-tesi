"""Addendum 2: real job13 replies, one recorded format retry, strict stages."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.document import AIGenerationJob, Document, DocumentProvenance
from app.services.executor_v2.budgets import POLICY, json_call, sparse_json
from app.services.executor_v2.outline import build_outline
from app.services.executor_v2.run import Context, run
from app.services.executor_v2.scopes import build_scopes
from app.services.executor_v2.warnings import ExecutionStop
from app.services.replay_dependencies import recording_context
from app.services.storage_service import StorageService
from tests.test_executor_v2 import NODES, PLAN, mock_sources, response, seed
from tests.test_executor_v2 import no_external_network as no_external_network

FIXTURES = Path(__file__).parent / "fixtures/executor_v2"
REAL_S1 = (FIXTURES / "job13-s1-response.txt").read_text()
REAL_S3 = (FIXTURES / "job13-s3-response.txt").read_text()
# Actual prose from the same response, with its JSON deliberately omitted.
PLAIN_TEXT = REAL_S3[: REAL_S3.index("{")]


@pytest.mark.parametrize(
    "text,key,size", [(REAL_S1, "nodes", 4), (REAL_S3, "sections", 4)]
)
async def test_real_json_reply_needs_no_retry(db_session, text, key, size):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.provider = AsyncMock(return_value=response(text))
    token = recording_context.set(ctx.recording)
    try:
        parsed = await json_call(
            ctx, "Recorded case", budget=8000, purpose="S1" if key == "nodes" else "S3"
        )
    finally:
        recording_context.reset(token)
    assert len(parsed[key]) == size
    assert ctx.provider.await_count == 1
    events = list((await db_session.scalars(select(DocumentProvenance))).all())
    receipt = next(
        e.payload
        for e in events
        if e.event_type == "generation_provider_attempt"
        and e.payload["outcome"] == "received"
    )
    assert receipt["response"]["content"][0]["text"] == text


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            'Explanation {not JSON}\n```json\n{"notes":"a } and { and \\"quote\\"","nested":{"a":1}}\n```\nTrailing text',
            {"notes": 'a } and { and "quote"', "nested": {"a": 1}},
        ),
        ('{} trailing {"nodes": []}', {}),
        (PLAIN_TEXT, None),
        ('{"nodes":', None),
    ],
)
def test_first_complete_object_with_arbitrary_surroundings(text, expected):
    assert sparse_json(text) == expected


@pytest.mark.parametrize("stage", ["S1", "S3", "S6"])
@pytest.mark.parametrize("first_text", [PLAIN_TEXT, ""])
async def test_missing_json_retries_once_then_stops_and_records_both(
    db_session, stage, first_text
):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.provider = AsyncMock(side_effect=[response(first_text), response(PLAIN_TEXT)])
    token = recording_context.set(ctx.recording)
    try:
        with pytest.raises(ExecutionStop) as stopped:
            await json_call(ctx, "Original task", budget=8000, purpose=stage)
    finally:
        recording_context.reset(token)
    assert stopped.value.stop["code"] == "provider_unusable_response"
    assert ctx.provider.await_count == 2
    assert ctx.provider.await_args_list[1].kwargs["messages"][0]["content"] == (
        "Original task\nReturn only a JSON object, without explanations."
    )
    events = list((await db_session.scalars(select(DocumentProvenance))).all())
    provider_events = [
        e.payload for e in events if e.event_type == "generation_provider_attempt"
    ]
    assert [e["outcome"] for e in provider_events] == [
        "started",
        "received",
        "started",
        "received",
    ]
    assert [
        e["response"]["content"][0]["text"]
        for e in provider_events
        if e["outcome"] == "received"
    ] == [first_text, PLAIN_TEXT]


@pytest.mark.parametrize("stage", ["S1", "S3", "S6"])
async def test_json_retry_can_recover_without_changing_schema(db_session, stage):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    expected = (
        {"nodes": NODES}
        if stage == "S1"
        else PLAN
        if stage == "S3"
        else {"verdict": "PASS", "notes": ""}
    )
    ctx.provider = AsyncMock(
        side_effect=[
            response(PLAIN_TEXT),
            response("Here:\n```json\n" + json.dumps(expected) + "\n```\nDone."),
        ]
    )
    token = recording_context.set(ctx.recording)
    try:
        assert (
            await json_call(ctx, "Original task", budget=8000, purpose=stage)
            == expected
        )
    finally:
        recording_context.reset(token)
    assert ctx.provider.await_count == 2


@pytest.mark.parametrize(
    "stage,reply",
    [
        ("S1", '{"nodes":[]}'),
        (
            "S1",
            '{"nodes":[{"title":"Sleep","required":true,"terms_local":[],"terms_en":["sleep"]}]}',
        ),
        ("S3", '{"sections":[{"title":"Sleep","target_words":0}]}'),
    ],
)
async def test_extracted_json_still_requires_valid_stage_content(
    db_session, stage, reply
):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.inputs = {"requirements": "", "brief": {"target_words": 500}}
    ctx.provider = AsyncMock(return_value=response("Explanation\n" + reply + "\nEnd"))
    token = recording_context.set(ctx.recording)
    try:
        with pytest.raises(ExecutionStop):
            if stage == "S1":
                await build_scopes(ctx)
            else:
                await build_outline(ctx, NODES, SimpleNamespace(sources=[]))
    finally:
        recording_context.reset(token)
    assert (
        ctx.provider.await_count == 1
    )  # Valid JSON is not repaired into a different task.


@pytest.mark.parametrize(
    "replies,expected_calls,status",
    [
        ([PLAIN_TEXT, PLAIN_TEXT], 5, "failed"),
        (['Prefix {"verdict":[],"notes":"invalid"}'], 4, "failed"),
        (
            ['Prefix {"verdict":"FAIL","notes":"Improve evidence"} suffix'],
            4,
            "completed",
        ),
    ],
)
async def test_s6_keeps_docx_and_distinguishes_bad_json_from_negative_review(
    db_session, monkeypatch, replies, expected_calls, status
):
    claimed, _, _, _ = await seed(db_session)
    mock_sources(monkeypatch)
    provider = AsyncMock(
        side_effect=[
            response(json.dumps({"nodes": NODES})),
            response(json.dumps(PLAN)),
            response("A complete section."),
            *[response(s) for s in replies],
        ]
    )

    async def call(self, **request):
        return await provider(**request)

    monkeypatch.setattr(Context, "provider", call)
    upload = AsyncMock(return_value="s3://offline/preserved.docx")
    monkeypatch.setattr(StorageService, "upload_file", upload)
    result = await run(claimed)
    db_session.expire_all()
    job = await db_session.get(AIGenerationJob, claimed.id)
    doc = await db_session.get(Document, claimed.document_id)
    assert job.status == status and doc.docx_path and upload.await_count == 1
    assert provider.await_count == expected_calls
    if status == "failed":
        assert (
            result is None
            and job.request_payload["execution"]["stop"]["code"]
            == "provider_unusable_response"
        )
    else:
        assert any(w["code"] == "review_negative" for w in result["warnings"])


async def test_format_retry_obeys_existing_call_ceiling(db_session):
    claimed, _, _, _ = await seed(db_session)
    ctx = Context(claimed)
    ctx.calls = POLICY["calls_per_section"] + POLICY["extra_calls"] - 1
    ctx.provider = AsyncMock(return_value=response(PLAIN_TEXT))
    token = recording_context.set(ctx.recording)
    try:
        with pytest.raises(ExecutionStop) as stopped:
            await json_call(ctx, "Original task", budget=8000, purpose="S1")
    finally:
        recording_context.reset(token)
    assert stopped.value.budget and ctx.provider.await_count == 1
