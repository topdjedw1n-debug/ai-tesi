"""Fenced orchestration. External calls never hold a database transaction open."""

import asyncio
import copy
import logging
from dataclasses import asdict

from anthropic import AsyncAnthropic

from app.core import database
from app.core.config import settings
from app.models.admin import SystemSetting
from app.models.document import AIGenerationJob, Document
from app.services.academic_context import digest
from app.services.cost_estimator import PRICING_INPUT, PRICING_OUTPUT, UsageTracker
from app.services.generation_operations import _append, journal_usage
from app.services.generation_policy import RecordingPersistenceError
from app.services.generation_worker import (
    GenerationLeaseLostError,
    complete_generation_job,
    fail_executor_job,
    persist_generation_section,
    persist_generation_source_pack,
    renew_generation_lease,
    update_executor_state,
    update_generation_document,
)
from app.services.model_recording import ReplayIncomplete, active_replay
from app.services.replay_dependencies import recording_context
from app.services.replay_snapshot import snapshot_inputs
from app.services.task_contract import contract_confirmation_error
from app.services.uploaded_sources import load_document_passages

from .budgets import POLICY
from .warnings import ExecutionStop, unusable, warning


class Context:
    def __init__(self, job):
        self.job = job
        self.lease = {
            "job_id": job.id,
            "worker_id": job.lease_owner,
            "lease_token": job.lease_token,
        }
        self.fence = {"document_id": job.document_id, **self.lease}
        self.recording = {
            "document_id": job.document_id,
            "job_id": job.id,
            "worker_attempt": job.attempt_count,
        }
        self.usage = UsageTracker()
        self.usage.generation_context = self.recording
        self.stage = "sources"
        self.section_index = None
        self.warnings = []
        self.calls = 0
        self.model = POLICY["model"]
        self.state = {"sections_done": 0, "sections_total": 0, "warnings_count": 0}

    async def provider(self, **request):
        async with AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            max_retries=0,
            timeout=POLICY["provider_timeout_seconds"],
        ) as client:
            return await client.messages.create(**request)

    async def emit(self, event_type, payload):
        await _append(
            self.recording, {"stage": self.stage, **payload}, event_type=event_type
        )

    async def progress(self, signal, **fields):
        fields["progress"] = max(
            self.state.get("progress", 0), fields.get("progress", 0)
        )
        self.state.update(
            stage=self.stage,
            last_signal=signal[:120],
            warnings_count=len(self.warnings),
            **fields,
        )
        async with database.AsyncSessionLocal() as db:
            await update_executor_state(db, **self.fence, state=self.state)

    async def warn(self, code, section_index=None, detail=""):
        item = warning(code, self.stage, section_index=section_index, detail=detail)
        await self.emit("generation_warning", item)
        self.warnings.append(item)
        await self.progress(item["message_uk"])

    async def initialize(self):
        tape = active_replay.get()
        if tape is not None:
            self.inputs = tape.dependency(
                "executor_inputs", digest({"document_id": self.job.document_id})
            )["response"]
            async with database.AsyncSessionLocal() as db:
                row = await db.get(AIGenerationJob, self.job.id)
                self.model = row.ai_model
            return
        async with database.AsyncSessionLocal() as db:
            document = await db.get(Document, self.job.document_id)
            row = await db.get(AIGenerationJob, self.job.id)
            self.model = row.ai_model
            if not self.model:
                raise RuntimeError("Writer model is missing from job")
            snapshot = await snapshot_inputs(
                db, document, row, worker_attempt=self.job.attempt_count
            )
            passages = await load_document_passages(db, document.id)
            library = await db.get(SystemSetting, "generation.standard_library")
            library_rows = copy.deepcopy(library.value if library else [])
            if not isinstance(library_rows, list):
                raise RecordingPersistenceError("Standard library must contain a list")
            uploaded = []
            for item in snapshot["tables"]["document_source_files"]:
                uploaded.append(
                    {
                        "key": item["citation_key"],
                        "origin": "pdf",
                        "mandatory": item["mandatory"],
                        "verification_provider": "PDF",
                        "verification_status": (
                            "verified"
                            if not item["metadata_incomplete"]
                            and item["status"] == "parsed"
                            else "unverified"
                        ),
                        "source": {
                            "title": item["title"] or item["filename"],
                            "authors": [
                                s.strip()
                                for s in (item["authors"] or "").split(";")
                                if s.strip()
                            ],
                            "year": item["year"],
                            "provider": "uploaded",
                            "paper_id": f'uploaded:{item["id"]}',
                            "abstract": None,
                        },
                    }
                )
            brief = {
                k: getattr(document, k)
                for k in (
                    "title topic work_type language target_pages citation_style "
                    "additional_requirements contract_confirmed_sha256 requirements_file_processed"
                ).split()
                if hasattr(document, k)
            }
            brief["target_words"] = (
                int(document.target_pages) * POLICY["words_per_page"]
            )
            requirements = "\n".join(
                filter(
                    None,
                    [
                        document.additional_requirements,
                        self.job.additional_requirements,
                    ],
                )
            )
            self.inputs = {
                "exported_at": snapshot["job"]["started_at"],
                "brief": brief,
                "requirements": requirements,
                "passages": [asdict(p) for p in passages],
                "uploaded_sources": uploaded,
                "library": library_rows,
            }
            defect = contract_confirmation_error(document)
            await db.rollback()
        await self.emit(
            "generation_replay_inputs", {**snapshot, "executor_inputs": self.inputs}
        )
        await self.emit(
            "generation_dependency",
            {
                "kind": "executor_inputs",
                "input_fingerprint": digest({"document_id": self.job.document_id}),
                "response": self.inputs,
                "outcome": "received",
            },
        )
        if defect:
            await self.emit("executor_launch_defect", {"message": defect})

    async def check_budget(self, output_tokens, prompt):
        ceiling = (
            POLICY["calls_per_section"] * max(1, self.state["sections_total"])
            + POLICY["extra_calls"]
        )
        if self.calls >= ceiling:
            raise unusable(
                "Досягнуто межі кількості звернень до моделі.",
                budget=True,
            )
        estimated = (
            len(prompt)
            / POLICY["chars_per_token"]
            * PRICING_INPUT["anthropic"][self.model]
            + output_tokens * PRICING_OUTPUT["anthropic"][self.model]
        ) / 10000
        if self.usage.cost_usd_cents() + estimated > POLICY["cost_ceiling_cents"]:
            raise unusable(
                "Наступне звернення перевищить бюджет цієї роботи.",
                budget=True,
            )
        self.calls += 1

    async def account(self):
        async with database.AsyncSessionLocal() as db:
            totals, unknown = await journal_usage(db, self.job.document_id, self.job.id)
        self.usage._by_model = totals._by_model
        self.state.update(
            tokens_so_far=totals.total_tokens, cost_cents_so_far=totals.cost_usd_cents()
        )
        await self.progress("Відповідь моделі записано.")
        if totals.cost_usd_cents() > POLICY["cost_ceiling_cents"]:
            raise unusable(
                "Досягнуто бюджету цієї роботи.",
                budget=True,
            )

    async def save_pack(self, pack):
        async with database.AsyncSessionLocal() as db:
            await persist_generation_source_pack(db, **self.fence, pack=pack)

    async def save_outline(self, sections):
        self.state["sections_total"] = len(sections)
        async with database.AsyncSessionLocal() as db:
            await update_generation_document(
                db, **self.fence, values={"outline": {"sections": sections}}
            )
        await self.progress("План роботи збережено.")

    async def save_section(self, section):
        async with database.AsyncSessionLocal() as db:
            await persist_generation_section(
                db,
                **self.fence,
                section_index=section["section_index"],
                values={
                    **section,
                    "status": "completed",
                    "tokens_used": section.get("tokens_used", 0),
                },
            )
        await self.progress(
            "Розділ збережено.",
            sections_done=section["section_index"],
            progress=35
            + round(50 * section["section_index"] / self.state["sections_total"]),
        )

    async def step(self, name, stage, call, *args):
        self.stage = stage
        from .warnings import STAGE_LABELS

        await self.progress(
            STAGE_LABELS[stage], progress=POLICY["stage_progress"][stage]
        )
        await self.emit("executor_step_started", {"step": name})
        result = await call(self, *args)
        await self.emit("executor_step_completed", {"step": name})
        return result


async def prepare(ctx):
    from .outline import build_outline
    from .scopes import build_scopes
    from .sources import build_sources

    await ctx.initialize()
    scopes = await ctx.step("S1", "sources", build_scopes)
    pack = await ctx.step("S2", "sources", build_sources, scopes)
    outline = await ctx.step("S3", "outline", build_outline, scopes, pack)
    return pack, outline


async def execute(ctx):
    from .assemble import assemble
    from .references import resolve_references
    from .sections import write_sections

    pack, outline = await prepare(ctx)
    sections = await ctx.step("S4", "writing", write_sections, outline, pack)
    bibliography = await ctx.step(
        "S5", "references", resolve_references, sections, pack
    )
    result = await ctx.step("S6", "assembling", assemble, sections, bibliography, pack)
    await ctx.progress("DOCX збережено. Написання завершено.", result=result)
    async with database.AsyncSessionLocal() as db:
        completed = await complete_generation_job(db, **ctx.lease)
    if not completed:
        raise GenerationLeaseLostError("Lease lost before completion")
    return result


async def heartbeat(ctx):
    while True:
        async with database.AsyncSessionLocal() as db:
            owned = await renew_generation_lease(db, **ctx.lease)
        if not owned:
            raise GenerationLeaseLostError("Generation was cancelled or lease expired")
        await asyncio.sleep(POLICY["heartbeat_seconds"])


async def run(job):
    ctx = Context(job)
    token = recording_context.set(ctx.recording)
    worker = pulse = None
    try:
        worker = asyncio.create_task(execute(ctx))
        pulse = asyncio.create_task(heartbeat(ctx))
        done, _ = await asyncio.wait(
            [worker, pulse], return_when=asyncio.FIRST_COMPLETED
        )
        return await (pulse if pulse in done else worker)
    except GenerationLeaseLostError:
        return None
    except (asyncio.CancelledError, ReplayIncomplete):
        raise
    except (Exception, RecordingPersistenceError) as error:
        logging.getLogger(__name__).exception(
            "Executor v2 job %s stopped at %s", job.id, ctx.stage
        )
        # Stop orchestration before waiting for DB recovery. An already sent
        # provider call may finish its receipt, but cannot advance the pipeline.
        if worker is not None and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        if isinstance(error, ExecutionStop):
            stop = error.stop
        elif isinstance(error, OSError | RecordingPersistenceError) or type(
            error
        ).__module__.startswith(("sqlalchemy", "botocore")):
            stop = ExecutionStop(
                "storage_or_db",
                "Не вдалося прочитати вхід або зберегти запис чи файл роботи.",
            ).stop
        else:
            stop = ExecutionStop(
                "internal_error",
                "Внутрішня помилка виконавця. Власнику потрібно перевірити запуск.",
            ).stop
        stop.update(stage=ctx.stage, section_index=ctx.section_index)
        # No external calls while persistence is unavailable. Persist the terminal
        # state after recovery; never turn an unknown DB outcome into completion.
        while True:
            try:
                async with database.AsyncSessionLocal() as db:
                    await fail_executor_job(db, **ctx.fence, stop=stop)
                break
            except (Exception, RecordingPersistenceError):
                await asyncio.sleep(POLICY["retry_seconds"][0])
        return None
    finally:
        for task in (worker, pulse):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(t for t in (worker, pulse) if t is not None), return_exceptions=True
        )
        recording_context.reset(token)
