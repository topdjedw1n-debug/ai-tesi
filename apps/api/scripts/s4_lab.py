"""S4 laboratory: rewrite only the section writing (S4) of one recorded job.

Usage:
  python scripts/s4_lab.py RECORDING.json.gz NEW_OUTPUT_DIRECTORY --job-id N --variant NAME
      [--mode exact|live] [--model MODEL] [--s4-instruction FILE]
      [--cost-cap-usd USD] [--live-sections 5,6] [--secrets-file apps/api/.env]
      [--uploaded-sources SPEC.json] [--recorded-outline] [--allow-host HOST]
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
--uploaded-sources adds manager-style PDF uploads to the recorded executor
  inputs (parsed by the production uploaded-sources code); the pack, the
  section evidence and the S4 prompt then follow the production path.
--recorded-outline serves the recorded S3 plan although the S3 request changed
  (the pack now holds the uploads); the report marks S3 as request_changed.
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


def parse_section_documents(values: list[str]) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for value in values:
        section, _, keys = value.partition("=")
        if not section.strip().isdigit() or not keys.strip():
            raise ValueError("--section-documents needs N=KEY,KEY")
        result[int(section)] = [k.strip() for k in keys.split(",") if k.strip()]
    return result


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


def parse_override(value: str | None) -> dict | None:
    if not value:
        return None
    override = json.loads(value)
    if not isinstance(override, dict) or not override:
        raise ValueError("--request-override must be a non-empty JSON object")
    if "messages" in override or "max_tokens" in override or "model" in override:
        raise ValueError(
            "--request-override cannot replace messages, max_tokens or model"
        )
    return override


def with_instruction(request: dict, production: str, variant: str) -> dict:
    """Swap the S4 instruction inside an already built prompt (one occurrence)."""
    messages = []
    for m in request["messages"]:
        content = m.get("content")
        if isinstance(content, str) and production in content:
            content = content.replace(production, variant, 1)
        messages.append({**m, "content": content})
    return {**request, "messages": messages}


def writer_request(request: dict, model: str | None, override: dict | None) -> dict:
    """The writer call as actually sent: model and extra parameters applied,
    prompt and budget untouched. Recorded verbatim by the production journal."""
    return {**request, "model": model or request["model"], **(override or {})}


def load_section_evidence(path: Path | None) -> dict[int, list[dict]]:
    """Extra evidence per section: every item becomes a citable pack source."""
    if path is None:
        return {}
    raw = json.loads(path.read_text())
    result = {}
    for section, spec in raw.items():
        items = spec.get("add") if isinstance(spec, dict) else spec
        if not isinstance(items, list) or not items:
            raise ValueError(f"section {section}: expected a non-empty 'add' list")
        for item in items:
            missing = {"key", "title", "authors", "year", "text"} - set(item)
            if missing:
                raise ValueError(f"section {section}: item lacks {sorted(missing)}")
            if len(item["text"]) > 2400:
                raise ValueError(f"section {section}: {item['key']} text > 2400 chars")
        result[int(section)] = items
    return result


def load_uploaded_sources(path: Path | None) -> list[dict]:
    """Manager-style uploads for the recorded inputs: every PDF is parsed by
    the production code, so S2 and S4 see exactly what an upload would give."""
    if path is None:
        return []
    specs = json.loads(path.read_text())
    if not isinstance(specs, list) or not specs:
        raise ValueError("--uploaded-sources: expected a non-empty JSON list")
    for spec in specs:
        missing = {"pdf", "key", "title", "authors", "year"} - set(spec)
        if missing:
            raise ValueError(f"uploaded source lacks {sorted(missing)}")
        if not isinstance(spec["authors"], list) or not isinstance(spec["year"], int):
            raise ValueError(f"{spec['key']}: authors must be a list, year an int")
        if not (path.parent / spec["pdf"]).exists() and not Path(spec["pdf"]).exists():
            raise ValueError(f"{spec['key']}: PDF not found: {spec['pdf']}")
        if ":" in spec["key"]:
            raise ValueError(f"{spec['key']}: keys must not contain ':'")
    return specs


def uploaded_inputs(specs: list[dict], base_path: Path) -> tuple[list, list, list]:
    """(uploaded_sources rows, passages, report) built with production parsing."""
    from dataclasses import asdict

    from app.services.uploaded_sources import (
        executor_source_rows,
        extract_pdf_pages,
        split_passages,
    )

    rows, passages, report = [], [], []
    for offset, spec in enumerate(specs):
        pdf = Path(spec["pdf"])
        if not pdf.exists():
            pdf = base_path / spec["pdf"]
        data = pdf.read_bytes()
        pages = extract_pdf_pages(data)
        file_id = 900001 + offset
        windows = split_passages(
            source_file_id=file_id,
            citation_key=spec["key"],
            filename=pdf.name,
            pages=list(enumerate(pages, 1)),
        )
        rows += executor_source_rows(
            [
                {
                    "id": file_id,
                    "citation_key": spec["key"],
                    "title": spec["title"],
                    "authors": "; ".join(spec["authors"]),
                    "year": spec["year"],
                    "mandatory": bool(spec.get("mandatory")),
                    "metadata_incomplete": False,
                    "status": "parsed",
                    "filename": pdf.name,
                }
            ]
        )
        passages += [asdict(w) for w in windows]
        report.append(
            {
                "key": spec["key"],
                "file": pdf.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "pages": len(pages),
                "windows": len(windows),
                "chars": sum(len(w.text) for w in windows),
            }
        )
    return rows, passages, report


async def fresh_uploads(
    db, specs: list[dict], base_path: Path, document_id: int
) -> list:
    """Insert manager-style uploads into the local database (fresh mode): the
    same rows the upload endpoint writes, parsed by the same code."""
    from app.models.document import DocumentSourceFile, SourceFilePage
    from app.services.uploaded_sources import MIN_TEXT_CHARS_PER_PAGE, extract_pdf_pages

    report = []
    for spec in specs:
        pdf = Path(spec["pdf"])
        if not pdf.exists():
            pdf = base_path / spec["pdf"]
        data = pdf.read_bytes()
        pages = extract_pdf_pages(data)
        text_chars = sum(len(p) for p in pages)
        has_text = (
            bool(pages) and text_chars / max(1, len(pages)) >= MIN_TEXT_CHARS_PER_PAGE
        )
        digest_hex = hashlib.sha256(data).hexdigest()
        row = DocumentSourceFile(
            document_id=document_id,
            filename=pdf.name[:255],
            citation_key=spec["key"],
            title=spec["title"],
            authors="; ".join(spec["authors"]) or None,
            year=int(spec["year"]),
            storage_path=f"lab://uploads/{digest_hex[:16]}.pdf",
            sha256=digest_hex,
            page_count=len(pages),
            text_chars=text_chars,
            status="parsed" if has_text else "no_text_layer",
            metadata_incomplete=False,
            mandatory=bool(spec.get("mandatory")),
        )
        db.add(row)
        await db.flush()
        if has_text:
            for number, text in enumerate(pages, start=1):
                if text.strip():
                    db.add(
                        SourceFilePage(
                            source_file_id=int(row.id), page_number=number, text=text
                        )
                    )
        report.append(
            {
                "key": spec["key"],
                "file": pdf.name,
                "sha256": digest_hex,
                "pages": len(pages),
                "chars": text_chars,
                "status": row.status,
            }
        )
    await db.commit()
    return report


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
    parser.add_argument(
        "--mode",
        choices=("exact", "live", "fresh"),
        default="exact",
        help=(
            "exact: replay only; live: S1-S3 from the tape, writing live; fresh: a"
            " new run of the recorded document (S1-S6 live, every external input"
            " fetched and journaled), uploads inserted into the local database"
            " like a manager upload"
        ),
    )
    parser.add_argument("--model", help="writer model for S4-S6 (default: recorded)")
    parser.add_argument(
        "--request-override",
        help=(
            "JSON object merged into writer requests (S4/S6), for example "
            'a thinking setting: {"thinking": {"type": "disabled"}}'
        ),
    )
    parser.add_argument(
        "--s4-instruction", type=Path, help="file with the S4 instruction text"
    )
    parser.add_argument("--cost-cap-usd", type=float, help="required in live mode")
    parser.add_argument(
        "--section-evidence",
        type=Path,
        help=(
            "JSON {section_index: {add: [{key, title, authors, year, url, text}]}} "
            "adding full-text evidence (each text <= 2400 chars) to those sections"
        ),
    )
    parser.add_argument(
        "--live-sections",
        help="comma-separated section indexes written live (default: all)",
    )
    parser.add_argument(
        "--secrets-file", type=Path, help="KEY=VALUE file; only provider keys are read"
    )
    parser.add_argument(
        "--uploaded-sources",
        type=Path,
        help=(
            "JSON list [{pdf, key, title, authors, year, mandatory, url}]: PDFs parsed"
            " by the production uploaded-sources code and added to the recorded"
            " executor inputs as manager-uploaded files"
        ),
    )
    parser.add_argument(
        "--live-outline",
        action="store_true",
        help=(
            "live mode: build the plan (S3) live with the current prompt on the"
            " recorded pack (S1-S2 from the tape); every section is then written"
            " live because the plan changed"
        ),
    )
    parser.add_argument(
        "--recorded-outline",
        action="store_true",
        help="serve the recorded S3 plan although the S3 request changed",
    )
    parser.add_argument(
        "--recorded-sections",
        action="store_true",
        help=(
            "serve recorded S4 answers for sections not written live although"
            " their request changed (previous summaries after a live rewrite)"
        ),
    )
    parser.add_argument(
        "--section-documents",
        action="append",
        default=[],
        metavar="N=KEY,KEY",
        help=(
            "restrict a live section to these pack documents (planned keys and"
            " the pool for out-of-plan windows); repeatable"
        ),
    )
    parser.add_argument(
        "--summaries-from-recorded",
        help=(
            "comma-separated live sections whose previous_summaries are taken from"
            " the recorded texts of all other sections (write the introduction last)"
        ),
    )
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="additional host allowed in live mode (repeatable)",
    )
    parser.add_argument("--price-input-usd-per-1m", type=float)
    parser.add_argument("--price-output-usd-per-1m", type=float)
    args = parser.parse_args()
    if args.mode in ("live", "fresh") and not (
        args.cost_cap_usd and args.cost_cap_usd > 0
    ):
        parser.error(
            "--cost-cap-usd (positive USD) is required in live and fresh modes"
        )
    if args.mode == "exact" and (args.live_sections or args.secrets_file):
        parser.error("--live-sections and --secrets-file apply to --mode live only")
    if args.live_outline and (args.mode != "live" or args.recorded_outline):
        parser.error(
            "--live-outline applies to --mode live and excludes --recorded-outline"
        )
    if args.mode == "fresh" and (args.live_sections or args.recorded_outline):
        parser.error(
            "--live-sections and --recorded-outline do not apply to fresh mode"
        )
    try:
        args.live_section_set = parse_sections(args.live_sections)
        args.request_override_dict = parse_override(args.request_override)
        args.section_evidence_map = load_section_evidence(args.section_evidence)
        args.uploaded_source_specs = load_uploaded_sources(args.uploaded_sources)
        args.section_documents_map = parse_section_documents(args.section_documents)
        args.summaries_from_recorded_set = parse_sections(args.summaries_from_recorded)
    except ValueError as error:
        parser.error(str(error))
    secrets = (
        read_secrets(args.secrets_file, os.environ) if args.mode != "exact" else {}
    )
    if args.mode != "exact" and "ANTHROPIC_API_KEY" not in secrets:
        parser.error(
            "live and fresh modes need ANTHROPIC_API_KEY (environment or --secrets-file)"
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
    from app.services import cost_estimator, full_text_sources
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
        "request_override": args.request_override_dict,
        "section_evidence": {
            str(k): [i["key"] for i in v] for k, v in args.section_evidence_map.items()
        },
        "section_evidence_sha256": (
            hashlib.sha256(args.section_evidence.read_bytes()).hexdigest()
            if args.section_evidence
            else None
        ),
        "live_sections": (
            (sorted(args.live_section_set) if args.live_section_set else "all")
            if args.mode in ("live", "fresh")
            else None
        ),
        "uploaded_sources": [],
        "recorded_outline": args.recorded_outline,
        "live_outline": bool(getattr(args, "live_outline", False)),
        "recorded_sections": args.recorded_sections,
        "section_documents": {str(k): v for k, v in args.section_documents_map.items()},
        "summaries_from_recorded": (
            sorted(args.summaries_from_recorded_set)
            if args.summaries_from_recorded_set
            else []
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
    fresh = args.mode == "fresh"
    store = LocalObjects(args.output)
    recorded_live = (data.get("lab") or {}).get("live_sections")
    override_sections = set(recorded_live) if isinstance(recorded_live, list) else None
    report["recorded_live_sections"] = recorded_live

    def no_network(*unused, **kwargs):
        raise ReplayIncomplete(
            "Unrecorded network access attempted; live fallback is prohibited"
        )

    try:
        tape = (
            ReplayTape([], persist_receipts=True)
            if fresh
            else ReplayTape.from_events(
                events,
                job_id=snapshot["job_id"],
                worker_attempt=snapshot["worker_attempt"],
                allow_request_changes=False,
                persist_receipts=True,
            )
        )
        if args.uploaded_source_specs and not fresh:
            rows, extra_passages, report["uploaded_sources"] = uploaded_inputs(
                args.uploaded_source_specs, args.uploaded_sources.parent
            )
            inputs_row = next(
                r for r in tape.dependencies if r.get("kind") == "executor_inputs"
            )
            inputs_row["response"]["uploaded_sources"] = (
                inputs_row["response"]["uploaded_sources"] + rows
            )
            inputs_row["response"]["passages"] = (
                inputs_row["response"]["passages"] + extra_passages
            )
        relaxed = {"S3"} if args.recorded_outline else set()
        if args.recorded_sections:
            relaxed.add("S4")
        if relaxed:
            recorded_response = tape.response

            def relaxed_response(**call):
                # The recorded answer is reused although the request changed
                # (plan after new uploads, sections after a live rewrite);
                # every consumed entry shows request_changed.
                if call.get("stage") not in relaxed:
                    return recorded_response(**call)
                tape.allow_request_changes = True
                try:
                    return recorded_response(**call)
                finally:
                    tape.allow_request_changes = False

            tape.response = relaxed_response
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
        if fresh:
            from app.models.document import ProductionCase
            from app.services.generation_contract import generation_contract_sha256
            from app.services.task_contract import task_contract_sha256
            from app.services.uploaded_sources import uploaded_sources_digest

            async with database.AsyncSessionLocal() as db:
                document_id = snapshot["document"]["id"]
                if args.uploaded_source_specs:
                    report["uploaded_sources"] = await fresh_uploads(
                        db,
                        args.uploaded_source_specs,
                        args.uploaded_sources.parent,
                        document_id,
                    )
                # What the cabinet does after an upload: the manager confirms
                # the task contract again and the job binds to it.
                document = await db.get(Document, document_id)
                job = await db.get(AIGenerationJob, snapshot["job_id"])
                case = (
                    await db.execute(
                        select(ProductionCase).where(
                            ProductionCase.document_id == document_id
                        )
                    )
                ).scalar_one_or_none()
                document.contract_confirmed_sha256 = task_contract_sha256(document)
                payload = dict(job.request_payload or {})
                payload["generation_contract_sha256"] = generation_contract_sha256(
                    document,
                    case,
                    payload.get("additional_requirements"),
                    await uploaded_sources_digest(db, document_id),
                )
                job.request_payload = payload
                await db.commit()
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
        recorded_sections = {}
        for event in events:
            payload = event.get("payload") or {}
            if (
                event.get("event_type") == "executor_section"
                and payload.get("job_id") == snapshot["job_id"]
                and payload.get("section_index") not in recorded_sections
            ):
                recorded_sections[payload["section_index"]] = payload

        def with_recorded_summaries(request, section_index):
            """previous_summaries of a live section = the recorded texts of all
            other sections, in plan order: the introduction written last."""
            content = request["messages"][0]["content"]
            start = content.index('{"forbidden_placeholders"')
            body = json.loads(content[start:])
            body["previous_summaries"] = [
                {
                    "title": row["title"],
                    "summary": row["content"][-POLICY["summary_chars"] :],
                }
                for index, row in sorted(recorded_sections.items())
                if index != section_index
            ]
            message = content[:start] + json.dumps(body, ensure_ascii=False)
            return {
                **request,
                "messages": [{**request["messages"][0], "content": message}],
            }

        def is_live(stage, section_index):
            if fresh:
                return True
            if stage == "S3" and args.mode == "live":
                return bool(args.live_outline)
            if args.mode != "live" or stage not in LIVE_STAGES:
                return False
            return (
                stage == "S6" or live_sections is None or section_index in live_sections
            )

        async def lab_provider_call(
            call, *, provider, model, request, usage_tracker, purpose
        ):
            section_index = operation_section.get()
            live = is_live(purpose, section_index)
            # Writer overrides apply to live writer calls, and in exact mode to
            # every writer call so a variant recording replays as it was made.
            # A tape-served call in live mode keeps its recorded model/request.
            exact_scope = args.mode == "exact" and (
                override_sections is None or section_index in override_sections
            )
            if purpose in LIVE_STAGES and (live or exact_scope):
                model = args.model or model
                request = writer_request(request, model, args.request_override_dict)
                if purpose == "S4" and instruction != production_instruction:
                    request = with_instruction(
                        request, production_instruction, instruction
                    )
                if (
                    purpose == "S4"
                    and live
                    and args.summaries_from_recorded_set
                    and section_index in args.summaries_from_recorded_set
                ):
                    request = with_recorded_summaries(request, section_index)
            if not live:
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

        def live_when_unrecorded(kind, production):
            """A dependency the tape holds is served from it; a new one goes
            live and is journaled by the production recorder."""
            signature = inspect.signature(production)

            async def wrapper(*call_args, **call_kwargs):
                bound = signature.bind(*call_args, **call_kwargs)
                bound.apply_defaults()
                fingerprint = digest(dependency_request(dict(bound.arguments)))
                recorded = any(
                    row.get("kind") == kind
                    and row.get("input_fingerprint") == fingerprint
                    for row in tape.dependencies
                )
                if recorded:
                    return await production(*call_args, **call_kwargs)
                token = active_replay.set(None)
                try:
                    return await production(*call_args, **call_kwargs)
                finally:
                    active_replay.reset(token)

            return wrapper

        lab_verify = live_when_unrecorded("executor_verify", references.verify)
        lab_full_text = live_when_unrecorded(
            "executor_full_text", full_text_sources.full_text
        )

        production_write_sections = sections.write_sections

        async def lab_write_sections(ctx, outline, pack):
            from app.services.ai_pipeline.rag_retriever import SourceDoc
            from app.services.ai_pipeline.source_pack import PackedSource
            from app.services.source_evidence import evidence_text, freeze_evidence

            for section in outline:
                index = section["section_index"]
                extra = args.section_evidence_map.get(index)
                # Only sections written in this run receive extra evidence; a
                # tape-served section must keep its recorded prompt.
                scoped = (
                    live_sections is None or index in live_sections
                    if args.mode == "live"
                    else override_sections is None or index in override_sections
                )
                if not extra or not scoped:
                    continue
                for item in extra:
                    if pack.by_key(item["key"]) is None:
                        source = SourceDoc(
                            title=item["title"],
                            authors=list(item["authors"]),
                            year=item["year"],
                            abstract=item["text"],
                            url=item.get("url"),
                            provider="lab_full_text",
                            verification_status="verified",
                            canonical_metadata={
                                "origin": "lab_full_text",
                                "verification_provider": "lab",
                                "evidence_level": "full_text",
                            },
                        )
                        freeze_evidence(source, [], item["key"])
                        assert evidence_text(source), item["key"]
                        pack.sources.append(PackedSource(source, item["key"], 1.0))
                    if item["key"] not in section["evidence_keys"]:
                        section["evidence_keys"].append(item["key"])
            return await production_write_sections(ctx, outline, pack)

        production_section_evidence = sections.section_evidence

        def lab_section_evidence(pack, section, nodes):
            from types import SimpleNamespace

            keys = args.section_documents_map.get(section.get("section_index"))
            index = section.get("section_index")
            scoped = (
                live_sections is None or index in live_sections
                if args.mode == "live"
                else override_sections is None or index in override_sections
            )
            if not keys or not scoped:
                return production_section_evidence(pack, section, nodes)
            narrow = SimpleNamespace(
                sources=[s for s in pack.sources if s.citation_key in keys],
                passages=[p for p in (pack.passages or []) if p.citation_key in keys],
                by_key=lambda key: pack.by_key(key) if key in keys else None,
            )
            planned = [k for k in keys if pack.by_key(k) is not None]
            return production_section_evidence(
                narrow, {**section, "evidence_keys": planned}, nodes
            )

        patches = [
            patch("app.services.background_jobs._redis_client", LocalRedis()),
            patch.object(StorageService, "client", property(lambda self: store)),
        ]
        if args.section_documents_map:
            patches.append(
                patch.object(sections, "section_evidence", lab_section_evidence)
            )
        if not fresh:
            patches.insert(0, replay_models(tape))
        if args.section_evidence_map:
            patches.append(patch.object(sections, "write_sections", lab_write_sections))
        if (
            args.model
            or args.request_override_dict
            or instruction != production_instruction
        ):
            patches.append(
                patch.object(budgets, "recorded_provider_call", lab_provider_call)
            )
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
        if args.mode in ("live", "fresh"):
            hosts = (
                set(MODEL_PROVIDER_HOSTS)
                | {
                    urlparse(url).hostname
                    for url in (
                        settings.CROSSREF_API_URL,
                        settings.OPENALEX_API_URL,
                        settings.SEMANTIC_SCHOLAR_API_URL,
                        settings.ARXIV_API_URL,
                        "https://openlibrary.org",
                    )
                }
                | set(args.allow_host)
            )
            guard = NetworkGuard(hosts)
            report["network"] = {
                "allowed_hosts": "*" if "*" in hosts else sorted(hosts),
                "refused": guard.refused,
            }
            if not (
                args.model
                or args.request_override_dict
                or instruction != production_instruction
            ):
                patches.append(
                    patch.object(budgets, "recorded_provider_call", lab_provider_call)
                )
            patches += [
                patch.object(references, "verify", lab_verify),
                patch.object(full_text_sources, "full_text", lab_full_text),
                *([] if "*" in hosts else guard.patches()),
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
        if fresh:
            report["explanation"] = (
                "fresh mode: a new run of the recorded document; every model call"
                " and external input was live and journaled, so the exported"
                " recording stands on its own"
            )
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
    if args.mode == "fresh":
        consumed_events = []  # every external input was journaled by this run
        # The seeded copy of the source snapshot precedes the run's own one;
        # the standard replay requires exactly one, the run's.
        snapshots = [
            i
            for i, r in enumerate(provenance_rows)
            if r.get("event_type") == "generation_replay_inputs"
        ]
        provenance_rows = [
            r for i, r in enumerate(provenance_rows) if i not in snapshots[:-1]
        ]
    else:
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
            "request_override": report.get("request_override"),
            "section_evidence": report.get("section_evidence"),
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
