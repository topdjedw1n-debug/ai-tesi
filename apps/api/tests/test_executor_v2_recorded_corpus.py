"""Recorded job12 sources/writer texts are fixtures, never claimed as v2 live proof."""

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.document import AIGenerationJob, Document, DocumentProvenance
from app.services.academic_context import digest
from app.services.executor_v2.run import Context, run
from app.services.executor_v2.scopes import fixed_index, flatten, title_identity
from app.services.generation_worker import ClaimedGenerationJob, utc_now
from app.services.model_recording import ReplayTape, _sdk_value, replay_models
from app.services.replay_dependencies import recorded_dependency
from app.services.replay_snapshot import row_data
from app.services.storage_service import StorageService
from tests.test_executor_v2 import no_external_network as no_external_network
from tests.test_executor_v2 import (
    response,
    seed,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/executor_v2/job12.json").read_text()
)


def model_scopes():
    roots, parents = [], {}
    terms = {
        "1": "perinatal nursing assessment prevention",
        "2": "neonatal thermoregulation nursing diagnosis",
        "3": "newborn respiratory transition Apgar nursing",
        "4": "skin to skin breastfeeding attachment rooming in",
    }
    for line in fixed_index(FIXTURE["brief"]["additional_requirements"]):
        number = re.search(r"\d+(?:\.\d+)*", line)[0]
        node = {
            "title": line,
            "required": True,
            "terms_local": [title_identity(line)],
            "terms_en": [terms[number[0]]],
            "children": [],
        }
        parent = parents.get(number.rsplit(".", 1)[0]) if "." in number else None
        (parent["children"] if parent else roots).append(node)
        parents[number] = node
    for i, root in enumerate(roots):
        root["children"].append(
            {
                "title": "Evidence limitations",
                "required": False,
                "terms_local": ["limiti delle evidenze"],
                "terms_en": ["evidence limitations"],
                "children": [],
            }
        )
    return roots


def model_plan():
    nodes = copy.deepcopy(model_scopes())
    # Same canonical traversal used by the server after retaining concepts.
    for i, node in enumerate(flatten(nodes), 1):
        node["scope_id"] = f"scope-{i}"
    sections = copy.deepcopy(FIXTURE["outline"]["sections"])
    result = []
    keys = []
    for doi, meta in FIXTURE["metadata"].items():
        keys.append(
            "K"
            + digest(
                {
                    "doi": meta.get("doi") or doi,
                    "title": meta["title"],
                    "year": meta["year"],
                }
            )[:12]
        )
    for i, s in enumerate(sections):
        scope_ids = [
            n["scope_id"]
            for n in flatten(nodes[max(0, i - 1) : i] if 1 <= i <= 4 else [])
        ]
        result.append(
            {
                "title": s["title"],
                "purpose": s.get("description") or s["title"],
                "main_points": s.get("main_points") or [s["title"]],
                "scope_ids": scope_ids,
                "evidence_keys": keys,
                "target_words": 750,
            }
        )
    return {"sections": result}


def test_real_supervisor_index_and_concepts_survive():
    titles = fixed_index(FIXTURE["brief"]["additional_requirements"])
    assert len(titles) == 18
    assert len([t for t in titles if t.startswith("CAPITOLO")]) == 4
    assert any("3.3.2 Problema Collaborativo" in t for t in titles)
    assert fixed_index("1. Обсяг 60 сторінок\n2. Шрифт Times") == []


@pytest.mark.asyncio
async def test_recorded_job12_to_docx_and_replay(db_session, monkeypatch, tmp_path):
    from datetime import timedelta

    from app.services.executor_v2 import sources

    claimed, _, doc, case = await seed(
        db_session, requirements=FIXTURE["brief"]["additional_requirements"]
    )
    doc = await db_session.get(Document, claimed.document_id)
    for name, value in FIXTURE["brief"].items():
        setattr(doc, name, value)
    from dataclasses import replace

    from app.services.generation_contract import generation_contract_sha256
    from app.services.task_contract import task_contract_sha256

    doc.contract_confirmed_sha256 = task_contract_sha256(doc)
    initial_job = await db_session.get(AIGenerationJob, claimed.id)
    initial_job.request_payload = {
        **initial_job.request_payload,
        "generation_contract_sha256": generation_contract_sha256(
            doc, case, claimed.additional_requirements
        ),
    }
    claimed = replace(claimed, request_payload=initial_job.request_payload)
    await db_session.commit()

    # Queries belong to v2; candidates are selected ONLY from actual recorded
    # Crossref/OpenAlex responses. This is a fixture simulation, not old-query replay.
    async def search_impl(provider, query):
        candidates = FIXTURE["search"][provider]
        words = set(re.findall(r"\w{4,}", query.lower()))
        return sorted(
            copy.deepcopy(candidates),
            key=lambda r: len(
                words
                & set(
                    re.findall(
                        r"\w{4,}",
                        (r["title"] + " " + (r.get("abstract") or "")).lower(),
                    )
                )
            ),
            reverse=True,
        )[:10]

    async def verify_impl(candidate):
        metadata = FIXTURE["metadata"].get((candidate.get("doi") or "").lower())
        return copy.deepcopy(metadata) if metadata else {"status": "not_found"}

    monkeypatch.setattr(
        sources, "search", recorded_dependency("executor_search")(search_impl)
    )
    monkeypatch.setattr(
        sources, "verify", recorded_dependency("executor_verify")(verify_impl)
    )
    # references.py imports this function separately.
    from app.services.executor_v2 import references

    monkeypatch.setattr(
        references, "verify", recorded_dependency("executor_verify")(verify_impl)
    )
    names = {}
    for key, doi in FIXTURE["original_keys"].items():
        meta = FIXTURE["metadata"][doi]
        names[key] = (
            "K"
            + digest(
                {
                    "doi": meta.get("doi") or doi,
                    "title": meta["title"],
                    "year": meta["year"],
                }
            )[:12]
        )
    responses = [
        response(json.dumps({"nodes": model_scopes()}, ensure_ascii=False)),
        response(json.dumps(model_plan(), ensure_ascii=False)),
    ]
    for writer in FIXTURE["writers"]:
        recorded = copy.deepcopy(writer["response"])
        for block in recorded["content"]:
            if block.get("type") == "text":
                for old, new in names.items():
                    block["text"] = re.sub(
                        r"(?<=[\[; ])" + re.escape(old) + r"(?=[;\],])",
                        new,
                        block["text"],
                    )
        responses.append(_sdk_value(recorded))
    responses.append(_sdk_value(FIXTURE["review"]["response"]))

    async def provider(self, **request):
        return responses.pop(0)

    monkeypatch.setattr(Context, "provider", provider)
    artifacts = []

    async def upload(self, name, data, content_type):
        artifacts.append(data)
        return "s3://offline-fixture/" + name

    monkeypatch.setattr(StorageService, "upload_file", upload)
    result = await run(claimed)
    db_session.expire_all()
    row = await db_session.get(AIGenerationJob, claimed.id)
    assert row.status == "completed", row.request_payload.get("execution")
    assert len(result["sections"]) == 6 and result["bibliography"]
    assert all(
        r["verified"] and r["verification_provider"] for r in result["bibliography"]
    )
    events = [
        row_data(e)
        for e in (await db_session.execute(select(DocumentProvenance))).scalars()
    ]
    scopes = next(
        e["payload"]["nodes"] for e in events if e["event_type"] == "executor_scopes"
    )
    assert len(flatten(scopes)) == 22
    assert len(result["usage"]["calls"]) == 9
    tape = ReplayTape.from_events(events, job_id=claimed.id)
    row.status = "running"
    row.lease_owner = "replay"
    row.lease_token = "replay-token"
    row.lease_expires_at = utc_now() + timedelta(seconds=300)
    await db_session.commit()
    replay_job = ClaimedGenerationJob(
        claimed.id,
        claimed.document_id,
        claimed.user_id,
        "replay",
        "replay-token",
        1,
        1,
        claimed.request_payload,
    )

    async def denied(self, **request):
        raise AssertionError("Replay cannot contact the model")

    monkeypatch.setattr(Context, "provider", denied)
    with replay_models(tape):
        replayed = await run(replay_job)
        tape.assert_complete()
    assert replayed and artifacts[0] == artifacts[1]
    assert hashlib.sha256(artifacts[0]).hexdigest() == result["docx"]["sha256"]
    # Test output is local and cannot overwrite a product artifact or DB.
    output = tmp_path
    (output / "offline-job12-fixture.docx").write_bytes(artifacts[0])
    (output / "offline-job12-recording.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2)
    )
    (output / "offline-job12-result.json").write_text(
        json.dumps(
            {
                "mode": "offline_fixture",
                "origin": FIXTURE["origin"],
                "result": result,
                "replay_identical_bytes": True,
                "provider_calls": 9,
                "real_paid_v2_run": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
