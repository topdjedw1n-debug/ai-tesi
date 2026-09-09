from functools import partial
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from app.models.document import DocumentProvenance
from app.services.ai_pipeline.rag_retriever import RAGRetriever
from app.services.citation_verifier import CitationVerifier, SourceInput
from app.services.model_recording import ReplayIncomplete, ReplayTape, replay_models
from app.services.replay_dependencies import recording_context
from tests.test_generation_worker import _seed_job


@pytest.mark.asyncio
async def test_actual_retrieval_and_identity_verifier_replay_external_inputs(
    db_session, monkeypatch
):
    doc, job = await _seed_job(db_session, email="external-replay@example.com")
    item = {
        "title": ["Nursing care of newborn thermal balance"],
        "author": [{"family": "Nurse"}],
        "issued": {"date-parts": [[2024]]},
        "DOI": "10.1000/thermal",
        "type": "journal-article",
        "abstract": "Newborn thermal balance and nursing care are assessed.",
    }
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "message": (
                    item if "/10.1000/" in request.url.path else {"items": [item]}
                )
            },
        )

    with patch(
        "httpx.AsyncClient",
        partial(httpx.AsyncClient, transport=httpx.MockTransport(respond)),
    ):
        token = recording_context.set(
            {"document_id": doc.id, "job_id": job.id, "worker_attempt": 1}
        )
        try:
            found = await RAGRetriever().search_crossref(
                "newborn thermal balance", limit=4
            )
            source = SourceInput(
                title=found[0].title,
                doi=found[0].doi,
                authors=found[0].authors,
                year=found[0].year,
            )
            verified = await CitationVerifier(cache_enabled=False).verify_source(source)
        finally:
            recording_context.reset(token)
    assert len(calls) == 2 and verified.status.value == "verified"
    events = (
        (
            await db_session.execute(
                select(DocumentProvenance).order_by(DocumentProvenance.id)
            )
        )
        .scalars()
        .all()
    )
    tape = ReplayTape.from_events(
        [{"event_type": e.event_type, "payload": e.payload} for e in events],
        job_id=job.id,
    )
    assert {d["kind"] for d in tape.dependencies} == {
        "scholarly_http",
        "citation_cache",
        "citation_http",
    }
    with (
        replay_models(tape),
        patch("httpx.AsyncClient", side_effect=AssertionError("network attempted")),
    ):
        replayed = await RAGRetriever().search_crossref(
            "newborn thermal balance", limit=4
        )
        replayed_verified = await CitationVerifier(cache_enabled=False).verify_source(
            source
        )
        tape.assert_complete()
    assert replayed == found
    assert replayed_verified.to_dict() == verified.to_dict()
    # Scoring is still real code. A different input cannot quietly reuse a
    # matching publication's verification record or fall back to the network.
    with replay_models(ReplayTape([], dependencies=tape.dependencies)):
        with pytest.raises(ReplayIncomplete):
            await CitationVerifier(cache_enabled=False).verify_source(
                SourceInput(title="Unrelated adult topic")
            )
