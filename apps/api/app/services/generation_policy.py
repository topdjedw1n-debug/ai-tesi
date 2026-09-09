"""Generation policy belongs to a new job, never to historical work statuses."""

from contextvars import ContextVar

import httpx
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import CitationIntegrityError, QualityThresholdNotMetError
from app.services.generation_outcomes import GenerationStageError
from app.services.model_response_recovery import IncompleteModelResponse

PLATFORM_FIRST = "platform-first-v1"
warning_mode: ContextVar[bool] = ContextVar("generation_warning_mode", default=False)
translation_cache: ContextVar[dict | None] = ContextVar(
    "generation_translation_cache", default=None
)


class RecordingPersistenceError(BaseException):
    """Storage failure must cross optional reviewer catch-all handlers.

    The generation worker catches this signal and records a technical failure.
    Like cancellation, it cannot be converted into an unchecked reviewer result.
    """


def optional_stage_failure(error: Exception) -> bool:
    """Only known academic/provider failures can become warnings; bugs propagate."""
    chain = []
    current = error
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    if any(isinstance(e, SQLAlchemyError) for e in chain):
        return False
    return any(
        isinstance(
            e,
            GenerationStageError
            | IncompleteModelResponse
            | CitationIntegrityError
            | QualityThresholdNotMetError
            | TimeoutError
            | httpx.HTTPError,
        )
        or type(e).__module__.startswith(("openai", "anthropic"))
        or (
            isinstance(e, ValueError)
            and str(e)
            in {"OpenAI API key not configured", "Anthropic API key not configured"}
        )
        for e in chain
    )


class AdvisoryConfig:
    """Keep checks enabled and their findings intact; change only blocking policy."""

    def __init__(self, config):
        self.config = config

    def __getattr__(self, name):
        if name == "CITATION_VERIFICATION_POLICY":
            return "mark_only"
        if name == "CLAIM_VERIFICATION_BLOCKING":
            return False
        return getattr(self.config, name)
