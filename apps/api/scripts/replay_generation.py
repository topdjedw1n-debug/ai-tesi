"""Run saved provider responses through the real worker in a fresh local DB.

Usage: python scripts/replay_generation.py RECORDING.json NEW_OUTPUT_DIRECTORY
The input is an export containing document_provenance (or provenance) events.
No keys, network, existing database or external storage are used.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import gzip
import hashlib
import io
import json
import os
import socket
import sys
from datetime import UTC
from pathlib import Path
from types import SimpleNamespace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--worker-attempt", type=int)
    parser.add_argument("--allow-request-changes", action="store_true")
    args = parser.parse_args()
    # Refuse to reuse a directory: no historical file or DB can be overwritten.
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.clear()
    os.environ.update(
        {
            "ENV_FILE": "/dev/null",
            "ENVIRONMENT": "test",
            "DEBUG": "true",
            "DATABASE_URL": f"sqlite+aiosqlite:///{args.output / 'replay.db'}",
            "SECRET_KEY": "offline-replay-only-secret-never-an-account",
            "JWT_SECRET": "offline-replay-only-secret-never-an-account",
        }
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    report = asyncio.run(run(args))
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "completed" else 2


async def run(args):
    from datetime import datetime
    from unittest.mock import patch

    from sqlalchemy import DateTime, select

    from app.core import database
    from app.core.config import settings
    from app.models.auth import User
    from app.models.document import AIGenerationJob, Document, DocumentProvenance
    from app.services.background_jobs import BackgroundJobService
    from app.services.generation_profile import generation_profile_sha256
    from app.services.model_recording import ReplayIncomplete, ReplayTape, replay_models
    from app.services.replay_snapshot import REPLAY_SETTING_NAMES
    from app.services.storage_service import StorageService

    raw = args.recording.read_bytes()
    data = json.loads(gzip.decompress(raw) if args.recording.suffix == ".gz" else raw)
    if isinstance(data, list):
        data = {"provenance": data}
    events = data.get("document_provenance", data.get("provenance", []))
    snapshots = [
        e["payload"]
        for e in events
        if e.get("event_type") == "generation_replay_inputs"
        and (args.job_id is None or e["payload"].get("job_id") == args.job_id)
        and (
            args.worker_attempt is None
            or e["payload"].get("worker_attempt") == args.worker_attempt
        )
    ]
    report = {
        "status": "incomplete",
        "actual_spend_usd": 0,
        "live_provider_calls": 0,
        "origin": data.get("origin", "recorded_export"),
        "consumed": [],
    }
    if len(snapshots) != 1:
        report[
            "reason"
        ] = "Exactly one complete initial generation snapshot is required; no inputs were invented"
        return report
    snapshot = snapshots[0]
    tape = None

    def no_network(*unused, **kwargs):
        raise ReplayIncomplete(
            "Unrecorded network access attempted; live fallback is prohibited"
        )

    try:
        tape = ReplayTape.from_events(
            events,
            job_id=snapshot["job_id"],
            worker_attempt=snapshot["worker_attempt"],
            allow_request_changes=args.allow_request_changes,
            persist_receipts=True,
        )
        for name, value in snapshot.get(
            "replay_settings", snapshot["profile"]["settings"]
        ).items():
            if name in REPLAY_SETTING_NAMES:
                setattr(settings, name, value)
        for name, present in snapshot.get("provider_presence", {}).items():
            if name in type(settings).model_fields and (
                name.endswith("_API_KEY") or name == "COPYSCAPE_USERNAME"
            ):
                setattr(settings, name, "offline-placeholder" if present else None)
        settings.UNLIMITED_GENERATION_USER_IDS = (
            [snapshot["job"]["user_id"]]
            if snapshot["profile"].get("unlimited_claim_checks")
            else []
        )

        async with database.engine.begin() as connection:
            await connection.run_sync(database.Base.metadata.create_all)

        def values(table, row):
            return {
                column.name: (
                    datetime.fromisoformat(row[column.name])
                    if isinstance(column.type, DateTime)
                    and isinstance(row[column.name], str)
                    else row[column.name]
                )
                for column in table.columns
                if column.name in row
            }

        async with database.AsyncSessionLocal() as db:
            rows = {"documents": [snapshot["document"]], **snapshot["tables"]}
            # Prior attempts stay in the export once, not nested in every snapshot.
            rows["document_provenance"] = [
                *rows.get("document_provenance", []),
                *[
                    {
                        "document_id": snapshot["document"]["id"],
                        "stage": "provider",
                        **event,
                    }
                    for event in events
                    if event.get("event_type")
                    in {"generation_provider_attempt", "generation_dependency"}
                    and (event.get("payload") or {}).get("job_id") == snapshot["job_id"]
                    and int((event.get("payload") or {}).get("worker_attempt", 0))
                    < snapshot["worker_attempt"]
                ],
            ]
            # The immutable original input receipt belongs in the isolated DB;
            # provider receipts are re-journaled when the tape consumes them.
            rows["document_provenance"].append(
                {
                    "document_id": snapshot["document"]["id"],
                    "stage": "sources",
                    "event_type": "generation_replay_inputs",
                    "payload": snapshot,
                }
            )
            user_ids = {snapshot["job"]["user_id"], snapshot["document"]["user_id"]}
            for table_name, records in rows.items():
                table = database.Base.metadata.tables[table_name]
                for column in table.columns:
                    if any(
                        fk.target_fullname == "users.id" for fk in column.foreign_keys
                    ):
                        user_ids.update(
                            r[column.name] for r in records if r.get(column.name)
                        )
            db.add_all(
                [
                    User(id=uid, email=f"replay-{uid}@example.invalid")
                    for uid in user_ids
                ]
            )
            await db.commit()
            for table in database.Base.metadata.sorted_tables:
                for row in rows.get(table.name, []):
                    await db.execute(table.insert().values(**values(table, row)))
            await db.commit()
            document = await db.get(Document, snapshot["document"]["id"])
            job_values = values(AIGenerationJob.__table__, snapshot["job"])
            job_values.update(
                status="queued",
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                available_at=datetime.now(UTC),
                completed_at=None,
                attempt_count=max(0, snapshot["worker_attempt"] - 1),
            )
            payload = dict(job_values.get("request_payload") or {})
            current_profile = generation_profile_sha256(document, job_values["user_id"])
            report["profile_changed"] = payload.get("profile_sha256") != current_profile
            # Compatibility of this isolated clone is reported, not asserted as live proof.
            payload["profile_sha256"] = current_profile
            job_values["request_payload"] = payload
            db.add(AIGenerationJob(**job_values))
            await db.commit()

        store = LocalObjects(args.output)
        for row in tape.dependencies:
            if row.get("kind") == "input_file" and row.get("outcome") == "received":
                key = StorageService()._parse_path(row["request"]["file_path"])
                store.objects[key] = base64.b64decode(row["response"])
        with (
            replay_models(tape),
            patch("app.services.background_jobs._redis_client", LocalRedis()),
            patch.object(StorageService, "client", property(lambda self: store)),
            patch.object(socket.socket, "connect", no_network),
            patch.object(socket, "getaddrinfo", no_network),
        ):
            await BackgroundJobService.generate_full_document_async(
                document_id=snapshot["document"]["id"],
                user_id=snapshot["job"]["user_id"],
                job_id=snapshot["job_id"],
                additional_requirements=(
                    snapshot["job"].get("request_payload") or {}
                ).get("additional_requirements"),
            )
        tape.assert_complete()
        async with database.AsyncSessionLocal() as db:
            job = await db.get(AIGenerationJob, snapshot["job_id"])
            document = await db.get(Document, snapshot["document"]["id"])
            report.update(
                status=(
                    "completed"
                    if job.status == "completed" and store.artifacts
                    else "failed"
                ),
                job_status=job.status,
                document_status=document.status,
                simulated_cost_cents=job.cost_cents,
                artifacts=store.artifacts,
            )
            provenance = (
                (
                    await db.execute(
                        select(DocumentProvenance).where(
                            DocumentProvenance.document_id == document.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            report["warnings"] = [
                e.payload for e in provenance if e.event_type == "generation_warning"
            ]
    except ReplayIncomplete as error:
        report.update(status="incomplete", reason=str(error))
    except Exception as error:
        report.update(status="failed", reason=f"{type(error).__name__}: {error}")
    finally:
        if tape:
            report["consumed"] = tape.consumed
            report["recorded_model_calls"] = len(tape.records)
        await database.engine.dispose()
    return report


class LocalRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, **kwargs):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


class ObjectReader(io.BytesIO):
    def release_conn(self):
        pass

    def stream(self, size):
        while chunk := self.read(size):
            yield chunk


class LocalObjects:
    def __init__(self, directory):
        self.directory, self.objects, self.artifacts = directory, {}, []

    def put_object(self, bucket_name, object_name, data, length, **kwargs):
        content = data.read()
        assert len(content) == length
        self.objects[bucket_name, object_name] = content
        sha = hashlib.sha256(content).hexdigest()
        path = self.directory / (sha + Path(object_name).suffix)
        path.write_bytes(content)
        self.artifacts.append({"path": str(path), "sha256": sha, "bytes": length})

    def get_object(self, bucket_name, object_name):
        return ObjectReader(self.objects[bucket_name, object_name])

    def stat_object(self, bucket_name, object_name):
        return SimpleNamespace(size=len(self.objects[bucket_name, object_name]))

    def bucket_exists(self, bucket_name):
        return True

    def presigned_get_object(self, bucket_name, object_name, **kwargs):
        return "https://offline.invalid/local-artifact"


if __name__ == "__main__":
    raise SystemExit(main())
