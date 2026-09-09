"""One policy block and one recorded, bounded provider boundary."""

import asyncio
import json
import math

from app.services.generation_operations import recorded_provider_call
from app.services.generation_policy import RecordingPersistenceError
from app.services.model_recording import operation_section

from .warnings import ExecutionStop

POLICY = {
    "placeholder_phrases": (
        "da verificare",
        "soggetta a verifica",
        "[citation needed]",
        "TODO",
    ),
    "stage_progress": {
        "sources": 5,
        "outline": 25,
        "writing": 35,
        "references": 90,
        "assembling": 95,
    },
    "model": "claude-opus-4-8",
    "max_sources": 40,
    "queries_per_scope": 3,
    "minimum_evidence_sources": 2,
    "json_min_tokens": 8000,
    "structure_tokens_per_node": 400,
    "json_multiplier": 2,
    "tokens_per_word": 1.6,
    "output_margin": 1.3,
    "truncation_multiplier": 2,
    "provider_attempts": 3,
    "retry_seconds": (5, 20, 60),
    "cost_ceiling_cents": 500,
    "calls_per_section": 3,
    "extra_calls": 6,
    "heartbeat_seconds": 15,
    "provider_timeout_seconds": 240,
    "words_per_page": 250,
    "short_ratio": 0.7,
    "long_ratio": 1.4,
    "summary_chars": 1200,
    "chars_per_token": 4,
    "search_concurrency": 6,
    "review_tokens": 8000,
}
_PENDING = set()


def output_budget(stage, size):
    if stage in {"S1", "S3"}:
        return max(
            POLICY["json_min_tokens"],
            POLICY["json_multiplier"] * size * POLICY["structure_tokens_per_node"],
        )
    return max(1, math.ceil(size * POLICY["tokens_per_word"] * POLICY["output_margin"]))


def _observe_late(task):
    _PENDING.discard(task)
    if not task.cancelled():
        task.exception()  # The recorder retains the late response; never write a section.


async def model_call(ctx, prompt, *, budget, purpose, section_index=None):
    request = {
        "model": ctx.model,
        "max_tokens": budget,
        "messages": [{"role": "user", "content": prompt}],
    }
    token = operation_section.set(section_index)
    try:
        for attempt in range(POLICY["provider_attempts"]):
            await ctx.check_budget(budget, prompt)
            task = asyncio.create_task(
                recorded_provider_call(
                    ctx.provider,
                    provider="anthropic",
                    model=ctx.model,
                    request=request,
                    usage_tracker=ctx.usage,
                    purpose=purpose,
                )
            )
            _PENDING.add(task)
            task.add_done_callback(_observe_late)
            try:
                response = await asyncio.shield(task)
            except (RecordingPersistenceError, asyncio.CancelledError):
                raise
            except Exception as error:
                status = getattr(error, "status_code", None)
                if (
                    status in {401, 403}
                    or status == 400
                    and any(
                        w in str(error).lower()
                        for w in ("balance", "credit", "billing")
                    )
                ):
                    raise ExecutionStop(
                        "provider_access",
                        "Недоступний обліковий запис моделі або вичерпано баланс.",
                    ) from error
                temporary = (
                    status in {408, 409, 429}
                    or status is not None
                    and status >= 500
                    or isinstance(error, ConnectionError | TimeoutError)
                    or type(error).__name__ in {"APIConnectionError", "APITimeoutError"}
                )
                if not temporary or attempt + 1 == POLICY["provider_attempts"]:
                    raise ExecutionStop(
                        "provider_unusable_response",
                        "Модель не повернула придатної відповіді після обмежених спроб.",
                    ) from error
                await asyncio.sleep(POLICY["retry_seconds"][attempt])
                continue
            await ctx.account()
            text = "\n".join(
                b.text for b in response.content if getattr(b, "type", None) == "text"
            ).strip()
            if not text:
                raise ExecutionStop(
                    "provider_unusable_response", "Модель повернула порожню відповідь."
                )
            return text, response.stop_reason == "max_tokens"
    finally:
        operation_section.reset(token)


def sparse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        return value
    except (ValueError, TypeError) as error:
        raise ExecutionStop(
            "provider_unusable_response",
            "Структуру відповіді моделі не вдалося прочитати.",
        ) from error
