"""Recover incomplete output without retrying permanent provider rejections."""

import re
from dataclasses import dataclass

from anthropic import APIStatusError as AnthropicStatusError
from openai import APIStatusError as OpenAIStatusError


def is_permanent_provider_error(error: Exception) -> bool:
    """Follow explicit causes retained by AIService's outline error wrapper."""
    from app.services.generation_outcomes import TEMPORARY_REASONS, GenerationStageError

    cause: BaseException | None = error
    seen: set[int] = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if (
            isinstance(cause, GenerationStageError)
            and cause.reason_code not in TEMPORARY_REASONS
        ):
            return True
        if isinstance(cause, AnthropicStatusError | OpenAIStatusError):
            status = cause.status_code
            if 400 <= status < 500 and status not in {408, 409, 429}:
                return True
            body = cause.body
            if status == 429 and isinstance(body, dict):
                detail = body.get("error", body)
                if isinstance(detail, dict) and (
                    detail.get("code") == "insufficient_quota"
                    or detail.get("type") == "insufficient_quota"
                ):
                    return True
        cause = cause.__cause__
    return False


def section_output_budget(prompt: str, model: str) -> int:
    """Reserve enough output for the writer's existing per-section word target."""
    match = re.search(r"Section Length: write approximately (\d+) words", prompt)
    base = 8000 if model.startswith("gpt-5") else 4000
    ceiling = model_output_ceiling(model)
    return (
        min(ceiling, max(base, int(match.group(1)) * 4))
        if match
        else min(base, ceiling)
    )


def model_output_ceiling(model: str) -> int:
    # Older selectable Claude models retain the pre-existing request limit.
    # The larger budget is for the current generation models.
    return 4000 if model.startswith("claude-3") else 16000


class IncompleteModelResponse(ValueError):
    pass


@dataclass
class ModelResponseRecovery:
    max_tokens: int = 4000
    output_ceiling: int = 16000

    @property
    def timeout_seconds(self) -> float:
        # Longer non-streaming responses need more time. The independent
        # worker heartbeat and cancellation remain active during this wait.
        return min(600.0, max(180.0, self.max_tokens * 0.045))

    def validate(self, content: str | None, stop_reason: str | None) -> str:
        if stop_reason in ("max_tokens", "length"):
            # Reissue the same task and model with room for a complete answer;
            # never concatenate partial JSON or duplicate section paragraphs.
            self.max_tokens = min(self.max_tokens * 2, self.output_ceiling)
            raise IncompleteModelResponse("Model output reached its token limit")
        if not isinstance(content, str) or not content.strip():
            raise IncompleteModelResponse("Model returned empty text")
        return content
