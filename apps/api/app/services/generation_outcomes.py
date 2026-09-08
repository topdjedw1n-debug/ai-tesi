"""Stable recovery reasons; classify typed failures, never user-facing prose."""

from __future__ import annotations

from typing import Any

import httpx
import redis.exceptions
from anthropic import APIConnectionError as AnthropicConnectionError
from anthropic import APIStatusError as AnthropicStatusError
from minio.error import S3Error
from openai import APIConnectionError as OpenAIConnectionError
from openai import APIStatusError as OpenAIStatusError
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from urllib3.exceptions import HTTPError as UrllibHTTPError

from app.core.exceptions import QualityThresholdNotMetError
from app.services.circuit_breaker import CircuitBreakerOpenError

TEMPORARY_REASONS = frozenset(
    {
        "provider_temporarily_unavailable",
        "review_temporarily_unavailable",
        "artifact_temporarily_unavailable",
    }
)
MANUAL_REASONS = TEMPORARY_REASONS | {"provider_access_required", "cancelled_by_user"}

# Object storage: credentials vs. an object/bucket that should already exist.
_STORAGE_ACCESS_CODES = frozenset(
    {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}
)
_STORAGE_MISSING_CODES = frozenset({"NoSuchKey", "NoSuchBucket"})
# SQLSTATE classes that describe a lost/contended connection, never a schema or
# programming defect: 08 connection, 40 transaction rollback (deadlock,
# serialization), 53 insufficient resources, 57 operator intervention.
_DB_TEMPORARY_SQLSTATE_CLASSES = frozenset({"08", "40", "53", "57"})


def _temporary_for(stage: str) -> str:
    return (
        "review_temporarily_unavailable"
        if stage == "review"
        else "provider_temporarily_unavailable"
    )


def _database_failure_is_temporary(error: DBAPIError) -> bool:
    if error.connection_invalidated:
        return True
    sqlstate = getattr(error.orig, "sqlstate", None) or getattr(
        error.orig, "pgcode", None
    )
    if isinstance(sqlstate, str) and len(sqlstate) >= 2:
        return sqlstate[:2] in _DB_TEMPORARY_SQLSTATE_CLASSES
    # Drivers without SQLSTATE (SQLite): only the connection-level classes.
    return isinstance(error, OperationalError | InterfaceError)


class GenerationStageError(RuntimeError):
    def __init__(self, reason_code: str, detail: str, *, stage: str):
        super().__init__(detail)
        self.reason_code = reason_code
        self.stage = stage


class GenerationQualityError(QualityThresholdNotMetError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(detail)
        self.reason_code = reason_code
        self.stage = "review"


def failure_reason(error: BaseException, *, stage: str = "generation") -> str:
    cause: BaseException | None = error
    seen: set[int] = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(cause, GenerationStageError | GenerationQualityError):
            return cause.reason_code
        if isinstance(cause, S3Error):
            if cause.code in _STORAGE_ACCESS_CODES:
                return "provider_access_required"
            if stage == "export":
                # The text is saved; the file can be produced again later.
                return "artifact_temporarily_unavailable"
            if cause.code in _STORAGE_MISSING_CODES:
                # A frozen object that should already exist is gone: evidence,
                # not availability. Never guess it back into existence.
                return "checkpoint_integrity_error"
            return _temporary_for(stage)
        if stage == "export" and isinstance(
            cause, OSError | UrllibHTTPError | httpx.TransportError
        ):
            return "artifact_temporarily_unavailable"
        if isinstance(cause, OpenAIStatusError | AnthropicStatusError):
            body = cause.body if isinstance(cause.body, dict) else {}
            detail = body.get("error", body)
            code = (
                detail.get("code") or detail.get("type")
                if isinstance(detail, dict)
                else None
            )
            if cause.status_code in {401, 402, 403} or code == "insufficient_quota":
                return "provider_access_required"
            # Anthropic reports insufficient credits as invalid_request_error/400.
            if (
                cause.status_code == 400
                and isinstance(detail, dict)
                and "credit balance" in str(detail.get("message") or str(cause)).lower()
            ):
                return "provider_access_required"
            if cause.status_code in {408, 409, 429} or cause.status_code >= 500:
                return _temporary_for(stage)
            # A rejected review request (for example context length) is an
            # invalid review input. Any other 4xx (unknown model, bad
            # parameter) is a technical defect of the request, never an
            # academic judgement about the plan or the text.
            return "review_input_invalid" if stage == "review" else "unknown_failure"
        if isinstance(
            cause,
            TimeoutError
            | ConnectionError
            | httpx.TransportError
            | OpenAIConnectionError
            | AnthropicConnectionError
            | CircuitBreakerOpenError
            | redis.exceptions.ConnectionError
            | redis.exceptions.TimeoutError,
        ):
            # An open breaker only says the provider was failing moments ago.
            return _temporary_for(stage)
        if isinstance(cause, DBAPIError) and _database_failure_is_temporary(cause):
            return _temporary_for(stage)
        cause = cause.__cause__
    return "unknown_failure"


def outcome_fields(
    stage: str,
    reason_code: str | None,
    binding: dict[str, Any],
    attempt_id: str | None = None,
) -> dict[str, Any]:
    from app.services.academic_context import digest

    return {
        "stage": stage,
        "reason_code": reason_code,
        "retryability": "automatic"
        if reason_code in TEMPORARY_REASONS
        else "manual"
        if reason_code in MANUAL_REASONS
        else "none",
        "input_fingerprint": digest(binding),
        "attempt_id": attempt_id,
        "output_reference": attempt_id,
    }
