"""Recovery from transient scholarly failures and malformed model plans."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.auth import User
from app.models.document import Document, DocumentOutline
from app.services.ai_pipeline.rag_retriever import RAGRetriever
from app.services.ai_service import AIService
from app.services.outline_validation import validate_outline


def test_legacy_unspecified_word_targets_remain_resumable():
    plan = {
        "sections": [
            {
                "title": "Introduzione",
                "target_word_count": None,
                "word_count": 0,
                "estimated_words": "1,200",
            }
        ]
    }
    assert validate_outline(plan)["sections"][0] == {
        "title": "Introduzione",
        "estimated_words": 1200,
    }
    assert plan["sections"][0]["word_count"] == 0


def test_generated_oversize_chapter_needs_split_before_writing():
    with pytest.raises(ValueError, match="split longer"):
        validate_outline(
            {"sections": [{"title": "Chapter", "estimated_words": 6000}]},
            generated=True,
        )


def scholarly_client(payload):
    client = MagicMock()
    client.get = AsyncMock(
        return_value=httpx.Response(
            200, json=payload, request=httpx.Request("GET", "https://example.org/works")
        )
    )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["crossref", "openalex"])
async def test_scholarly_outage_recovers_without_restarting_order(tmp_path, provider):
    payload = (
        {"message": {"items": [{"title": ["Valid source"]}]}}
        if provider == "crossref"
        else {"results": [{"title": "Valid source"}]}
    )
    client = scholarly_client(payload)
    good = client.get.return_value
    failed = httpx.Response(429, request=good.request)
    client.get.side_effect = [failed, httpx.ReadTimeout("temporary"), good]
    with (
        patch("httpx.AsyncClient", return_value=client),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        sources = await getattr(
            RAGRetriever(cache_dir=str(tmp_path)), f"search_{provider}"
        )("topic", raise_on_error=True)
    assert [source.title for source in sources] == ["Valid source"]
    assert client.get.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["crossref", "openalex"])
async def test_bad_scholarly_record_does_not_discard_valid_neighbors(
    tmp_path, provider
):
    payload = (
        {
            "message": {
                "items": [
                    None,
                    {
                        "title": ["Valid source"],
                        "author": [{"name": "World Health Organization"}],
                    },
                ]
            }
        }
        if provider == "crossref"
        else {
            "results": [
                None,
                {
                    "title": "Valid source",
                    "authorships": [{"author": {"display_name": "Ada Rossi"}}],
                },
            ]
        }
    )
    with patch("httpx.AsyncClient", return_value=scholarly_client(payload)):
        sources = await getattr(
            RAGRetriever(cache_dir=str(tmp_path)), f"search_{provider}"
        )("topic", raise_on_error=True)
    assert [source.title for source in sources] == ["Valid source"]
    assert sources[0].authors


@pytest.mark.asyncio
async def test_openalex_uses_configured_key_without_putting_secret_in_url(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "OPENALEX_API_KEY", "test-private-key")
    client = scholarly_client({"results": []})
    with patch("httpx.AsyncClient", return_value=client):
        await RAGRetriever(cache_dir=str(tmp_path)).search_openalex("topic")
    assert (
        client.get.call_args.kwargs["headers"]["Authorization"]
        == "Bearer test-private-key"
    )
    assert "api_key" not in client.get.call_args.kwargs["params"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        {"content": "not JSON"},
        {"sections": []},
        {"sections": ["Introduction"]},
        {"sections": [{"title": "Introduction", "estimated_words": "many"}]},
    ],
)
async def test_malformed_outline_is_repaired_before_persisting(
    db_session, monkeypatch, bad
):
    user = User(email="outline-repair@example.com", is_active=True)
    db_session.add(user)
    await db_session.flush()
    doc = Document(
        user_id=user.id,
        title="A supported order",
        topic="Nursing care and prevention",
        status="generating",
        ai_provider="anthropic",
        ai_model="claude-opus-4-8",
    )
    db_session.add(doc)
    await db_session.commit()
    provider = AsyncMock(
        side_effect=[
            {**bad, "tokens_used": 20},
            {
                "sections": [{"title": "Introduzione", "estimated_words": 1000}],
                "tokens_used": 50,
            },
        ]
    )
    monkeypatch.setattr(AIService, "_call_ai_provider", provider)
    await AIService(db_session).generate_outline(doc.id, user.id)
    await db_session.refresh(doc)
    assert doc.outline["sections"][0]["title"] == "Introduzione"
    assert doc.status == "generating"
    assert doc.tokens_used == 70
    assert (
        await db_session.scalar(select(func.count()).select_from(DocumentOutline)) == 1
    )
    assert provider.await_count == 2
    assert {call.kwargs["model"] for call in provider.call_args_list} == {
        "claude-opus-4-8"
    }
