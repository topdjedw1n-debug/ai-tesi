"""Exercise real service retry loops with provider output interrupted once."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.services.ai_pipeline.generator import SectionGenerator
from app.services.ai_service import AIService
from app.services.cost_estimator import UsageTracker


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("service_kind", ["outline", "section"])
@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422, 429])
async def test_permanent_provider_rejection_does_not_repeat_paid_work(
    db_session, monkeypatch, provider, service_kind, status
):
    import importlib

    import httpx

    sdk = importlib.import_module(provider)
    monkeypatch.setattr(settings, provider.upper() + "_API_KEY", "qa-test-key")
    body = {
        "error": {
            "message": "Your credit balance is too low to access the Anthropic API.",
            "type": "insufficient_quota" if status == 429 else "invalid_request_error",
            "code": "insufficient_quota" if status == 429 else None,
        }
    }
    error = sdk.APIStatusError(
        "provider access rejected",
        response=httpx.Response(
            status, request=httpx.Request("POST", "https://provider.invalid/messages")
        ),
        body=body,
    )
    client = MagicMock()
    client.close = AsyncMock()
    create = AsyncMock(side_effect=error)
    if provider == "anthropic":
        client.messages.create = create
        model = "claude-opus-4-8"
    else:
        client.chat.completions.create = create
        model = "gpt-5.4"
    tracker = UsageTracker()
    service = (
        AIService(db_session, usage_tracker=tracker)
        if service_kind == "outline"
        else SectionGenerator(usage_tracker=tracker)
    )
    with (
        patch(
            provider
            + ".Async"
            + ("Anthropic" if provider == "anthropic" else "OpenAI"),
            return_value=client,
        ),
        patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
        pytest.raises(sdk.APIStatusError),
    ):
        await getattr(service, "_call_" + provider)(model, "A generation step")
    assert create.await_count == 1
    sleep.assert_not_awaited()
    assert tracker.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,model", [("openai", "gpt-5.4"), ("anthropic", "claude-opus-4-8")]
)
@pytest.mark.parametrize("service_kind", ["outline", "section"])
@pytest.mark.parametrize("fault", ["truncated", "empty"])
async def test_incomplete_output_recovers_on_same_model_and_counts_all_usage(
    db_session, monkeypatch, provider, model, service_kind, fault
):
    monkeypatch.setattr(settings, provider.upper() + "_API_KEY", "qa-test-key")
    tracker = UsageTracker()
    service = (
        AIService(db_session, usage_tracker=tracker)
        if service_kind == "outline"
        else SectionGenerator(usage_tracker=tracker)
    )
    text = (
        '{"sections":[{"title":"Introduzione","estimated_words":500}]}'
        if service_kind == "outline"
        else "Complete section text."
    )

    def response(content, truncated=False):
        if provider == "openai":
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=content),
                        finish_reason="length" if truncated else "stop",
                    )
                ],
                usage=SimpleNamespace(
                    total_tokens=30, prompt_tokens=10, completion_tokens=20
                ),
            )
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=content)],
            stop_reason="max_tokens" if truncated else "end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        )

    client = MagicMock()
    client.close = AsyncMock()
    create = AsyncMock(
        side_effect=[
            response(text[:10] if fault == "truncated" else "", fault == "truncated"),
            response(text),
        ]
    )
    sdk = "AsyncOpenAI" if provider == "openai" else "AsyncAnthropic"
    if provider == "openai":
        client.chat.completions.create = create
    else:
        client.messages.create = create
    with (
        patch(provider + "." + sdk, return_value=client) as factory,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await getattr(service, "_call_" + provider)(
            model, "A supported generation step"
        )
    assert create.await_count == 2
    assert tracker.total_tokens == 60
    if service_kind == "outline":
        assert result["sections"][0]["title"] == "Introduzione"
        assert result["tokens_used"] == 60
    else:
        assert result == text
    calls = [call.kwargs for call in create.call_args_list]
    assert {call["model"] for call in calls} == {model}
    cap = "max_completion_tokens" if provider == "openai" else "max_tokens"
    assert calls[1][cap] == calls[0][cap] * (2 if fault == "truncated" else 1)
    assert factory.call_args.kwargs["max_retries"] == 0
    assert factory.call_args.kwargs["timeout"] == 600.0
    assert calls[1]["timeout"] >= calls[0]["timeout"]
    assert calls[1]["timeout"] == min(600.0, max(180.0, calls[1][cap] * 0.045))
    assert client.close.await_count == (2 if service_kind == "outline" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("service_kind", ["outline", "section"])
@pytest.mark.parametrize("status", [408, 409, 429, 500, 529])
async def test_temporary_provider_failure_still_recovers(
    db_session, monkeypatch, provider, service_kind, status
):
    import importlib

    import httpx

    sdk = importlib.import_module(provider)
    monkeypatch.setattr(settings, provider.upper() + "_API_KEY", "qa-test-key")
    error = sdk.APIStatusError(
        "Temporarily unavailable",
        response=httpx.Response(
            status, request=httpx.Request("POST", "https://provider.invalid/messages")
        ),
        body={"error": {"type": "rate_limit_error" if status == 429 else "api_error"}},
    )
    text = "Complete section text."
    if provider == "anthropic":
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        )
        model = "claude-opus-4-8"
    else:
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=text), finish_reason="stop"
                )
            ],
            usage=None,
        )
        model = "gpt-5.4"
    client = MagicMock()
    client.close = AsyncMock()
    create = AsyncMock(side_effect=[error, response])
    if provider == "anthropic":
        client.messages.create = create
    else:
        client.chat.completions.create = create
    service = AIService(db_session) if service_kind == "outline" else SectionGenerator()
    with (
        patch(
            provider
            + ".Async"
            + ("Anthropic" if provider == "anthropic" else "OpenAI"),
            return_value=client,
        ),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await getattr(service, "_call_" + provider)(model, "A generation step")
    assert create.await_count == 2
    assert result["content"] == text if service_kind == "outline" else result == text
    assert {c.kwargs["model"] for c in create.call_args_list} == {model}


def test_writer_output_budget_matches_long_section_without_paid_truncation():
    from app.services.model_response_recovery import section_output_budget

    assert (
        section_output_budget(
            "Section Length: write approximately 1750 words", "claude-opus-4-8"
        )
        == 7000
    )
    assert (
        section_output_budget(
            "Section Length: write approximately 3000 words", "claude-opus-4-8"
        )
        == 12000
    )
    assert (
        section_output_budget(
            "Section Length: write approximately 1000000 words", "claude-opus-4-8"
        )
        == 16000
    )


def test_budget_reads_real_italian_prompt_and_preserves_legacy_cap():
    from app.models.document import Document
    from app.services.ai_pipeline.prompt_builder import PromptBuilder
    from app.services.model_response_recovery import (
        IncompleteModelResponse,
        ModelResponseRecovery,
        model_output_ceiling,
        section_output_budget,
    )

    document = Document(
        title="Didattica",
        topic="Intelligenza artificiale nella scuola secondaria",
        language="it",
        target_pages=18,
    )
    prompt = PromptBuilder.build_section_prompt(
        document=document,
        section_title="Didattica",
        section_index=2,
        target_word_count=1750,
    )
    assert section_output_budget(prompt, "claude-opus-4-8") == 7000
    assert section_output_budget(prompt, "claude-3-opus-20240229") == 4000
    recovery = ModelResponseRecovery(
        4000, model_output_ceiling("claude-3-opus-20240229")
    )
    with pytest.raises(IncompleteModelResponse):
        recovery.validate("partial", "max_tokens")
    assert recovery.max_tokens == 4000
