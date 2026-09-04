"""Private, durable operator transcript and owner-only offline export.

No network listener or model tool exposes this module. Export requires server
operator access to the private bot volume. Working-memory cleanup is separate.
"""

import argparse
import base64
import html
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def initialize(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key TEXT NOT NULL UNIQUE,
            actor INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            update_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            created REAL NOT NULL,
            image_jpeg BLOB);
        CREATE INDEX IF NOT EXISTS journal_actor_time ON journal(actor, created, id);
    """)


def record(db, actor, update_id, kind, payload, *, key=None, image_jpeg=None):
    binding = db.execute(
        "SELECT value FROM meta WHERE key=?", (f"binding:{actor}",)
    ).fetchone()
    if binding is None:
        return  # Unapproved strangers do not create an unlimited archive.
    with db:
        db.execute(
            "INSERT OR IGNORE INTO journal "
            "(event_key,actor,user_id,update_id,kind,payload,created,image_jpeg) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                key or uuid.uuid4().hex,
                actor,
                int(binding[0]),
                update_id,
                kind,
                json.dumps(payload, ensure_ascii=False),
                time.time(),
                image_jpeg,
            ),
        )


LABELS = {
    "incoming": "Повідомлення менеджера",
    "screenshot": "Скриншот",
    "outgoing": "Відповідь бота",
    "delivery": "Доставка відповіді",
    "action_requested": "Запит на дію",
    "action_result": "Результат дії",
    "action_error": "Помилка дії",
    "request_error": "Помилка обробки",
}

ACTION_NAMES = {
    "list_documents": "Перевірка списку робіт",
    "document_status": "Перевірка стану роботи",
    "prepare_generation": "Підготовка умов для підтвердження",
    "confirm_generation": "Підтвердження запуску генерації",
    "support_request": "Збереження звернення на виправлення",
    "support_status": "Перевірка звернень",
    "find_project_code": "Пошук у коді Thesica",
    "read_project_file": "Перегляд коду Thesica",
}


def read_events(db, actor=None, user_id=None):
    clauses, values = [], []
    for name, value in (("actor", actor), ("user_id", user_id)):
        if value is not None:
            clauses.append(f"{name}=?")
            values.append(value)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    # A read transaction provides a consistent snapshot even with a live writer.
    rows = db.execute("SELECT * FROM journal" + where + " ORDER BY id", values)
    for row in rows:
        event = dict(row)
        event["payload"] = json.loads(event["payload"])
        picture = event.pop("image_jpeg")
        if picture is not None:
            event["image"] = (
                "data:image/jpeg;base64," + base64.b64encode(picture).decode()
            )
        yield event


def html_parts(events):
    esc = html.escape
    yield HTML_PREFIX
    empty = True
    for event in events:
        empty = False
        payload = event["payload"]
        title = LABELS.get(event["kind"], event["kind"])
        timestamp = datetime.fromtimestamp(event["created"], ZoneInfo("Europe/Kyiv"))
        text = payload.get("text")
        if text is None and event["kind"] == "delivery":
            text = {
                "delivered": "Доставлено в Telegram.",
                "attempting": "Розпочато надсилання в Telegram; результат — у наступній події.",
                "failed": "Telegram відхилив доставку.",
            }.get(payload.get("status"), "Стан доставки уточнюється.")
        if text is None and event["kind"].startswith("action_"):
            text = ACTION_NAMES.get(payload.get("name"), "Дія помічника")
            result = payload.get("result") or {}
            if result.get("job_id"):
                text += f". Робота №{result.get('document_id')}, спроба №{result['job_id']}."
            elif result.get("error"):
                text += ". Дію не виконано: " + str(result["error"])
            elif result.get("status") == "awaiting_user_confirmation":
                text += ". Очікує натискання кнопки менеджером."
        if text is None and event["kind"] == "request_error":
            text = "Обробка запиту завершилася помилкою."
        details = {k: v for k, v in payload.items() if k != "text"}
        content = f'<p class="message">{esc(text)}</p>' if text is not None else ""
        if event.get("image"):
            content += f'<img alt="Скриншот менеджера" loading="lazy" src="{esc(event["image"], quote=True)}">'
        if details:
            content += (
                "<details><summary>Подробиці</summary><pre>"
                + esc(json.dumps(details, ensure_ascii=False, indent=2))
                + "</pre></details>"
            )
        yield (
            f'<article class="{esc(event["kind"], quote=True)}">'
            f'<div class="meta">{timestamp:%d.%m.%Y · %H:%M:%S} · Telegram {event["actor"]}'
            f' · Обліковий запис {event["user_id"]} · Подія {event["id"]}</div>'
            f"<h2>{esc(title)}</h2>{content}</article>"
        )
    if empty:
        yield "<p>За вибраним обліковим записом подій ще немає.</p>"
    yield "</main></html>"


HTML_PREFIX = """<!doctype html><html lang="uk"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Thesica — журнал помічника</title><style>
*{box-sizing:border-box}body{margin:0;background:#f7f5f0;color:#1c1b19;font:17px/1.6 'Source Sans 3',Arial,sans-serif}
main{max-width:900px;margin:auto;padding:48px 24px}header{border-bottom:1px solid #d6d0c2;padding-bottom:24px;margin-bottom:32px}
.brand{color:#0f6e56;font-weight:700}h1,h2{font-family:Literata,Georgia,serif;line-height:1.25}h1{font-size:38px;margin:12px 0}h2{font-size:22px;margin:8px 0 16px}
.intro,.meta{color:#4a4843}.meta{font-size:13px}article{background:#fffdf9;border:1px solid #e6e1d6;border-radius:14px;padding:24px;margin:16px 0;overflow-wrap:anywhere}
.incoming{border-left:4px solid #0f6e56}.action_error,.request_error{border-left:4px solid #9a2b22}.message{white-space:pre-wrap;margin:0}
summary{cursor:pointer;color:#0f6e56}details{margin-top:12px}pre{white-space:pre-wrap;font-size:13px;background:#f7f5f0;padding:16px;border-radius:6px}
img{display:block;max-width:100%;height:auto;margin-top:16px;border:1px solid #e6e1d6;border-radius:6px}
@media(max-width:600px){main{padding:24px 16px}h1{font-size:30px}article{padding:16px}}
</style><main><header><div class="brand">THESICA · ДЛЯ ВЛАСНИКА</div>
<h1>Журнал помічника</h1><p class="intro">Повідомлення, відповіді та дії в порядку запису. Час — Київ.
Це збережений знімок: нові події з’являться після наступного вивантаження.
Для пошуку натисни Ctrl+F або ⌘F.</p></header>"""


def render_html(events):
    """Small local preview helper; the production CLI streams via html_parts."""
    return "".join(html_parts(events))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="/state/bot.sqlite3")
    parser.add_argument("--actor", type=int)
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--format", choices=("html", "json"), default="html")
    args = parser.parse_args()
    if any(value is not None and value <= 0 for value in (args.actor, args.user_id)):
        parser.error("IDs must be positive")
    with sqlite3.connect(Path(args.db).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        events = read_events(db, args.actor, args.user_id)
        if args.format == "html":
            for part in html_parts(events):
                sys.stdout.write(part)
        else:
            sys.stdout.write("[\n")
            separator = ""
            for event in events:
                sys.stdout.write(separator + json.dumps(event, ensure_ascii=False))
                separator = ",\n"
            sys.stdout.write("\n]\n")


if __name__ == "__main__":
    main()
