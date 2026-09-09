"""Exact model records and an explicit, local-only replay transport.

Replay substitutes SDK responses, not planners, validators or writers. A hole
in a recording must leave the local replay incomplete, even when a business
stage normally treats a failed reviewer as a warning.
"""

from __future__ import annotations

import base64
import copy
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

from app.services.academic_context import digest

RECORDING_VERSION = "model-recording-v1"
operation_section: ContextVar[int | None] = ContextVar(
    "recording_section", default=None
)
active_replay: ContextVar[ReplayTape | None] = ContextVar("model_replay", default=None)
_CREDENTIAL_FIELDS = {"api_key", "authorization", "headers", "extra_headers"}


def json_value(value: Any) -> Any:
    """Preserve complete SDK data; never fall back to a truncated repr."""
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"__recorded_bytes__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [json_value(v) for v in value]
    if isinstance(value, SimpleNamespace):
        return json_value(vars(value))
    if hasattr(value, "model_dump"):
        return json_value(value.model_dump(mode="json"))
    raise TypeError(f"Unsupported recording value: {type(value).__name__}")


def recorded_request(request: dict[str, Any]) -> dict[str, Any]:
    # SDK credentials live on the client, not in the prompt. Exclude optional
    # transport credential fields without changing message text or parameters.
    return json_value(
        {k: v for k, v in request.items() if k.lower() not in _CREDENTIAL_FIELDS}
    )


def _sdk_value(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__recorded_bytes__"}:
            return base64.b64decode(value["__recorded_bytes__"], validate=True)
        return SimpleNamespace(**{k: _sdk_value(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_sdk_value(v) for v in value]
    return value


class ReplayIncomplete(BaseException):
    """Local replay control signal, never a live generation quality verdict.

    It deliberately bypasses Exception handlers that downgrade reviewer
    failures to warnings. The offline runner catches it and reports a gap.
    """


@dataclass
class ReplayTape:
    records: list[dict[str, Any]]
    allow_request_changes: bool = False
    persist_receipts: bool = False  # Only the isolated replay CLI writes a new journal.
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    consumed: list[dict[str, Any]] = field(default_factory=list)
    _used: set[int] = field(default_factory=set)
    _used_dependencies: set[int] = field(default_factory=set)

    @classmethod
    def from_events(
        cls,
        events: list[dict[str, Any]],
        *,
        job_id: int,
        worker_attempt: int | None = None,
        **kwargs: Any,
    ) -> ReplayTape:
        started: dict[str, dict[str, Any]] = {}
        finished: dict[str, dict[str, Any]] = {}
        for event in events:
            if event.get("event_type") != "generation_provider_attempt":
                continue
            p = event.get("payload") or {}
            if p.get("job_id") != job_id or (
                worker_attempt is not None and p.get("worker_attempt") != worker_attempt
            ):
                continue
            attempt = p["attempt_id"]
            target = started if p.get("outcome") == "started" else finished
            if attempt in target:
                raise ReplayIncomplete(f"Ambiguous recording for attempt {attempt}")
            target[attempt] = p
        if finished.keys() - started.keys():
            raise ReplayIncomplete(
                "A provider result has no corresponding recorded request"
            )
        records = []
        for attempt, request in started.items():
            result = finished.get(attempt, {})
            records.append({**request, **result, "request": request.get("request")})
        dependencies = [
            e["payload"]
            for e in events
            if e.get("event_type") == "generation_dependency"
            and (e.get("payload") or {}).get("job_id") == job_id
            and (
                worker_attempt is None
                or e["payload"].get("worker_attempt") == worker_attempt
            )
        ]
        return cls(records, dependencies=dependencies, **kwargs)

    def dependency(self, kind: str, fingerprint: str) -> dict[str, Any]:
        for index, row in enumerate(self.dependencies):
            if (
                index not in self._used_dependencies
                and row.get("kind") == kind
                and row.get("input_fingerprint") == fingerprint
            ):
                self._used_dependencies.add(index)
                parents = {row.get("dependency_id")} - {None}
                while parents:
                    children = [
                        (i, child)
                        for i, child in enumerate(self.dependencies)
                        if i not in self._used_dependencies
                        and child.get("parent_dependency_id") in parents
                    ]
                    self._used_dependencies.update(i for i, _ in children)
                    parents = {child.get("dependency_id") for _, child in children} - {
                        None
                    }
                return copy.deepcopy(row)
        raise ReplayIncomplete(
            f"No external input recording for {kind}/{fingerprint[:12]}"
        )

    def response(
        self, *, provider: str, model: str, stage: str, request: dict[str, Any]
    ) -> Any:
        scope = (stage, operation_section.get())
        found = next(
            (
                (i, r)
                for i, r in enumerate(self.records)
                if i not in self._used
                and (r.get("stage"), r.get("section_index")) == scope
            ),
            None,
        )
        if found is None:
            raise ReplayIncomplete(
                f"No model recording for stage={stage}, section={scope[1]}"
            )
        index, record = found
        if record.get("provider") != provider or record.get("model") != model:
            raise ReplayIncomplete(
                f"Model differs at {stage}: recorded {record.get('provider')}/{record.get('model')}"
            )
        if record.get("request") is None or (
            record.get("response") is None and record.get("outcome") != "failed"
        ):
            raise ReplayIncomplete(
                f"Missing full request/response for {record.get('attempt_id')}"
            )
        changed = digest(record["request"]) != digest(recorded_request(request))
        if changed and not self.allow_request_changes:
            raise ReplayIncomplete(
                f"Request differs at {stage}; recorded text is not evidence for a changed prompt"
            )
        if record.get("outcome") not in {"received", "failed"}:
            raise ReplayIncomplete(f"Unknown provider result at {stage}")
        self._used.add(index)
        self.consumed.append(
            {
                "attempt_id": record.get("attempt_id"),
                "stage": stage,
                "section_index": scope[1],
                "request_changed": changed,
            }
        )
        if record.get("outcome") == "failed":
            raise_recorded_error(record.get("error") or {})
        return _sdk_value(copy.deepcopy(record["response"]))

    def assert_complete(self) -> None:
        if len(self._used) != len(self.records):
            raise ReplayIncomplete(
                f"{len(self.records) - len(self._used)} model recordings were not consumed"
            )
        if len(self._used_dependencies) != len(self.dependencies):
            raise ReplayIncomplete(
                f"{len(self.dependencies) - len(self._used_dependencies)} external inputs were not consumed"
            )


@contextmanager
def replay_models(tape: ReplayTape):
    token = active_replay.set(tape)
    try:
        yield tape
    finally:
        active_replay.reset(token)


def sdk_key(configured: str | None) -> str | None:
    """Construct an SDK in replay mode without reading or using live credentials."""
    return (
        ("local-replay-no-network" if configured else None)
        if active_replay.get() is not None
        else configured
    )


def raise_recorded_error(error: dict[str, Any]) -> None:
    """Reproduce observed transport failures without importing tape-supplied code."""
    import anthropic
    import httpx
    import openai

    request = httpx.Request("POST", "https://recorded.invalid")
    message = str(error.get("message") or "Recorded provider failure")
    module, name, status = (
        str(error.get("module", "")),
        error.get("type"),
        error.get("status_code"),
    )
    sdk = (
        openai
        if module.startswith("openai")
        else anthropic
        if module.startswith("anthropic")
        else None
    )
    if sdk is not None:
        if status is not None:
            response = httpx.Response(
                int(status), request=request, json=error.get("body")
            )
            raise sdk.APIStatusError(message, response=response, body=error.get("body"))
        if name == "APITimeoutError":
            raise sdk.APITimeoutError(request=request)
        raise sdk.APIConnectionError(message=message, request=request)
    if name == "TimeoutError":
        raise TimeoutError(message)
    if module.startswith("httpx"):
        if status is not None:
            response = httpx.Response(int(status), request=request)
            raise httpx.HTTPStatusError(message, request=request, response=response)
        if name in {
            "TimeoutException",
            "ReadTimeout",
            "ConnectTimeout",
            "WriteTimeout",
            "PoolTimeout",
        }:
            raise httpx.TimeoutException(message, request=request)
        raise httpx.ConnectError(message, request=request)
    # Unexpected SDK/programming errors are not invented into a retryable outage.
    raise ReplayIncomplete(f"Unsupported recorded error type: {module}.{name}")
