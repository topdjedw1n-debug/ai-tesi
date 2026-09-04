"""Transport checks with mocked networks; no Telegram sends or paid AI calls."""

import io
import json
import base64
import time
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image
from journal import html_parts, read_events, render_html

from bot import (
    Bot,
    CodeSnapshot,
    Gateway,
    GatewayError,
    Store,
    Telegram,
    TelegramError,
    review_text,
    sender,
)


def message(update_id=1, actor=123, text="/works", **extra):
    return {
        "update_id": update_id,
        "message": {
            "from": {"id": actor},
            "chat": {"id": actor, "type": "private"},
            "text": text,
            **extra,
        },
    }


@pytest.fixture
def bot(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    telegram, gateway = AsyncMock(), AsyncMock()
    gateway.call.return_value = {
        "user_id": 1,
        "documents": [{"id": 7, "topic": "Topic", "status": "failed"}],
    }
    return Bot(store, telegram, gateway, AsyncMock(), "fake", "test-model")


def test_private_numeric_identity_only():
    assert sender(message())[0] == 123
    update = message()
    update["message"]["chat"]["type"] = "group"
    assert sender(update) is None
    update = message()
    update["message"]["from"]["id"] = 999
    assert sender(update) is None
    update = message()
    update["message"]["from"]["is_bot"] = True
    assert sender(update) is None


@pytest.mark.asyncio
async def test_rejected_actor_never_downloads_or_uses_ai(bot):
    bot.gateway.call.side_effect = GatewayError("not allowed", 403)
    bot.chat = AsyncMock()
    await bot.process(message(text="look", photo=[{"file_id": "secret-photo"}]))
    bot.telegram.image.assert_not_called()
    bot.chat.assert_not_called()
    assert "Telegram ID: 123" in bot.telegram.call.call_args.args[1]["text"]


@pytest.mark.asyncio
async def test_callback_actor_comes_from_clicker(bot):
    bot.gateway.call.side_effect = [{"user_id": 1}, {"document_id": 7, "job_id": 15}]
    update = {
        "update_id": 2,
        "callback_query": {
            "id": "query",
            "from": {"id": 123},
            "data": "run:" + "a" * 32,
            "message": {
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 999, "is_bot": True},
            },
        },
    }
    await bot.process(update)
    assert bot.gateway.call.call_args.args[:3] == (
        123,
        "POST",
        "/actions/" + "a" * 32 + "/confirm",
    )


@pytest.mark.asyncio
async def test_model_cannot_confirm_deploy_or_choose_another_actor(bot):
    for name, args in [
        ("confirm_generation", {"action_id": "a" * 32}),
        ("deploy", {}),
        ("document_status", {"document_id": 1, "actor": 999}),
        ("document_status", {"document_id": "../../admin"}),
    ]:
        assert "error" in await bot.invoke(123, 1, 1, name, args)
    bot.gateway.call.assert_not_called()


@pytest.mark.asyncio
async def test_durable_output_replayed_without_model_or_tools(bot):
    bot.store.ingest([message()])
    await bot.send(1, 123, "Already prepared")
    bot.chat = AsyncMock()
    await bot.process(message())
    assert bot.gateway.call.call_count == 1  # authorization only
    bot.chat.assert_not_called()
    assert bot.telegram.call.call_args.args[1]["text"] == "Already prepared"
    assert bot.store.pending() is None
    assert bot.store.offset() == 2


def test_history_and_rebind_do_not_cross_users(bot):
    bot.store.bind(123, 1)
    bot.store.remember(1, 123, "private account A", "answer")
    assert not bot.store.history(999)
    assert bot.store.history(123)
    bot.store.bind(123, 2)
    assert not bot.store.history(123)


@pytest.mark.asyncio
async def test_gateway_key_only_sent_to_fixed_thesica_route():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"user_id": 1})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        gateway = Gateway(client, "http://api:8000", "secret")
        await gateway.call(123, "GET", "/me")
    assert str(requests[0].url) == "http://api:8000/api/v1/operator-bot/me"
    assert requests[0].headers["x-telegram-user-id"] == "123"
    assert requests[0].headers["x-operator-bot-key"] == "secret"
    assert requests[0].headers["host"] == "app.thesica.co"


@pytest.mark.asyncio
async def test_blocked_stranger_does_not_block_manager_inbox(bot):
    first, second = message(1, 999, "/start"), message(2, 123, "/works")
    bot.store.ingest([first, second])
    bot.gateway.call.side_effect = [
        GatewayError("unknown", 403),
        {"user_id": 1},
        {"documents": [{"id": 7, "topic": "Topic", "status": "failed"}]},
    ]
    bot.telegram.call.side_effect = [TelegramError(403), {}]
    await bot.process(bot.store.pending())
    assert bot.store.pending()["update_id"] == 2
    assert (
        bot.store.db.execute("SELECT sent FROM outbox WHERE update_id=1").fetchone()[0]
        == -1
    )
    await bot.process(bot.store.pending())
    assert bot.store.pending() is None
    assert "Topic" in bot.telegram.call.call_args.args[1]["text"]


@pytest.mark.asyncio
async def test_telegram_rate_limit_retains_prepared_output(bot):
    bot.store.ingest([message()])
    await bot.send(1, 123, "Prepared")
    bot.telegram.call.side_effect = TelegramError(429, 12)
    with pytest.raises(TelegramError):
        await bot.process(bot.store.pending())
    assert bot.store.pending()["update_id"] == 1
    assert bot.store.db.execute("SELECT sent FROM outbox").fetchone()[0] == 0
    bot.telegram.call.side_effect = None
    await bot.process(bot.store.pending())
    assert bot.store.pending() is None
    assert bot.telegram.call.call_args.args[1]["text"] == "Prepared"


@pytest.mark.asyncio
async def test_api_outage_preserves_prepared_response(bot):
    bot.store.ingest([message()])
    await bot.send(1, 123, "Prepared")
    bot.gateway.call.side_effect = GatewayError("outage", 503)
    with pytest.raises(GatewayError):
        await bot.process(bot.store.pending())
    assert bot.store.pending()["update_id"] == 1
    assert (
        "Prepared" in bot.store.db.execute("SELECT payload FROM outbox").fetchone()[0]
    )
    bot.telegram.call.assert_not_called()


@pytest.mark.asyncio
async def test_screenshot_download_and_vision_input(bot):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 32), "red").save(buffer, format="PNG")

    def handle(request):
        if request.url.path.endswith("/getFile"):
            return httpx.Response(
                200, json={"ok": True, "result": {"file_path": "photos/test.png"}}
            )
        return httpx.Response(200, content=buffer.getvalue())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        picture = await Telegram(client, "123:fake").image("photo-id")
    assert (
        picture["type"] == "image" and picture["source"]["media_type"] == "image/jpeg"
    )
    bot.telegram.image.return_value = picture
    bot.chat = AsyncMock(return_value="I checked the screenshot")
    await bot.process(message(text="Що сталося?", photo=[{"file_id": "photo-id"}]))
    assert bot.chat.call_args.args[-1] == picture
    assert "base64" not in json.dumps(bot.store.history(123))


@pytest.mark.asyncio
async def test_photo_path_cannot_escape_telegram_download():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"ok": True, "result": {"file_path": "../../other"}}
            )
        )
    ) as client:
        with pytest.raises(ValueError):
            await Telegram(client, "123:fake").image("file")


@pytest.mark.asyncio
async def test_tool_roundtrip_uses_live_data_but_never_generation_confirmation(bot):
    calls = []

    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "document_status",
                            "input": {"document_id": 7},
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "Причина зупинки підтверджена."}]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        bot.client = client
        result = await bot.chat(123, 1, "Що з роботою 7?", None)
    assert result == "Причина зупинки підтверджена."
    bot.gateway.call.assert_awaited_once_with(123, "GET", "/documents/7")
    assert calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_confirmation_is_full_and_readable():
    text = review_text(
        {
            "diagnostic": {
                "document_id": 7,
                "url": "https://app.thesica.co/dashboard/documents/7",
                "document_requirements": "Обов’язкова конкретна вимога",
                "case_requirements": "Умова замовлення",
                "contract": {
                    "rules": [
                        {"key": "language", "value": "it", "status": "explicit"},
                        {
                            "key": "work_type",
                            "value": "tesi_magistrale",
                            "status": "assumed",
                        },
                    ]
                },
            }
        }
    )
    assert "італійська" in text and "магістерська (припущення системи)" in text
    assert "Обов’язкова конкретна вимога" in text and "Умова замовлення" in text


def test_source_snapshot_cannot_read_host_or_other_projects(tmp_path):
    source = tmp_path / "apps/api/app/example.py"
    source.parent.mkdir(parents=True)
    source.write_text("def value():\n    return 1\n")
    snapshot = CodeSnapshot(str(tmp_path))
    result = snapshot.read("apps/api/app/example.py")
    assert "return 1" in result["content"]
    for path in ("/etc/passwd", "apps/api/app/../../.env", "Astelora/app.py"):
        with pytest.raises(ValueError):
            snapshot.read(path)
    proposal = snapshot.proposals(
        [
            {
                "path": "apps/api/app/example.py",
                "source_sha256": result["source_sha256"],
                "before": "return 1",
                "after": "return 2",
            }
        ]
    )
    assert "+    return 2" in proposal[0]["patch"]
    assert "return 1" in source.read_text()  # Preparing cannot apply a patch.
    with pytest.raises(ValueError):
        snapshot.proposals(
            [
                {
                    "path": "apps/api/app/example.py",
                    "source_sha256": "0" * 64,
                    "before": "return 1",
                    "after": "return 2",
                }
            ]
        )


@pytest.mark.asyncio
async def test_notification_rechecks_access_and_is_quiet_while_running(bot):
    bot.store.db.execute("INSERT INTO watches VALUES (15,123,1)")
    bot.gateway.call.side_effect = [{"user_id": 1}, {"status": "running"}]
    await bot.notify_finished()
    bot.telegram.call.assert_not_called()
    bot.gateway.call.side_effect = [
        {"user_id": 1},
        {"status": "completed", "document_id": 7},
    ]
    await bot.notify_finished()
    assert "Compilatio" in bot.telegram.call.call_args.args[1]["text"]
    assert bot.store.db.execute("SELECT count(*) FROM watches").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_revoked_operator_receives_no_notification(bot):
    bot.store.db.execute("INSERT INTO watches VALUES (15,123,1)")
    bot.gateway.call.side_effect = GatewayError("revoked", 403)
    await bot.notify_finished()
    bot.telegram.call.assert_not_called()
    assert bot.store.db.execute("SELECT count(*) FROM watches").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_journal_persists_full_conversation_after_cleanup_and_restart(bot):
    question, answer = "Питання" * 2000, "Відповідь" * 1600
    bot.chat = AsyncMock(return_value=answer)
    bot.store.ingest([message(text=question)])
    await bot.process(bot.store.pending())
    bot.store.db.execute("UPDATE history SET created=?", (time.time() - 9 * 86400,))
    bot.store.finish(9000)  # Retire operational inbox/outbox and working context.
    bot.store.forget(123)
    path = bot.store.db.execute("PRAGMA database_list").fetchone()[2]
    reopened = Store(path)
    events = list(read_events(reopened.db, actor=123))
    assert [e for e in events if e["kind"] == "incoming"][0]["payload"][
        "text"
    ] == question
    assert (
        "".join(e["payload"]["text"] for e in events if e["kind"] == "outgoing")
        == answer
    )
    assert not reopened.history(123)
    assert all(e["user_id"] == 1 for e in events)


@pytest.mark.asyncio
async def test_journal_keeps_screenshot_even_with_command_caption(bot):
    data = io.BytesIO()
    Image.new("RGB", (40, 20), "green").save(data, format="JPEG")
    encoded = base64.b64encode(data.getvalue()).decode()
    bot.telegram.image.return_value = {"source": {"data": encoded}}
    await bot.process(message(text="/works", photo=[{"file_id": "photo-id"}]))
    events = list(read_events(bot.store.db, 123))
    image = next(e for e in events if e["kind"] == "screenshot")
    assert image["image"] == "data:image/jpeg;base64," + encoded
    assert image["image"] in render_html(events)


@pytest.mark.asyncio
async def test_journal_replay_and_delivery_failure_are_truthful(bot):
    bot.store.ingest([message()])
    bot.telegram.call.side_effect = TelegramError(429, 1)
    with pytest.raises(TelegramError):
        await bot.process(bot.store.pending())
    bot.telegram.call.side_effect = None
    await bot.process(bot.store.pending())
    events = list(read_events(bot.store.db, 123))
    assert sum(e["kind"] == "incoming" for e in events) == 1
    assert sum(e["kind"] == "outgoing" for e in events) == 1
    assert [e["payload"]["status"] for e in events if e["kind"] == "delivery"] == [
        "attempting",
        "failed",
        "attempting",
        "delivered",
    ]


@pytest.mark.asyncio
async def test_journal_is_owner_only_and_preserves_old_account_binding(bot):
    bot.gateway.call.side_effect = GatewayError("unknown", 403)
    await bot.process(message())
    assert not list(read_events(bot.store.db))
    bot.store.bind(123, 1)
    bot.store.record(123, 1, "incoming", {"text": "Account 1"})
    bot.store.bind(123, 2)
    bot.store.record(123, 2, "incoming", {"text": "Account 2"})
    assert len(list(read_events(bot.store.db, user_id=1))) == 1
    assert len(list(read_events(bot.store.db, user_id=2))) == 1
    assert not list(read_events(bot.store.db, actor=999))
    assert "error" in await bot.invoke(123, 3, 1, "read_journal", {})
    assert not bot.store.history(123)


@pytest.mark.asyncio
async def test_journal_records_tool_request_result_and_failure(bot):
    bot.store.bind(123, 1)
    await bot.invoke(123, 1, 1, "document_status", {"document_id": 7})
    bot.gateway.call.side_effect = GatewayError("unavailable", 503)
    with pytest.raises(GatewayError):
        await bot.invoke(123, 1, 2, "document_status", {"document_id": 7})
    events = list(read_events(bot.store.db, 123))
    assert [e["kind"] for e in events] == [
        "action_requested",
        "action_result",
        "action_requested",
        "action_error",
    ]
    assert events[1]["payload"]["result"]["documents"][0]["id"] == 7


def test_journal_export_escapes_untrusted_messages_and_stays_offline(bot):
    bot.store.bind(123, 1)
    bot.store.record(
        123,
        1,
        "incoming",
        {"text": '<script>alert(1)</script><img src="https://tracker.test">'},
    )
    html = render_html(read_events(bot.store.db))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert '<img src="https://' not in html
    assert "default-src 'none'" in html
    assert "Content-Security-Policy" in html


@pytest.mark.asyncio
async def test_finished_notification_is_not_resent_or_lost_from_archive(bot):
    bot.store.bind(123, 1)
    bot.store.db.execute("INSERT INTO watches VALUES (15,123,1)")
    bot.gateway.call.side_effect = [
        {"user_id": 1},
        {"status": "completed", "document_id": 7},
    ]
    await bot.notify_finished()
    # Replaying the original confirmation may recreate a watch after completion.
    bot.store.db.execute("INSERT INTO watches VALUES (15,123,1)")
    await bot.notify_finished()
    bot.telegram.call.assert_awaited_once()
    events = list(read_events(bot.store.db, 123))
    assert sum(e["kind"] == "outgoing" for e in events) == 1
    assert (
        sum(
            e["kind"] == "delivery" and e["payload"]["status"] == "delivered"
            for e in events
        )
        == 1
    )


def test_html_export_streams_one_event_at_a_time(bot):
    bot.store.bind(123, 1)
    bot.store.record(123, 1, "incoming", {"text": "First"})
    first = next(read_events(bot.store.db))

    def source():
        yield first
        raise RuntimeError("Next event has not been loaded")

    parts = html_parts(source())
    assert "<!doctype html>" in next(parts)
    assert "First" in next(parts)
    with pytest.raises(RuntimeError):
        next(parts)
