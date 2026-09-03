"""Runtime contracts for the AI provider SDKs used in production."""

import inspect
from importlib.metadata import version

import pytest
from anthropic import AsyncAnthropic
from openai.resources.chat.completions import AsyncCompletions
from packaging.version import Version


def test_ai_provider_sdk_versions_meet_runtime_minimums() -> None:
    assert Version(version("anthropic")) >= Version("0.76.0")
    assert Version(version("openai")) >= Version("2.15.0")


@pytest.mark.asyncio
async def test_anthropic_sdk_supports_messages_api() -> None:
    client = AsyncAnthropic(api_key="test-key")
    try:
        assert hasattr(client, "messages")
    finally:
        await client.close()


def test_openai_sdk_accepts_max_completion_tokens() -> None:
    parameters = inspect.signature(AsyncCompletions.create).parameters
    assert "max_completion_tokens" in parameters
