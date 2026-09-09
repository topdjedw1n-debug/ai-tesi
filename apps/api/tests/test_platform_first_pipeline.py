"""Synthetic transport responses, real worker/checks/export, then offline replay.

This proves local plumbing and warning behaviour, never academic or live quality.
"""

import importlib.util
import json
import os
import subprocess
import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.document import DocumentProvenance
from app.services.background_jobs import BackgroundJobService
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_operations import operation_purpose
from app.services.generation_profile import generation_profile_sha256
from app.services.storage_service import StorageService
from tests.test_generation_worker import _seed_job

RUNNER = Path(__file__).parents[1] / "scripts/replay_generation.py"
spec = importlib.util.spec_from_file_location("offline_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "sparse",
        "reviewer_reject",
        "prep_reject",
        "standard",
        "missing_abstract",
        "humanizer_unavailable",
        "unresolved",
    ],
)
async def test_source_shortage_bad_reviews_grammar_reach_real_docx_and_replay(
    db_session, monkeypatch, tmp_path, scenario
):
    for name, value in {
        "SOURCE_GROUNDING_ENABLED": True,
        "SOURCE_PACK_PREFLIGHT_ENABLED": True,
        "SOURCE_PACK_BILINGUAL_ENABLED": False,
        "GROUNDING_GATE_ENABLED": True,
        "QUALITY_GATES_ENABLED": True,
        "QUALITY_MAX_REGENERATE_ATTEMPTS": 3,
        "QUALITY_PANEL_ENABLED": False,
        "CITATION_VERIFICATION_ENABLED": True,
        "CLAIM_VERIFICATION_ENABLED": True,
        "CLAIM_VERIFICATION_BLOCKING": True,
        "PROVENANCE_LEDGER_ENABLED": True,
        "HUMANIZER_ENABLED": scenario == "humanizer_unavailable",
        "HUMANIZER_PROVIDER": None,
        "HUMANIZER_MODEL": None,
        "LANGUAGETOOL_API_URL": "https://languagetool.local.invalid/v2",
        "LANGUAGETOOL_DISABLED_CATEGORIES": "TYPOS,CASING",
        "QUALITY_GATES_MAX_CONTEXT_SECTIONS": 2,
        "AI_ENABLE_FALLBACK": False,
        "AI_DETECTION_ENABLED": False,
        "METHODOLOGY_REQUIRED_FOR_GENERATION": False,
        "OPENAI_API_KEY": "synthetic-never-sent",
        "ANTHROPIC_API_KEY": None,
    }.items():
        monkeypatch.setattr(settings, name, value)
    document, job = await _seed_job(
        db_session, email=f"synthetic-{scenario}@example.invalid"
    )
    document.ai_provider, document.ai_model = "openai", "gpt-4"
    document.outline = None
    job.request_payload = {
        **job.request_payload,
        "generation_policy": "platform-first-v1",
        "profile_sha256": generation_profile_sha256(document, job.user_id),
        "generation_contract_sha256": generation_contract_sha256(
            document, None, job.request_payload["additional_requirements"]
        ),
    }
    await db_session.commit()
    ids = document.id, job.user_id, job.id
    calls = []

    async def model_response(**kwargs):
        purpose = operation_purpose.get()
        calls.append(purpose)
        if (
            scenario == "humanizer_unavailable"
            and purpose is None
            and calls.count(None) == 2
        ):
            raise httpx.ReadTimeout("Synthetic unavailable editor")
        from app.services.academic_context import ACADEMIC_FUNCTIONS

        if purpose == "outline":
            outline = {
                "academic_plan": {
                    "research_question": "Which methods support recovery?",
                    "objectives": ["Compare recovery designs"],
                },
                "sections": [
                    {
                        "title": "Introduzione",
                        "estimated_words": 500,
                        "main_points": ["Comparison of study designs and populations"],
                        "academic_functions": list(ACADEMIC_FUNCTIONS),
                        "evidence_keys": []
                        if scenario in {"sparse", "prep_reject"}
                        else ["Researcher2024"],
                    }
                ],
            }
            content = json.dumps(outline)
        elif purpose == "academic_plan_preparation":
            content = json.dumps({"sections": [{"title": "Wrong replacement chapter"}]})
        elif purpose and "review" in purpose:
            content = json.dumps(
                {
                    "functions": {
                        k: {
                            "satisfied": False,
                            "evidence_quote": "",
                            "reason": "Synthetic academic finding",
                        }
                        for k in ACADEMIC_FUNCTIONS
                    },
                    "requirements_satisfied": False,
                    "source_coverage": [
                        {
                            "section_index": 1,
                            "supported": False,
                            "source_keys": [],
                            "reason": "Evidence gap",
                        }
                    ],
                    "issues": [
                        {"severity": "major", "reason": "Synthetic academic finding"}
                    ],
                }
            )
        else:
            content = (
                "Il confronto tra gli studi considera le differenze nei metodi e nelle popolazioni. "
                * 40
            )
            if scenario == "unresolved":
                content += " Una citazione [Selix2015]."
            if scenario == "standard":
                content += '[STD:who]\n<STANDARD_REFERENCES_JSON>[{"id":"who","title":"WHO standard manual","authors":["WHO"],"year":null}]</STANDARD_REFERENCES_JSON>'
        return SimpleNamespace(
            id="synthetic-model-response",
            choices=[
                SimpleNamespace(
                    finish_reason="stop", message=SimpleNamespace(content=content)
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=1200, completion_tokens=600, total_tokens=1800
            ),
        )

    sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=model_response)),
        close=AsyncMock(),
    )

    def external_response(request):
        if "languagetool" in str(request.url):
            return httpx.Response(
                200, json={"matches": [{"rule": {"id": "SYNTHETIC_RULE"}}] * 100}
            )
        if scenario != "sparse" and "crossref" in str(request.url):
            item = {
                "title": [document.topic],
                "author": [{"family": "Researcher"}],
                "issued": {"date-parts": [[2024]]},
                "DOI": "10.1000/recorded-recovery",
                "type": "journal-article",
                "abstract": document.topic
                + ". Comparison of study designs and populations reveals different recovery methods.",
            }
            if scenario == "missing_abstract":
                item.pop("abstract")
            return httpx.Response(
                200,
                json={
                    "message": item
                    if "/10.1000/" in request.url.path
                    else {"items": [item]}
                },
            )
        return httpx.Response(
            200, json={"message": {"items": []}, "results": [], "data": []}
        )

    objects = runner.LocalObjects(tmp_path)
    with (
        patch("openai.AsyncOpenAI", return_value=sdk),
        patch(
            "httpx.AsyncClient",
            partial(
                httpx.AsyncClient, transport=httpx.MockTransport(external_response)
            ),
        ),
        patch("app.services.background_jobs._redis_client", runner.LocalRedis()),
        patch.object(StorageService, "client", property(lambda self: objects)),
    ):
        await BackgroundJobService.generate_full_document_async(
            document_id=ids[0],
            user_id=ids[1],
            job_id=ids[2],
            additional_requirements=job.request_payload["additional_requirements"],
        )
    await db_session.refresh(document)
    await db_session.refresh(job)
    assert job.status == "completed" and document.docx_path
    assert calls.count(None) == (2 if scenario == "humanizer_unavailable" else 1)
    # One writer and at most the configured editor; no quality-triggered rewrite.
    if scenario == "sparse":
        assert len(calls) == 2
    if scenario == "unresolved":
        assert (
            "[Selix2015]" not in document.content
            and "(Selix, 2015)" in document.content
        )
    if scenario == "standard":
        assert (
            "STANDARD_REFERENCES_JSON" not in document.content
            and "WHO" in document.content
        )
    events = (
        (
            await db_session.execute(
                select(DocumentProvenance)
                .where(DocumentProvenance.document_id == ids[0])
                .order_by(DocumentProvenance.id)
            )
        )
        .scalars()
        .all()
    )
    assert {e.stage for e in events if e.event_type == "generation_warning"} >= {
        "retrieval",
        "review",
        "quality",
    }
    if scenario == "prep_reject":
        assert any(
            e.stage == "preparation" and e.event_type == "generation_warning"
            for e in events
        )
        assert document.outline["sections"][0]["title"] == "Introduzione"
    if scenario == "missing_abstract":
        assert any(
            e.event_type == "generation_dependency"
            and e.payload.get("kind") == "retrieval_clock"
            and e.payload["request"].get("page") == 0
            for e in events
        )
    if scenario == "humanizer_unavailable":
        assert any(
            e.event_type == "generation_warning" and e.stage == "humanization"
            for e in events
        )
    snapshot = next(
        e.payload for e in events if e.event_type == "generation_replay_inputs"
    )
    assert (
        snapshot["replay_settings"]["LANGUAGETOOL_DISABLED_CATEGORIES"]
        == "TYPOS,CASING"
    )
    assert "OPENAI_API_KEY" not in snapshot["replay_settings"]
    # An exported tape may be edited; connection targets still cannot override isolation.
    snapshot["replay_settings"][
        "DATABASE_URL"
    ] = "postgresql+asyncpg://never-connect.invalid/prod"
    recording = tmp_path / "synthetic-recording.json"
    recording.write_text(
        json.dumps(
            {
                "origin": "synthetic_transport_not_real_model",
                "document_provenance": [
                    {"event_type": e.event_type, "payload": e.payload} for e in events
                ],
            }
        )
    )
    replay = subprocess.run(
        [sys.executable, str(RUNNER), str(recording), str(tmp_path / "replay")],
        text=True,
        capture_output=True,
        timeout=90,
        env={"PATH": os.environ.get("PATH", "")},
    )
    report = json.loads((tmp_path / "replay/report.json").read_text())
    assert replay.returncode == 0, (report, replay.stderr[-4000:])
    assert report["status"] == "completed" and report["actual_spend_usd"] == 0
    assert len(report["consumed"]) == len(calls) and report["artifacts"]
