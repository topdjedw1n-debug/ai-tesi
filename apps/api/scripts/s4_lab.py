"""S4 laboratory: rewrite only the section writing (S4) of one recorded job.

Usage:
  python scripts/s4_lab.py RECORDING.json.gz NEW_OUTPUT_DIRECTORY --job-id N --variant NAME
      [--mode exact|live] [--model MODEL] [--s4-instruction FILE]
      [--cost-cap-usd USD] [--live-sections 5,6] [--secrets-file apps/api/.env]
      [--price-input-usd-per-1m X --price-output-usd-per-1m Y]

Frozen from the recording: brief, requirements, source pack, evidence excerpts,
library, outline (S3), volume and budget parameters. None of it is recomputed.

exact: every model response and external input comes from the recording through
  the production replay path; the DOCX must equal the recorded one byte for byte.
  A changed instruction or model makes the tape stop: the recording holds no
  answers for a changed request, and the lab never substitutes the old text.
live: S1-S3 and their external inputs come from the recording. S4 sections are
  written live and sequentially (each one sees the new variant's previous
  summaries); S5 verifies new [STD:...] candidates with a real external call
  (a candidate already verified in the recording is served by fingerprint); S6
  runs a new advisory review; production code assembles the DOCX. Every live
  call is recorded like in production into the local database, and the variant
  recording is exported for scripts/replay_generation.py.
Output (new empty directory): DOCX, report.json, s4-instruction.txt, the exported
variant recording and replay.db. No product database, storage or account is used.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import gzip
import hashlib
import inspect
import json
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

# Anthropic first-party rates (USD per 1M tokens) for models absent from the
# production tables in app/services/cost_estimator.py, which stay untouched.
# Source: claude-api skill reference cached 2026-06-24. Any other model needs
# explicit --price-input-usd-per-1m / --price-output-usd-per-1m.
LAB_PRICING_USD_PER_1M = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
# Only provider credentials are read from --secrets-file; nothing else of a
# developer environment reaches the isolated run. Values are never reported.
LIVE_SECRET_NAMES = (
    "ANTHROPIC_API_KEY",
    "OPENALEX_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
)
MODEL_PROVIDER_HOSTS = ("api.anthropic.com",)
LIVE_STAGES = {"S4", "S6"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def normalize_instruction(text: str) -> str:
    """Keep the prompt structure identical: directive + '\\n...\\n' + JSON."""
    return "\n" + text.strip("\n") + "\n"


def parse_sections(value: str | None) -> set[int] | None:
    if not value:
        return None
    indexes = {int(part) for part in value.split(",") if part.strip()}
    if not indexes or min(indexes) < 1:
        raise ValueError("--live-sections needs positive section indexes")
    return indexes


def read_secrets(path: Path | None, environment: dict[str, str]) -> dict[str, str]:
    values = {n: environment[n] for n in LIVE_SECRET_NAMES if environment.get(n)}
    if path is None:
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line or line.startswith("#"):
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("'\"")
        if name in LIVE_SECRET_NAMES and value:
            values[name] = value
    return values


def resolve_prices(model, args, pricing_input, pricing_output):
    """(input, output) USD per 1M tokens; production rates win, lab rates fill."""
    production = (
        pricing_input["anthropic"].get(model),
        pricing_output["anthropic"].get(model),
    )
    if None not in production:
        return production, False
    if args.price_input_usd_per_1m is not None and args.price_output_usd_per_1m:
        return (args.price_input_usd_per_1m, args.price_output_usd_per_1m), True
    if model in LAB_PRICING_USD_PER_1M:
        return LAB_PRICING_USD_PER_1M[model], True
    raise SystemExit(
        f"No price known for {model}; pass --price-input-usd-per-1m and "
        "--price-output-usd-per-1m (USD per 1M tokens)"
    )


def request_chars(request) -> int:
    return sum(
        len(m["content"])
        for m in request.get("messages", [])
        if isinstance(m.get("content"), str)
    )


class CostCapExceeded(BaseException):
    """Lab stop: the next live call could exceed --cost-cap-usd."""


class Ledger:
    """Per-call live accounting; the ceiling is checked before each live call."""

    def __init__(self, cap_usd, prices_for, chars_per_token):
        self.cap_usd = cap_usd
        self.prices_for = prices_for
        self.chars_per_token = chars_per_token
        self.calls = []
        self.spent_usd = 0.0
        # A failed attempt may still have been billed by the provider; its
        # conservative estimate counts against the ceiling as unknown spend.
        self.unknown_spend_usd = 0.0
        self.input_tokens = 0
        self.output_tokens = 0

    def estimate(self, request) -> float:
        price_in, price_out = self.prices_for(request["model"])
        return (
            request_chars(request) / self.chars_per_token * price_in
            + request["max_tokens"] * price_out
        ) / 1_000_000

    def check(self, request, stage, section_index):
        estimate = self.estimate(request)
        if self.spent_usd + self.unknown_spend_usd + estimate > self.cap_usd:
            raise CostCapExceeded(
                f"Cost cap {self.cap_usd:.2f} USD would be exceeded at {stage}"
                f" section={section_index}: spent {self.spent_usd:.4f} USD, unknown"
                f" spend of failed attempts up to {self.unknown_spend_usd:.4f} USD,"
                f" plus a conservative estimate {estimate:.4f} USD for the next call"
            )
        return estimate

    def add_failure(self, error, request, stage, section_index, elapsed):
        estimate = self.estimate(request)
        self.unknown_spend_usd += estimate
        self.calls.append(
            {
                "stage": stage,
                "section_index": section_index,
                "model": request["model"],
                "max_tokens": request["max_tokens"],
                "outcome": "failed",
                "error": type(error).__name__,
                "status_code": getattr(error, "status_code", None),
                "spend_unknown_estimate_usd": round(estimate, 6),
                "elapsed_seconds": round(elapsed, 3),
            }
        )

    def add(self, response, request, stage, section_index, elapsed):
        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
        price_in, price_out = self.prices_for(request["model"])
        cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
        self.spent_usd += cost
        self.input_tokens += tokens_in
        self.output_tokens += tokens_out
        self.calls.append(
            {
                "stage": stage,
                "section_index": section_index,
                "model": request["model"],
                "max_tokens": request["max_tokens"],
                "outcome": "received",
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "cost_usd": round(cost, 6),
                "stop_reason": getattr(response, "stop_reason", None),
                "response_id": getattr(response, "id", None),
                "elapsed_seconds": round(elapsed, 3),
            }
        )


class NetworkGuard:
    """Live mode: only the model provider and reference-verification hosts.

    A refused host fails like an unreachable network (OSError), so production
    code treats it as the outage it is; every refusal is listed in the report.
    """

    def __init__(self, allowed_hosts):
        self.allowed_hosts = set(allowed_hosts)
        self.allowed_addresses = set()
        self.refused = []
        self.original_getaddrinfo = socket.getaddrinfo
        self.original_connect = socket.socket.connect

    def getaddrinfo(self, host, port, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else str(host)
        if name not in self.allowed_hosts:
            self.refused.append(name)
            raise socket.gaierror(f"Network access to {name} is refused by the lab")
        results = self.original_getaddrinfo(host, port, *args, **kwargs)
        self.allowed_addresses.update(str(r[4][0]) for r in results)
        return results

    def connect(self, sock, address):
        target = address[0] if isinstance(address, tuple) else address
        if str(target) not in self.allowed_addresses:
            self.refused.append(str(target))
            raise ConnectionRefusedError(
                f"Connection to {target!r} is refused by the lab"
            )
        return self.original_connect(sock, address)

    def patches(self):
        # Plain functions: a bound method stored on the socket class would not
        # receive the socket instance as its first argument.
        def getaddrinfo(host, port, *args, **kwargs):
            return self.getaddrinfo(host, port, *args, **kwargs)

        def connect(sock, address):
            return self.connect(sock, address)

        from unittest.mock import patch

        return [
            patch.object(socket, "getaddrinfo", getaddrinfo),
            patch.object(socket.socket, "connect", connect),
        ]


def git_revision(repo_root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--mode", choices=("exact", "live"), default="exact")
    parser.add_argument("--model", help="writer model for S4-S6 (default: recorded)")
    parser.add_argument(
        "--s4-instruction", type=Path, help="file with the S4 instruction text"
    )
    parser.add_argument("--cost-cap-usd", type=float, help="required in live mode")
    parser.add_argument(
        "--live-sections",
        help="comma-separated section indexes written live (default: all)",
    )
    parser.add_argument(
        "--secrets-file", type=Path, help="KEY=VALUE file; only provider keys are read"
    )
    parser.add_argument("--price-input-usd-per-1m", type=float)
    parser.add_argument("--price-output-usd-per-1m", type=float)
    args = parser.parse_args()
    if args.mode == "live" and not (args.cost_cap_usd and args.cost_cap_usd > 0):
        parser.error("--cost-cap-usd (positive USD) is required in live mode")
    if args.mode == "exact" and (args.live_sections or args.secrets_file):
        parser.error("--live-sections and --secrets-file apply to --mode live only")
    try:
        args.live_section_set = parse_sections(args.live_sections)
    except ValueError as error:
        parser.error(str(error))
    secrets = read_secrets(args.secrets_file, os.environ) if args.mode == "live" else {}
    if args.mode == "live" and "ANTHROPIC_API_KEY" not in secrets:
        parser.error(
            "live mode needs ANTHROPIC_API_KEY (environment or --secrets-file)"
        )
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
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    report = asyncio.run(run(args, secrets))
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "completed" else 2


async def run(args, secrets):
    from unittest.mock import patch

    from replay_generation import LocalObjects, LocalRedis
    from sqlalchemy import DateTime, select

    from app.core import database
    from app.core.config import settings
    from app.models.auth import User
    from app.models.document import AIGenerationJob, Document, DocumentProvenance
    from app.services import cost_estimator
    from app.services.academic_context import digest
    from app.services.background_jobs import BackgroundJobService
    from app.services.executor_v2 import budgets, references, sections
    from app.services.executor_v2.budgets import POLICY
    from app.services.generation_operations import journal_usage
    from app.services.generation_operations import (
        recorded_provider_call as production_provider_call,
    )
    from app.services.generation_profile import generation_profile_sha256
    from app.services.model_recording import (
        ReplayIncomplete,
        ReplayTape,
        active_replay,
        operation_section,
        replay_models,
    )
    from app.services.replay_dependencies import _request as dependency_request
    from app.services.replay_snapshot import REPLAY_SETTING_NAMES, row_data
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
        and e["payload"].get("job_id") == args.job_id
    ]
    production_instruction = sections.S4_INSTRUCTION
    instruction = (
        normalize_instruction(args.s4_instruction.read_text())
        if args.s4_instruction
        else production_instruction
    )
    (args.output / "s4-instruction.txt").write_text(instruction)
    report = {
        "status": "incomplete",
        "mode": args.mode,
        "variant": args.variant,
        "job_id": args.job_id,
        "actual_spend_usd": 0.0,
        "live_provider_calls": 0,
        "cost_cap_usd": args.cost_cap_usd,
        "lab_revision": git_revision(Path(__file__).resolve().parents[3]),
        "input_recording": {
            "path": str(args.recording),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "origin": data.get("origin", "recorded_export"),
            "revision": data.get("revision"),
        },
        "s4_instruction": {
            "source": str(args.s4_instruction) if args.s4_instruction else "production",
            "sha256": sha256_text(instruction),
            "production_sha256": sha256_text(production_instruction),
            "changed": instruction != production_instruction,
        },
        "model": {"requested": args.model, "recorded": None, "writer": None},
        "live_sections": (
            (sorted(args.live_section_set) if args.live_section_set else "all")
            if args.mode == "live"
            else None
        ),
        "live": {
            "calls": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "secrets_present": sorted(secrets),
        },
        "consumed": [],
        "replaced_recorded_calls": [],
        "warnings": [],
        "sections": [],
        "artifacts": [],
    }
    if len(snapshots) != 1:
        report[
            "reason"
        ] = "Exactly one complete initial generation snapshot is required; no inputs were invented"
        return report
    snapshot = snapshots[0]
    recorded_model = snapshot["job"].get("ai_model")
    writer_model = args.model or recorded_model
    report["model"].update(recorded=recorded_model, writer=writer_model)
    prices, lab_priced = resolve_prices(
        writer_model, args, cost_estimator.PRICING_INPUT, cost_estimator.PRICING_OUTPUT
    )
    report["pricing_usd_per_1m"] = {
        "model": writer_model,
        "input": prices[0],
        "output": prices[1],
        "source": "lab" if lab_priced else "production",
    }
    tape = ledger = None
    store = LocalObjects(args.output)

    def no_network(*unused, **kwargs):
        raise ReplayIncomplete(
            "Unrecorded network access attempted; live fallback is prohibited"
        )

    try:
        tape = ReplayTape.from_events(
            events,
            job_id=snapshot["job_id"],
            worker_attempt=snapshot["worker_attempt"],
            allow_request_changes=False,
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
        for name, value in secrets.items():
            setattr(settings, name, value)
        settings.UNLIMITED_GENERATION_USER_IDS = (
            [snapshot["job"]["user_id"]]
            if snapshot["profile"].get("unlimited_claim_checks")
            else []
        )
        await seed_database(
            snapshot,
            events,
            database=database,
            User=User,
            AIGenerationJob=AIGenerationJob,
            Document=Document,
            DateTime=DateTime,
            generation_profile_sha256=generation_profile_sha256,
            report=report,
        )
        for row in tape.dependencies:
            if row.get("kind") == "input_file" and row.get("outcome") == "received":
                key = StorageService()._parse_path(row["request"]["file_path"])
                store.objects[key] = base64.b64decode(row["response"])

        # --- lab boundaries -------------------------------------------------
        def prices_for(model):
            return (
                cost_estimator.PRICING_INPUT["anthropic"][model],
                cost_estimator.PRICING_OUTPUT["anthropic"][model],
            )

        ledger = Ledger(args.cost_cap_usd or 0.0, prices_for, POLICY["chars_per_token"])
        live_sections = args.live_section_set

        def is_live(stage, section_index):
            if args.mode != "live" or stage not in LIVE_STAGES:
                return False
            return (
                stage == "S6" or live_sections is None or section_index in live_sections
            )

        async def lab_provider_call(
            call, *, provider, model, request, usage_tracker, purpose
        ):
            section_index = operation_section.get()
            if not is_live(purpose, section_index):
                return await production_provider_call(
                    call,
                    provider=provider,
                    model=model,
                    request=request,
                    usage_tracker=usage_tracker,
                    purpose=purpose,
                )

            # Checked before the journal writes a started receipt: a refused
            # call never existed, so no unknown-spend receipt is created.
            ledger.check(request, purpose, section_index)

            async def guarded(**live_request):
                started = time.monotonic()
                try:
                    response = await call(**live_request)
                except BaseException as error:
                    ledger.add_failure(
                        error,
                        live_request,
                        purpose,
                        section_index,
                        time.monotonic() - started,
                    )
                    raise
                ledger.add(
                    response,
                    live_request,
                    purpose,
                    section_index,
                    time.monotonic() - started,
                )
                return response

            token = active_replay.set(None)
            try:
                return await production_provider_call(
                    guarded,
                    provider=provider,
                    model=model,
                    request=request,
                    usage_tracker=usage_tracker,
                    purpose=purpose,
                )
            finally:
                active_replay.reset(token)

        production_verify = references.verify
        verify_signature = inspect.signature(production_verify)

        async def lab_verify(*call_args, **call_kwargs):
            bound = verify_signature.bind(*call_args, **call_kwargs)
            bound.apply_defaults()
            fingerprint = digest(dependency_request(dict(bound.arguments)))
            recorded = any(
                row.get("kind") == "executor_verify"
                and row.get("input_fingerprint") == fingerprint
                for row in tape.dependencies
            )
            if recorded:
                return await production_verify(*call_args, **call_kwargs)
            token = active_replay.set(None)
            try:
                return await production_verify(*call_args, **call_kwargs)
            finally:
                active_replay.reset(token)

        production_write_sections = sections.write_sections

        async def lab_write_sections(ctx, outline, pack):
            if args.model:
                ctx.model = args.model
            report["model"]["writer"] = ctx.model
            return await production_write_sections(ctx, outline, pack)

        patches = [
            replay_models(tape),
            patch("app.services.background_jobs._redis_client", LocalRedis()),
            patch.object(StorageService, "client", property(lambda self: store)),
            patch.object(sections, "S4_INSTRUCTION", instruction),
            patch.object(sections, "write_sections", lab_write_sections),
        ]
        if lab_priced:
            patches += [
                patch.dict(
                    cost_estimator.PRICING_INPUT["anthropic"], {writer_model: prices[0]}
                ),
                patch.dict(
                    cost_estimator.PRICING_OUTPUT["anthropic"],
                    {writer_model: prices[1]},
                ),
            ]
        if args.mode == "live":
            hosts = set(MODEL_PROVIDER_HOSTS) | {
                urlparse(url).hostname
                for url in (
                    settings.CROSSREF_API_URL,
                    settings.OPENALEX_API_URL,
                    settings.SEMANTIC_SCHOLAR_API_URL,
                    settings.ARXIV_API_URL,
                    "https://openlibrary.org",
                )
            }
            guard = NetworkGuard(hosts)
            report["network"] = {
                "allowed_hosts": sorted(hosts),
                "refused": guard.refused,
            }
            patches += [
                patch.object(budgets, "recorded_provider_call", lab_provider_call),
                patch.object(references, "verify", lab_verify),
                *guard.patches(),
            ]
        else:
            patches += [
                patch.object(socket.socket, "connect", no_network),
                patch.object(socket, "getaddrinfo", no_network),
            ]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            await BackgroundJobService.generate_full_document_async(
                document_id=snapshot["document"]["id"],
                user_id=snapshot["job"]["user_id"],
                job_id=snapshot["job_id"],
                additional_requirements=(
                    snapshot["job"].get("request_payload") or {}
                ).get("additional_requirements"),
            )
        if args.mode == "exact":
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
    except CostCapExceeded as error:
        report.update(status="stopped_cost_cap", reason=str(error))
    except ReplayIncomplete as error:
        report.update(status="incomplete", reason=str(error))
        if args.mode == "exact" and (
            report["s4_instruction"]["changed"]
            or args.model not in (None, recorded_model)
        ):
            report["explanation"] = (
                "exact mode replays recorded answers only; the recording holds no"
                " answer for a changed S4 instruction or model, so the lab stops"
                " instead of substituting the recorded text. Use --mode live with"
                " --cost-cap-usd for a new variant."
            )
    except Exception as error:
        report.update(status="failed", reason=f"{type(error).__name__}: {error}")
    finally:
        try:
            await finish(
                report,
                args=args,
                data=data,
                snapshot=snapshot,
                tape=tape,
                ledger=ledger,
                database=database,
                select=select,
                DocumentProvenance=DocumentProvenance,
                journal_usage=journal_usage,
                row_data=row_data,
                raw_sha256=report["input_recording"]["sha256"],
            )
        finally:
            await database.engine.dispose()
    return report


async def seed_database(
    snapshot,
    events,
    *,
    database,
    User,
    AIGenerationJob,
    Document,
    DateTime,
    generation_profile_sha256,
    report,
):
    """Mirror of scripts/replay_generation.py: the isolated initial state."""
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
                if any(fk.target_fullname == "users.id" for fk in column.foreign_keys):
                    user_ids.update(
                        r[column.name] for r in records if r.get(column.name)
                    )
        db.add_all(
            [User(id=uid, email=f"replay-{uid}@example.invalid") for uid in user_ids]
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
        payload["profile_sha256"] = current_profile
        job_values["request_payload"] = payload
        db.add(AIGenerationJob(**job_values))
        await db.commit()


async def finish(
    report,
    *,
    args,
    data,
    snapshot,
    tape,
    ledger,
    database,
    select,
    DocumentProvenance,
    journal_usage,
    row_data,
    raw_sha256,
):
    """Accounting, tape bookkeeping and the replayable variant export."""
    if ledger is not None:
        report["live"].update(
            calls=ledger.calls,
            received=sum(c["outcome"] == "received" for c in ledger.calls),
            failed=sum(c["outcome"] == "failed" for c in ledger.calls),
            input_tokens=ledger.input_tokens,
            output_tokens=ledger.output_tokens,
            cost_usd=round(ledger.spent_usd, 6),
            unknown_spend_estimate_usd=round(ledger.unknown_spend_usd, 6),
        )
        report["live_provider_calls"] = len(ledger.calls)
        report["actual_spend_usd"] = round(ledger.spent_usd, 6)
    if tape is None:
        return
    report["consumed"] = tape.consumed
    report["recorded_model_calls"] = len(tape.records)
    consumed_ids = {c["attempt_id"] for c in tape.consumed}
    report["replaced_recorded_calls"] = [
        {
            "attempt_id": r.get("attempt_id"),
            "stage": r.get("stage"),
            "section_index": r.get("section_index"),
        }
        for r in tape.records
        if r.get("attempt_id") not in consumed_ids
    ]
    live_sections = {
        c["section_index"]
        for c in (ledger.calls if ledger else [])
        if c["stage"] == "S4"
    }
    try:
        await export_variant(
            report,
            args=args,
            data=data,
            snapshot=snapshot,
            tape=tape,
            live_sections=live_sections,
            database=database,
            select=select,
            DocumentProvenance=DocumentProvenance,
            journal_usage=journal_usage,
            row_data=row_data,
            raw_sha256=raw_sha256,
        )
    except Exception as error:  # the report itself must still be written
        report["export_error"] = f"{type(error).__name__}: {error}"


async def export_variant(
    report,
    *,
    args,
    data,
    snapshot,
    tape,
    live_sections,
    database,
    select,
    DocumentProvenance,
    journal_usage,
    row_data,
    raw_sha256,
):
    document_id = snapshot["document"]["id"]
    async with database.AsyncSessionLocal() as db:
        provenance = (
            (
                await db.execute(
                    select(DocumentProvenance)
                    .where(DocumentProvenance.document_id == document_id)
                    .order_by(DocumentProvenance.id)
                )
            )
            .scalars()
            .all()
        )
        report["warnings"] = [
            e.payload for e in provenance if e.event_type == "generation_warning"
        ]
        report["sections"] = [
            {
                "section_index": e.payload.get("section_index"),
                "title": e.payload.get("title"),
                "target_words": e.payload.get("target_words"),
                "word_count": e.payload.get("word_count"),
                "tokens_used": e.payload.get("tokens_used"),
                "written": (
                    "live"
                    if e.payload.get("section_index") in live_sections
                    else "recorded"
                ),
            }
            for e in provenance
            if e.event_type == "executor_section"
        ]
        totals, unknown = await journal_usage(db, document_id, snapshot["job_id"])
        report["journal"] = {
            "confirmed_tokens": totals.total_tokens,
            "confirmed_cost_cents": totals.cost_usd_cents(),
            "unknown_provider_attempts": unknown,
        }
        tables = {}
        for name in (
            "documents",
            "ai_generation_jobs",
            "document_sections",
            "document_sources",
            "document_source_files",
            "production_cases",
        ):
            model = next(
                m for m in database.Base.registry.mappers if m.local_table.name == name
            ).class_
            rows = (await db.execute(select(model))).scalars().all()
            tables[name] = [row_data(r) for r in rows]
        provenance_rows = [row_data(e) for e in provenance]
    # Recorded external inputs consumed by the tape are not re-journaled by the
    # executor; the export carries the original events so the standard replay
    # finds every dependency it needs and nothing it does not.
    used = tape._used_dependencies  # index set maintained by ReplayTape.dependency
    dependency_events = [
        e
        for e in data.get("document_provenance", data.get("provenance", []))
        if e.get("event_type") == "generation_dependency"
        and (e.get("payload") or {}).get("job_id") == snapshot["job_id"]
        and (e.get("payload") or {}).get("worker_attempt") == snapshot["worker_attempt"]
    ]
    assert len(dependency_events) == len(tape.dependencies)
    consumed_events = [dependency_events[i] for i in sorted(used)]
    export = {
        "origin": f"s4-lab:{args.variant}:{args.mode}:{data.get('origin', 'recorded_export')}",
        "exported_at": datetime.now(UTC).isoformat(),
        "revision": report.get("lab_revision"),
        "source_recording_sha256": raw_sha256,
        "lab": {
            "variant": args.variant,
            "mode": args.mode,
            "writer_model": report["model"]["writer"],
            "s4_instruction_sha256": report["s4_instruction"]["sha256"],
            "live_sections": report["live_sections"],
            "status": report["status"],
        },
        "document_id": document_id,
        "job_id": snapshot["job_id"],
        **tables,
        "document_provenance": consumed_events + provenance_rows,
        "journal_usage": report["journal"],
    }
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", args.variant).strip("-") or "variant"
    path = args.output / f"{slug}-job{snapshot['job_id']}-recording.json.gz"
    payload = gzip.compress(json.dumps(export, ensure_ascii=False).encode())
    path.write_bytes(payload)
    report["export"] = {
        "path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "consumed_dependency_events": len(consumed_events),
        "provenance_rows": len(provenance_rows),
    }


if __name__ == "__main__":
    raise SystemExit(main())
