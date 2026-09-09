"""Record external retrieval/cache/file inputs without replacing business gates."""

from __future__ import annotations

import base64
import functools
import inspect
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from typing import Any
from uuid import uuid4

import httpx

from app.services.academic_context import digest
from app.services.model_recording import active_replay, json_value

dependency_parent: ContextVar[str | None] = ContextVar(
    "dependency_parent", default=None
)

recording_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "dependency_recording", default=None
)


def _request(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): _request(v)
            for k, v in value.items()
            if str(k).lower()
            not in {"api_key", "apikey", "authorization", "headers", "k", "u"}
        }
    if isinstance(value, list | tuple):
        return [_request(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _request(asdict(value))
    return json_value(value)


def _encode(value: Any, codec: str) -> Any:
    if codec == "sources":
        return None if value is None else [asdict(s) for s in value]
    if codec == "verification":
        return value.to_dict() if value is not None else None
    if codec == "bytes":
        return base64.b64encode(value).decode("ascii")
    if codec == "http_response":
        return {
            "status_code": value.status_code,
            "body": base64.b64encode(value.content).decode("ascii"),
            "content_type": value.headers.get("content-type"),
        }
    if codec == "http":
        status, response = value
        return {
            "status": status,
            "response": (
                None
                if response is None
                else {
                    "status_code": response.status_code,
                    "body": base64.b64encode(response.content).decode("ascii"),
                    "content_type": response.headers.get("content-type"),
                }
            ),
        }
    return json_value(value)


def _decode(value: Any, codec: str) -> Any:
    if codec == "sources":
        from app.services.ai_pipeline.rag_retriever import SourceDoc

        return None if value is None else [SourceDoc(**s) for s in value]
    if codec == "verification":
        from app.services.citation_verifier import VerificationResult

        return VerificationResult.from_dict(value) if value is not None else None
    if codec == "bytes":
        return base64.b64decode(value, validate=True)
    if codec == "http_response":
        return httpx.Response(
            value["status_code"],
            content=base64.b64decode(value["body"], validate=True),
            headers=(
                {"content-type": value["content_type"]}
                if value.get("content_type")
                else {}
            ),
            request=httpx.Request("POST", "https://recorded.invalid"),
        )
    if codec == "http":
        r = value["response"]
        return value["status"], (
            None
            if r is None
            else httpx.Response(
                r["status_code"],
                content=base64.b64decode(r["body"], validate=True),
                headers=(
                    {"content-type": r["content_type"]} if r.get("content_type") else {}
                ),
                request=httpx.Request("GET", "https://recorded.invalid"),
            )
        )
    return value


def recorded_dependency(kind: str, *, codec: str = "json"):
    """Wrap an external adapter, including cache hits; never wrap validators."""

    def decorate(function):
        signature = inspect.signature(function)

        @functools.wraps(function)
        async def wrapped(*args, **kwargs):
            context, tape = recording_context.get(), active_replay.get()
            if context is None and tape is None:
                return await function(*args, **kwargs)
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            request = _request(
                {k: v for k, v in bound.arguments.items() if k != "self"}
            )
            fingerprint = digest(request)
            if tape is not None:
                row = tape.dependency(kind, fingerprint)
                if row.get("outcome") != "received":
                    # This recorded adapter failed. Reproduce a transport
                    # failure; do not create a successful empty source list.
                    if row.get("status_code"):
                        response = httpx.Response(
                            row["status_code"],
                            request=httpx.Request("GET", "https://recorded.invalid"),
                        )
                        raise httpx.HTTPStatusError(
                            "Recorded provider failure",
                            request=response.request,
                            response=response,
                        )
                    raise httpx.ConnectError(
                        row.get("error", "Recorded external dependency failure")
                    )
                return _decode(row["response"], codec)
            from app.services.generation_operations import _append

            dependency_id = uuid4().hex
            payload = {
                "dependency_id": dependency_id,
                "parent_dependency_id": dependency_parent.get(),
                "kind": kind,
                "input_fingerprint": fingerprint,
                "request": request,
                "codec": codec,
            }
            parent_token = dependency_parent.set(dependency_id)
            try:
                result = await function(*args, **kwargs)
            except Exception as error:
                await _append(
                    context,
                    {
                        **payload,
                        "outcome": "failed",
                        "error": type(error).__name__,
                        "status_code": getattr(
                            getattr(error, "response", None), "status_code", None
                        ),
                    },
                    event_type="generation_dependency",
                )
                raise
            finally:
                dependency_parent.reset(parent_token)
            await _append(
                context,
                {**payload, "outcome": "received", "response": _encode(result, codec)},
                event_type="generation_dependency",
            )
            return result

        return wrapped

    return decorate


@recorded_dependency("quality_http", codec="http_response")
async def recorded_http(
    self: Any, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    """The existing HTTP client remains responsible for the actual request."""
    return await getattr(self, method.lower())(url, **kwargs)


@recorded_dependency("retrieval_clock")
async def retrieval_time(query: str, provider: str, page: int) -> str:
    """Search time is prompt input too; replay must retain the actual timestamp."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
