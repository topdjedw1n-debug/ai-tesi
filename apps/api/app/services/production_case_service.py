"""Services for internal production cases and release gates."""

from datetime import datetime
from math import ceil
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.admin import AdminAuditLog
from app.models.auth import User
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentProvenance,
    DocumentSection,
    EditorTask,
    ProductionCase,
    ReleaseGateResult,
)
from app.schemas.production import (
    EditorTaskCreate,
    EditorTaskResolveRequest,
    EditorTaskUpdate,
    ManualDetectorResultRequest,
    ProductionCaseCreate,
    ProductionCaseUpdate,
)
from app.services.provenance_service import derive_quality_gate_status

DETECTOR_GATE_KEYS = {"plagiarism_proxy", "ai_detection_proxy"}

RELEASE_GATE_CONFIG: dict[str, dict[str, Any]] = {
    "citation_verification": {
        "blocking": True,
        # Override with an audited reason is the intended resolution for
        # mark_only "warning" states (not_found sources the manager has
        # reviewed); strict-policy failures kill generation before a case
        # is releasable anyway.
        "override_allowed": True,
        "source": "document_provenance",
    },
    "claim_support": {
        "blocking": True,
        "override_allowed": True,
        "source": "document_provenance",
    },
    "section_quality": {
        "blocking": True,
        "override_allowed": True,
        "source": "document_provenance",
    },
    "plagiarism_proxy": {
        "blocking": True,
        "override_allowed": False,
        "source": "phase1_run_report",
    },
    "ai_detection_proxy": {
        "blocking": True,
        "override_allowed": False,
        "source": "phase1_run_report",
    },
    "editorial_review": {
        "blocking": True,
        "override_allowed": True,
        "source": "editor_tasks",
    },
    "delivery_package": {
        "blocking": True,
        "override_allowed": False,
        "source": "document_export",
    },
}


def _document_generation_status(document: Document) -> str:
    if document.status == "generating":
        return "running"
    if document.status in {"completed", "failed", "failed_quality"}:
        return document.status
    return "not_started"


def _event_payload(event: DocumentProvenance | None) -> dict[str, Any]:
    return event.payload if event and isinstance(event.payload, dict) else {}


def _latest_event(
    events: list[DocumentProvenance], event_type: str
) -> DocumentProvenance | None:
    for event in reversed(events):
        if event.event_type == event_type:
            return event
    return None


def _serialize_document(document: Document | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return {
        "id": document.id,
        "title": document.title,
        "topic": document.topic,
        "status": document.status,
        "language": document.language,
        "target_pages": document.target_pages,
        "docx_path": document.docx_path,
        "pdf_path": document.pdf_path,
    }


class ProductionCaseService:
    """Production case orchestration."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_case(
        self, data: ProductionCaseCreate, actor_id: int
    ) -> ProductionCase:
        document = await self._get_document(data.document_id)
        existing_result = await self.db.execute(
            select(ProductionCase).where(ProductionCase.document_id == data.document_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Production case already exists for this document.",
            )

        case = ProductionCase(
            document_id=document.id,
            client_user_id=document.user_id,
            manager_id=data.manager_id or actor_id,
            editor_id=data.editor_id,
            deadline_at=data.deadline_at,
            citation_style=data.citation_style,
            requirements_text=data.requirements_text,
            generation_status=_document_generation_status(document),
            payment_status="not_required",
        )
        self.db.add(case)
        await self.db.flush()
        await self._audit(
            actor_id,
            "create_production_case",
            "production_case",
            int(case.id),
            new_value={"document_id": document.id},
        )
        await self.db.commit()
        await self.db.refresh(case)
        return case

    async def list_cases(
        self,
        *,
        page: int,
        per_page: int,
        release_status: str | None = None,
        manager_id: int | None = None,
        editor_id: int | None = None,
    ) -> dict[str, Any]:
        query = select(ProductionCase).order_by(ProductionCase.created_at.desc())
        count_query = select(func.count(ProductionCase.id))
        filters = []
        if release_status:
            filters.append(ProductionCase.release_status == release_status)
        if manager_id:
            filters.append(ProductionCase.manager_id == manager_id)
        if editor_id:
            filters.append(ProductionCase.editor_id == editor_id)
        for predicate in filters:
            query = query.where(predicate)
            count_query = count_query.where(predicate)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.offset((page - 1) * per_page).limit(per_page)
        )
        cases = list(result.scalars().all())
        return {
            "cases": [await self.serialize_case(case) for case in cases],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": ceil(total / per_page) if total else 0,
        }

    async def get_case(self, case_id: int) -> ProductionCase:
        result = await self.db.execute(
            select(ProductionCase).where(ProductionCase.id == case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Production case not found.")
        return case

    async def update_case(
        self, case_id: int, data: ProductionCaseUpdate, actor_id: int
    ) -> ProductionCase:
        case = await self.get_case(case_id)
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(case, key, value)
        await self._audit(
            actor_id,
            "update_production_case",
            "production_case",
            case_id,
            new_value=payload,
        )
        await self.db.commit()
        await self.db.refresh(case)
        return case

    async def get_release_gates(self, case_id: int) -> list[dict[str, Any]]:
        case = await self.get_case(case_id)
        persisted_result = await self.db.execute(
            select(ReleaseGateResult).where(
                ReleaseGateResult.production_case_id == case_id
            )
        )
        persisted = {gate.gate_key: gate for gate in persisted_result.scalars().all()}

        events_result = await self.db.execute(
            select(DocumentProvenance)
            .where(DocumentProvenance.document_id == case.document_id)
            .order_by(DocumentProvenance.id.asc())
        )
        events = list(events_result.scalars().all())
        document = await self._get_document(case.document_id)

        task_result = await self.db.execute(
            select(EditorTask).where(EditorTask.production_case_id == case_id)
        )
        tasks = list(task_result.scalars().all())

        gates = []
        for gate_key, config in RELEASE_GATE_CONFIG.items():
            computed = self._compute_gate(
                gate_key, config, case, document, events, tasks
            )
            stored = persisted.get(gate_key)
            if stored and gate_key in DETECTOR_GATE_KEYS:
                computed.update(
                    {
                        "id": stored.id,
                        "status": stored.status,
                        "summary": stored.summary,
                        "evidence": stored.evidence or {},
                        "last_checked_at": stored.last_checked_at,
                    }
                )
            elif stored and stored.override_reason:
                computed.update(
                    {
                        "id": stored.id,
                        "status": "overridden",
                        "override_reason": stored.override_reason,
                        "overridden_by_id": stored.overridden_by_id,
                        "overridden_at": stored.overridden_at,
                        "last_checked_at": stored.last_checked_at,
                    }
                )
            elif stored:
                computed["id"] = stored.id
            gates.append(computed)
        return gates

    async def override_gate(
        self, case_id: int, gate_key: str, reason: str, actor_id: int
    ) -> dict[str, Any]:
        if gate_key not in RELEASE_GATE_CONFIG:
            raise HTTPException(status_code=404, detail="Unknown release gate.")
        if gate_key in DETECTOR_GATE_KEYS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Detector gates require a structured detector result; "
                    "use the detector-result endpoint."
                ),
            )
        config = RELEASE_GATE_CONFIG[gate_key]
        if not config["override_allowed"]:
            raise HTTPException(
                status_code=400, detail="This release gate cannot be overridden."
            )
        await self.get_case(case_id)
        gate = await self._get_or_create_gate(case_id, gate_key, config)
        gate.status = "overridden"
        gate.override_reason = reason
        gate.overridden_by_id = actor_id
        gate.overridden_at = datetime.utcnow()
        gate.last_checked_at = datetime.utcnow()
        await self._audit(
            actor_id,
            "override_release_gate",
            "production_case",
            case_id,
            new_value={"gate_key": gate_key, "reason": reason},
        )
        await self.db.commit()
        return (await self.get_release_gates(case_id))[
            list(RELEASE_GATE_CONFIG.keys()).index(gate_key)
        ]

    async def record_detector_result(
        self,
        case_id: int,
        gate_key: str,
        data: ManualDetectorResultRequest,
        actor_id: int,
    ) -> dict[str, Any]:
        if gate_key not in DETECTOR_GATE_KEYS:
            raise HTTPException(
                status_code=400,
                detail="Manual detector results are allowed only for detector gates.",
            )

        config = RELEASE_GATE_CONFIG[gate_key]
        await self.get_case(case_id)
        gate = await self._get_or_create_gate(case_id, gate_key, config)
        passed = data.result_percent <= data.threshold_percent
        gate.status = "passed" if passed else "failed"
        gate.summary = (
            f"{data.detector_name} result {data.result_percent:.2f}% "
            f"{'<=' if passed else '>'} threshold {data.threshold_percent:.2f}%."
        )
        gate.evidence = {
            "detector_name": data.detector_name,
            "result_percent": data.result_percent,
            "threshold_percent": data.threshold_percent,
            "checked_at": data.checked_at.isoformat(),
            "report_ref": data.report_ref,
            "reason": data.reason,
            "lower_is_better": True,
        }
        gate.override_reason = None
        gate.overridden_by_id = None
        gate.overridden_at = None
        gate.last_checked_at = datetime.utcnow()
        await self._audit(
            actor_id,
            "record_detector_result",
            "production_case",
            case_id,
            new_value={
                "gate_key": gate_key,
                "status": gate.status,
                "detector_name": data.detector_name,
                "result_percent": data.result_percent,
                "threshold_percent": data.threshold_percent,
                "report_ref": data.report_ref,
            },
        )
        await self.db.commit()
        return (await self.get_release_gates(case_id))[
            list(RELEASE_GATE_CONFIG.keys()).index(gate_key)
        ]

    async def release_case(
        self, case_id: int, actor_id: int, notes: str | None = None
    ) -> ProductionCase:
        case = await self.get_case(case_id)
        gates = await self.get_release_gates(case_id)
        # "unchecked" (checks never ran) and "warning" (mark_only let
        # not_found sources through) block release the same as failures —
        # a manager must either fix the evidence or override with a reason.
        blockers = [
            gate
            for gate in gates
            if gate["blocking"]
            and gate["status"] in {"failed", "no_data", "unchecked", "warning"}
            and gate.get("override_reason") is None
        ]
        if blockers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Release blocked by unresolved gates.",
                    "blockers": [gate["gate_key"] for gate in blockers],
                },
            )

        case.release_status = "released"
        case.delivery_status = "delivered"
        case.release_notes = notes
        case.released_at = datetime.utcnow()
        await self._audit(
            actor_id,
            "release_production_case",
            "production_case",
            case_id,
            new_value={"notes": notes},
        )
        await self.db.commit()
        await self.db.refresh(case)
        return case

    async def serialize_case(self, case: ProductionCase) -> dict[str, Any]:
        document = await self._get_document(case.document_id)
        client = await self._get_user(case.client_user_id)
        manager = await self._get_user(case.manager_id) if case.manager_id else None
        editor = await self._get_user(case.editor_id) if case.editor_id else None
        usage_row = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(AIGenerationJob.total_tokens), 0),
                    func.coalesce(func.sum(AIGenerationJob.cost_cents), 0),
                ).where(AIGenerationJob.document_id == case.document_id)
            )
        ).one()
        ai_total_tokens = int(usage_row[0] or 0)
        ai_cost_usd_cents = int(usage_row[1] or 0)
        return {
            "id": case.id,
            "document_id": case.document_id,
            "client_user_id": case.client_user_id,
            "manager_id": case.manager_id,
            "editor_id": case.editor_id,
            "deadline_at": case.deadline_at,
            "citation_style": case.citation_style,
            "requirements_text": case.requirements_text,
            "intake_status": case.intake_status,
            "generation_status": case.generation_status,
            "qa_status": case.qa_status,
            "editorial_status": case.editorial_status,
            "payment_status": case.payment_status,
            "delivery_status": case.delivery_status,
            "release_status": case.release_status,
            "human_minutes_budget": case.human_minutes_budget,
            "human_minutes_used": case.human_minutes_used,
            "cost_cents": case.cost_cents,
            "ai_total_tokens": ai_total_tokens,
            "ai_cost_usd_cents": ai_cost_usd_cents,
            "ai_cost_eur_cents": round(ai_cost_usd_cents * settings.USD_TO_EUR_RATE),
            "release_notes": case.release_notes,
            "released_at": case.released_at,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
            "document": _serialize_document(document),
            "client_email": client.email if client else None,
            "manager_email": manager.email if manager else None,
            "editor_email": editor.email if editor else None,
        }

    async def _sync_case_status(self, case: ProductionCase) -> None:
        document = await self._get_document(case.document_id)
        case.generation_status = _document_generation_status(document)
        if document.status == "failed_quality":
            case.qa_status = "failed"
            case.release_status = "blocked"
        elif document.status == "completed" and case.qa_status == "no_data":
            case.qa_status = "needs_review"

        open_tasks = (
            await self.db.execute(
                select(func.count(EditorTask.id)).where(
                    EditorTask.production_case_id == case.id,
                    EditorTask.status.in_(["open", "in_progress"]),
                )
            )
        ).scalar() or 0
        if open_tasks:
            case.editorial_status = "needs_review"
        elif case.editorial_status == "needs_review":
            case.editorial_status = "completed"

    def _compute_gate(
        self,
        gate_key: str,
        config: dict[str, Any],
        case: ProductionCase,
        document: Document,
        events: list[DocumentProvenance],
        tasks: list[EditorTask],
    ) -> dict[str, Any]:
        status_value = "no_data"
        summary = "No evidence recorded yet."
        evidence: dict[str, Any] = {}

        if gate_key == "citation_verification":
            event = _latest_event(events, "citation_gate")
            payload = _event_payload(event)
            if event:
                explicit = payload.get("status")
                if explicit in {"passed", "failed", "warning"}:
                    status_value = explicit
                elif (
                    payload.get("passed") is True
                    and payload.get("policy") == "mark_only"
                    and int(payload.get("not_found_count") or 0) > 0
                ):
                    # Legacy mark_only event: pipeline continued, but
                    # not_found sources exist — never a clean pass.
                    status_value = "warning"
                else:
                    status_value = (
                        "passed" if payload.get("passed") is True else "failed"
                    )
                summary = f"Citation gate policy {payload.get('policy', 'unknown')}."
                if status_value == "warning":
                    summary += (
                        f" {int(payload.get('not_found_count') or 0)} cited "
                        f"source(s) not found in any bibliographic database."
                    )
                evidence = payload
        elif gate_key == "claim_support":
            event = _latest_event(events, "claim_check_summary")
            payload = _event_payload(event)
            counts = (
                payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
            )
            if event:
                unsupported = int(counts.get("unsupported") or 0)
                total_claims = int(payload.get("total_claims") or 0)
                if unsupported > 0:
                    status_value = "failed"
                elif total_claims == 0:
                    # Audit ran but extracted nothing — a finished thesis
                    # with zero cited claims is suspicious, not a pass.
                    status_value = "warning"
                else:
                    status_value = "passed"
                summary = f"{payload.get('checked', 0)}/{total_claims} claims checked."
                if status_value == "warning":
                    summary += (
                        " No cited claims were extracted — verify citations"
                        " manually."
                    )
                evidence = payload
        elif gate_key == "section_quality":
            quality_events = [
                event for event in events if event.event_type == "quality_gate"
            ]
            if quality_events:
                statuses = [
                    derive_quality_gate_status(_event_payload(event))
                    for event in quality_events
                ]
                failed = statuses.count("failed")
                unchecked = statuses.count("unchecked")
                if failed:
                    status_value = "failed"
                elif unchecked:
                    status_value = "unchecked"
                else:
                    status_value = "passed"
                summary = (
                    f"{len(statuses) - failed - unchecked}/{len(statuses)} "
                    f"section gates passed · {failed} failed · "
                    f"{unchecked} unchecked."
                )
                evidence = {
                    "total": len(statuses),
                    "failed": failed,
                    "unchecked": unchecked,
                }
        elif gate_key in DETECTOR_GATE_KEYS:
            status_value = "no_data"
            summary = "Record a structured external detector result before release."
        elif gate_key == "editorial_review":
            if tasks:
                open_count = sum(
                    1 for task in tasks if task.status in {"open", "in_progress"}
                )
                status_value = "failed" if open_count else "passed"
                summary = f"{open_count} open editor task(s)."
                evidence = {"total": len(tasks), "open": open_count}
        elif gate_key == "delivery_package":
            if document.docx_path or document.pdf_path:
                status_value = "passed"
                summary = "Delivery package is available."
                evidence = {
                    "docx_path": document.docx_path,
                    "pdf_path": document.pdf_path,
                }
            elif case.generation_status == "completed":
                status_value = "warning"
                summary = "Document completed but no stored delivery path is recorded."

        return {
            "id": None,
            "production_case_id": case.id,
            "gate_key": gate_key,
            "status": status_value,
            "severity": "blocking" if config["blocking"] else "advisory",
            "blocking": config["blocking"],
            "source": config["source"],
            "summary": summary,
            "evidence": evidence,
            "override_allowed": config["override_allowed"],
            "override_reason": None,
            "overridden_by_id": None,
            "overridden_at": None,
            "last_checked_at": datetime.utcnow(),
        }

    async def _get_or_create_gate(
        self, case_id: int, gate_key: str, config: dict[str, Any]
    ) -> ReleaseGateResult:
        result = await self.db.execute(
            select(ReleaseGateResult).where(
                ReleaseGateResult.production_case_id == case_id,
                ReleaseGateResult.gate_key == gate_key,
            )
        )
        gate = result.scalar_one_or_none()
        if gate:
            return gate
        gate = ReleaseGateResult(
            production_case_id=case_id,
            gate_key=gate_key,
            status="no_data",
            blocking=config["blocking"],
            severity="blocking" if config["blocking"] else "advisory",
            source=config["source"],
            override_allowed=config["override_allowed"],
        )
        self.db.add(gate)
        await self.db.flush()
        return gate

    async def _get_document(self, document_id: int) -> Document:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")
        return document

    async def _get_user(self, user_id: int | None) -> User | None:
        if user_id is None:
            return None
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _audit(
        self,
        actor_id: int,
        action: str,
        target_type: str,
        target_id: int | None,
        *,
        new_value: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AdminAuditLog(
                admin_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                new_value=new_value,
            )
        )


class EditorTaskService:
    """Editor task permissions and transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(self, data: EditorTaskCreate, actor_id: int) -> EditorTask:
        case = await ProductionCaseService(self.db).get_case(data.production_case_id)
        task = EditorTask(
            production_case_id=case.id,
            document_id=case.document_id,
            section_id=data.section_id,
            assigned_editor_id=data.assigned_editor_id,
            created_by_id=actor_id,
            source_gate=data.source_gate,
            finding_key=data.finding_key,
            title=data.title,
            description=data.description,
            status="open",
        )
        self.db.add(task)
        case.editor_id = data.assigned_editor_id
        case.editorial_status = "needs_review"
        await ProductionCaseService(self.db)._audit(
            actor_id,
            "create_editor_task",
            "production_case",
            int(case.id),
            new_value={"title": data.title, "editor_id": data.assigned_editor_id},
        )
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def list_tasks(
        self,
        *,
        user: User,
        page: int,
        per_page: int,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        query = select(EditorTask).order_by(EditorTask.created_at.desc())
        count_query = select(func.count(EditorTask.id))
        if not user.is_admin:
            query = query.where(EditorTask.assigned_editor_id == user.id)
            count_query = count_query.where(EditorTask.assigned_editor_id == user.id)
        if status_filter:
            query = query.where(EditorTask.status == status_filter)
            count_query = count_query.where(EditorTask.status == status_filter)
        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.offset((page - 1) * per_page).limit(per_page)
        )
        tasks = list(result.scalars().all())
        return {
            "tasks": [await self.serialize_task(task) for task in tasks],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": ceil(total / per_page) if total else 0,
        }

    async def get_task(self, task_id: int, user: User) -> EditorTask:
        result = await self.db.execute(
            select(EditorTask).where(EditorTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Editor task not found.")
        if not user.is_admin and task.assigned_editor_id != user.id:
            raise HTTPException(
                status_code=403, detail="Editor task is not assigned to you."
            )
        return task

    async def update_task(
        self, task_id: int, data: EditorTaskUpdate, user: User
    ) -> EditorTask:
        task = await self.get_task(task_id, user)
        payload = data.model_dump(exclude_unset=True)
        if not user.is_admin:
            payload.pop("assigned_editor_id", None)
        for key, value in payload.items():
            setattr(task, key, value)
        if task.status in {"resolved", "rejected"} and task.resolved_at is None:
            task.resolved_at = datetime.utcnow()
        await self.db.flush()
        await self._sync_case_minutes(task.production_case_id)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def resolve_task(
        self, task_id: int, data: EditorTaskResolveRequest, user: User
    ) -> EditorTask:
        return await self.update_task(
            task_id,
            EditorTaskUpdate(
                status=data.status,
                resolution_notes=data.resolution_notes,
                minutes_spent=data.minutes_spent,
            ),
            user,
        )

    async def serialize_task(self, task: EditorTask) -> dict[str, Any]:
        document = (
            await self.db.execute(
                select(Document).where(Document.id == task.document_id)
            )
        ).scalar_one_or_none()
        section = None
        if task.section_id:
            section = (
                await self.db.execute(
                    select(DocumentSection).where(DocumentSection.id == task.section_id)
                )
            ).scalar_one_or_none()
        return {
            "id": task.id,
            "production_case_id": task.production_case_id,
            "document_id": task.document_id,
            "section_id": task.section_id,
            "assigned_editor_id": task.assigned_editor_id,
            "created_by_id": task.created_by_id,
            "source_gate": task.source_gate,
            "finding_key": task.finding_key,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "resolution_notes": task.resolution_notes,
            "minutes_spent": task.minutes_spent,
            "resolved_at": task.resolved_at,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "document_title": document.title if document else None,
            "section_title": section.title if section else None,
        }

    async def _sync_case_minutes(self, production_case_id: int) -> None:
        total = (
            await self.db.execute(
                select(func.coalesce(func.sum(EditorTask.minutes_spent), 0)).where(
                    EditorTask.production_case_id == production_case_id
                )
            )
        ).scalar() or 0
        case = (
            await self.db.execute(
                select(ProductionCase).where(ProductionCase.id == production_case_id)
            )
        ).scalar_one_or_none()
        if case:
            case.human_minutes_used = int(total)
            open_tasks = (
                await self.db.execute(
                    select(func.count(EditorTask.id)).where(
                        EditorTask.production_case_id == production_case_id,
                        EditorTask.status.in_(["open", "in_progress"]),
                    )
                )
            ).scalar() or 0
            if open_tasks == 0:
                case.editorial_status = "completed"
