"""Services for internal production cases and release gates."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from math import ceil
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
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
from app.services.generation_contract import (
    generation_contract_error,
    generation_contract_sha256,
)
from app.services.provenance_service import derive_quality_gate_status
from app.services.storage_service import StorageService

DETECTOR_GATE_KEYS = {"plagiarism_proxy", "ai_detection_proxy"}
DETECTOR_ARTIFACT_FORMATS = ("docx", "pdf")


def _timestamp_token(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _artifact_binding(
    document: Document, artifact_format: str
) -> dict[str, str | None] | None:
    """Derive a stable identifier for the exact current generated artifact.

    The caller chooses only which available format was checked. The server owns
    the fingerprint, so a release decision cannot be attached to an arbitrary
    client-supplied version identifier. A new generation or content change
    changes at least one signed input and invalidates prior evidence.
    """
    if artifact_format not in DETECTOR_ARTIFACT_FORMATS:
        return None
    if document.status != "completed":
        return None

    artifact_path = (
        document.docx_path if artifact_format == "docx" else document.pdf_path
    )
    if not artifact_path:
        return None

    artifact_sha256 = (
        document.docx_sha256 if artifact_format == "docx" else document.pdf_sha256
    )
    artifact_sha256 = str(artifact_sha256 or "").lower()
    if len(artifact_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in artifact_sha256
    ):
        return None
    document_completed_at = _timestamp_token(document.completed_at)
    fingerprint_input: dict[str, Any] = {
        "document_id": int(document.id),
        "artifact_format": artifact_format,
        "artifact_path": str(artifact_path),
        "document_completed_at": document_completed_at,
        "artifact_sha256": artifact_sha256,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_input,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "format": artifact_format,
        "identifier": f"document-{document.id}-{artifact_format}-{fingerprint[:16]}",
        "fingerprint_sha256": fingerprint,
        "artifact_sha256": artifact_sha256,
        "document_completed_at": document_completed_at,
    }


def _artifact_bindings(document: Document) -> dict[str, dict[str, str | None]]:
    return {
        artifact_format: binding
        for artifact_format in DETECTOR_ARTIFACT_FORMATS
        if (binding := _artifact_binding(document, artifact_format)) is not None
    }


def _detector_binding_is_current(
    document: Document, evidence: dict[str, Any]
) -> tuple[bool, dict[str, str | None] | None]:
    artifact_format = str(evidence.get("artifact_format") or "").lower()
    current = _artifact_binding(document, artifact_format)
    recorded_fingerprint = str(evidence.get("artifact_fingerprint_sha256") or "")
    if current is None or not recorded_fingerprint:
        return False, current
    return (
        hmac.compare_digest(recorded_fingerprint, str(current["fingerprint_sha256"])),
        current,
    )


def revoke_release(case: ProductionCase) -> None:
    """Invalidate a prior release whenever its artifact or evidence changes."""
    if case.release_status == "released":
        case.release_status = "blocked"
    case.delivery_status = "not_ready"
    case.released_at = None
    case.released_docx_path = None
    case.released_pdf_path = None
    case.released_docx_sha256 = None
    case.released_pdf_sha256 = None


RELEASE_GATE_CONFIG: dict[str, dict[str, Any]] = {
    "generation_contract": {
        "blocking": True,
        "override_allowed": False,
        "source": "generation_job",
    },
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
    # Honest source-base gate (doc-8 fix): an empty pack means generation ran
    # closed-book; an underfilled pack means the topic-relevance threshold was
    # silently relaxed — both must face the manager, not hide in a log.
    # NOTE: appended LAST — override endpoints index gates by key order.
    "source_availability": {
        "blocking": True,
        "override_allowed": True,
        "source": "document_provenance",
    },
}


def _document_generation_status(document: Document) -> str:
    if document.status == "generating":
        return "running"
    if document.status in {"completed", "failed", "failed_quality"}:
        return document.status
    return "not_started"


def _same_instant(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False

    def _utc_naive(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    return abs((_utc_naive(left) - _utc_naive(right)).total_seconds()) < 0.001


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
        "artifact_bindings": _artifact_bindings(document),
    }


class ProductionCaseService:
    """Production case orchestration."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_case(
        self, data: ProductionCaseCreate, actor_id: int
    ) -> ProductionCase:
        # The document row is the stable mutex shared with generation. It must
        # be locked before checking the optional case row: locking a SELECT
        # that returns no case cannot prevent a concurrent insert.
        document = await self.get_document_for_update(data.document_id)
        existing_result = await self.db.execute(
            select(ProductionCase)
            .where(ProductionCase.document_id == data.document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Production case already exists for this document.",
            )

        active_job_result = await self.db.execute(
            select(AIGenerationJob.id).where(
                AIGenerationJob.document_id == data.document_id,
                AIGenerationJob.status.in_(["queued", "running"]),
            )
        )
        if document.status == "generating" or active_job_result.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Production case cannot be created while generation is active; "
                    "otherwise its requirements would not be included in the run."
                ),
            )
        if document.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A production case cannot be attached after generation. "
                    "Create the case first, then regenerate so its requirements "
                    "are bound to the artifact."
                ),
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

    async def get_case_for_update(self, case_id: int) -> ProductionCase:
        result = await self.db.execute(
            select(ProductionCase)
            .where(ProductionCase.id == case_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Production case not found.")
        return case

    async def get_document_for_update(self, document_id: int) -> Document:
        result = await self.db.execute(
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")
        return document

    async def get_case_and_document_for_update(
        self, case_id: int
    ) -> tuple[ProductionCase, Document]:
        """Lock a case and its document in the global document -> case order."""
        case_document_result = await self.db.execute(
            select(ProductionCase.document_id).where(ProductionCase.id == case_id)
        )
        document_id = case_document_result.scalar_one_or_none()
        if document_id is None:
            raise HTTPException(status_code=404, detail="Production case not found.")

        document = await self.get_document_for_update(int(document_id))
        case = await self.get_case_for_update(case_id)
        return case, document

    async def update_case(
        self, case_id: int, data: ProductionCaseUpdate, actor_id: int
    ) -> ProductionCase:
        payload = data.model_dump(exclude_unset=True)
        requirements_changed = bool(
            {"requirements_text", "citation_style"} & payload.keys()
        )
        document: Document | None = None
        if requirements_changed:
            case, document = await self.get_case_and_document_for_update(case_id)
            active_job_result = await self.db.execute(
                select(AIGenerationJob.id).where(
                    AIGenerationJob.document_id == document.id,
                    AIGenerationJob.status.in_(["queued", "running"]),
                )
            )
            if document.status == "generating" or active_job_result.first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Production requirements cannot change while generation is active.",
                )
        else:
            case = await self.get_case_for_update(case_id)

        if payload:
            revoke_release(case)
        if requirements_changed and document is not None:
            document.status = "draft"
            document.completed_at = None
            case.generation_status = "not_started"
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
        case = await self.get_case_for_update(case_id)
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
        latest_run_start = max(
            (
                index
                for index, event in enumerate(events)
                if event.event_type == "generation_run_started"
            ),
            default=-1,
        )
        current_run_started_at = None
        if latest_run_start >= 0:
            current_run_started_at = events[latest_run_start].created_at
            events = events[latest_run_start + 1 :]
        document = await self._get_document(case.document_id)

        sections_result = await self.db.execute(
            select(DocumentSection).where(
                DocumentSection.document_id == case.document_id,
                DocumentSection.status == "completed",
            )
        )
        sections = list(sections_result.scalars().all())

        task_query = select(EditorTask).where(EditorTask.production_case_id == case_id)
        if current_run_started_at is not None:
            task_query = task_query.where(
                EditorTask.created_at >= current_run_started_at
            )
        task_result = await self.db.execute(task_query)
        tasks = list(task_result.scalars().all())

        latest_job = (
            await self.db.execute(
                select(AIGenerationJob)
                .where(
                    AIGenerationJob.document_id == case.document_id,
                    AIGenerationJob.job_type == "full_document",
                    AIGenerationJob.status == "completed",
                )
                .order_by(AIGenerationJob.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        gates = []
        for gate_key, config in RELEASE_GATE_CONFIG.items():
            computed = self._compute_gate(
                gate_key,
                config,
                case,
                document,
                events,
                tasks,
                sections,
                latest_job,
            )
            stored = persisted.get(gate_key)
            if stored and gate_key in DETECTOR_GATE_KEYS:
                stored_evidence = dict(stored.evidence or {})
                binding_current, current_binding = _detector_binding_is_current(
                    document, stored_evidence
                )
                stored_evidence["binding_status"] = (
                    "current" if binding_current else "stale"
                )
                if current_binding is not None:
                    stored_evidence["current_artifact_identifier"] = current_binding[
                        "identifier"
                    ]
                computed.update(
                    {
                        "id": stored.id,
                        "status": stored.status,
                        "summary": stored.summary,
                        "evidence": stored_evidence,
                        "last_checked_at": stored.last_checked_at,
                    }
                )
                if not binding_current:
                    computed["status"] = "no_data"
                    computed["summary"] = (
                        "Recorded detector decision is not bound to the current "
                        "generated artifact. Re-run the detector and record a new "
                        "release-manager decision."
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
                    "Detector gates require an artifact-bound release-manager decision; "
                    "use the detector-result endpoint."
                ),
            )
        config = RELEASE_GATE_CONFIG[gate_key]
        if not config["override_allowed"]:
            raise HTTPException(
                status_code=400, detail="This release gate cannot be overridden."
            )
        case = await self.get_case_for_update(case_id)
        revoke_release(case)
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
                detail="Manual detector decisions are allowed only for detector gates.",
            )

        expected_detector = settings.RELEASE_PRIMARY_DETECTOR_NAME.strip()
        if data.detector_name.strip().casefold() != expected_detector.casefold():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Release evidence for this production contour must come "
                    f"from {expected_detector}. Other detector results are "
                    "diagnostic only."
                ),
            )

        config = RELEASE_GATE_CONFIG[gate_key]
        case, document = await self.get_case_and_document_for_update(case_id)
        artifact_binding = _artifact_binding(document, data.artifact_format)
        if artifact_binding is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Detector evidence cannot be recorded: the current "
                    f"{data.artifact_format.upper()} artifact is unavailable or "
                    "generation is not completed."
                ),
            )
        artifact_path = (
            document.docx_path if data.artifact_format == "docx" else document.pdf_path
        )
        storage = StorageService()
        try:
            stored_sha256 = await storage.get_file_sha256(str(artifact_path))
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Detector evidence cannot be recorded: stored artifact is unavailable.",
            ) from error
        if not hmac.compare_digest(
            stored_sha256, str(artifact_binding["artifact_sha256"])
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Detector evidence cannot be recorded: stored artifact bytes "
                    "do not match the generated artifact fingerprint."
                ),
            )
        revoke_release(case)
        gate = await self._get_or_create_gate(case_id, gate_key, config)
        gate.status = data.decision
        gate.summary = (
            f"{data.detector_name} reported {data.result_percent:.2f}%. "
            f"Release manager decision: {data.decision}."
        )
        gate.evidence = {
            "detector_name": data.detector_name,
            "result_percent": data.result_percent,
            "decision": data.decision,
            "checked_at": data.checked_at.isoformat(),
            "report_ref": data.report_ref,
            "reason": data.reason,
            "decision_by_id": actor_id,
            "artifact_format": data.artifact_format,
            "artifact_identifier": artifact_binding["identifier"],
            "artifact_fingerprint_sha256": artifact_binding["fingerprint_sha256"],
            "artifact_sha256": artifact_binding["artifact_sha256"],
            "artifact_completed_at": artifact_binding["document_completed_at"],
            "binding_status": "current",
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
                "decision": data.decision,
                "report_ref": data.report_ref,
                "artifact_format": data.artifact_format,
                "artifact_identifier": artifact_binding["identifier"],
                "artifact_fingerprint_sha256": artifact_binding["fingerprint_sha256"],
                "artifact_sha256": artifact_binding["artifact_sha256"],
            },
        )
        await self.db.commit()
        return (await self.get_release_gates(case_id))[
            list(RELEASE_GATE_CONFIG.keys()).index(gate_key)
        ]

    async def release_case(
        self, case_id: int, actor_id: int, notes: str | None = None
    ) -> ProductionCase:
        case, document = await self.get_case_and_document_for_update(case_id)
        if document.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Release blocked: document generation is not completed.",
            )
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

        # Both external decisions must describe the exact same binary that we
        # make available to the client. Passing plagiarism on DOCX and AI risk
        # on PDF must not accidentally authorize both files.
        detector_formats = {
            str(gate["gate_key"]): str(
                (gate.get("evidence") or {}).get("artifact_format") or ""
            )
            for gate in gates
            if gate["gate_key"] in DETECTOR_GATE_KEYS and gate["status"] == "passed"
        }
        approved_formats = set(detector_formats.values()) - {""}
        if set(detector_formats) != DETECTOR_GATE_KEYS or len(approved_formats) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Release blocked: plagiarism and AI detector decisions must "
                    "both be bound to the same delivery artifact."
                ),
            )
        approved_format = approved_formats.pop()

        storage = StorageService()
        released_docx_path = None
        released_pdf_path = None
        released_docx_sha256 = None
        released_pdf_sha256 = None
        if approved_format == "docx" and document.docx_path and document.docx_sha256:
            try:
                actual_docx_sha256 = await storage.get_file_sha256(
                    str(document.docx_path)
                )
            except Exception:
                actual_docx_sha256 = None
            if actual_docx_sha256 and hmac.compare_digest(
                actual_docx_sha256, str(document.docx_sha256)
            ):
                released_docx_path = str(document.docx_path)
                released_docx_sha256 = actual_docx_sha256
        if approved_format == "pdf" and document.pdf_path and document.pdf_sha256:
            try:
                actual_pdf_sha256 = await storage.get_file_sha256(
                    str(document.pdf_path)
                )
            except Exception:
                actual_pdf_sha256 = None
            if actual_pdf_sha256 and hmac.compare_digest(
                actual_pdf_sha256, str(document.pdf_sha256)
            ):
                released_pdf_path = str(document.pdf_path)
                released_pdf_sha256 = actual_pdf_sha256
        if not released_docx_path and not released_pdf_path:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Release blocked: the delivery file is missing from storage.",
            )

        case.release_status = "released"
        case.delivery_status = "delivered"
        case.release_notes = notes
        case.released_docx_path = released_docx_path
        case.released_pdf_path = released_pdf_path
        case.released_docx_sha256 = released_docx_sha256
        case.released_pdf_sha256 = released_pdf_sha256
        case.release_version = int(case.release_version or 0) + 1
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
        # Case status is a projection of the live document and editor-task
        # state. Refresh it before every manager response so a completed or
        # failed generation cannot remain displayed as "not started" merely
        # because no separate synchronization endpoint was called.
        await self._sync_case_status(case)
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
            "released_docx_path": case.released_docx_path,
            "released_pdf_path": case.released_pdf_path,
            "released_docx_sha256": case.released_docx_sha256,
            "released_pdf_sha256": case.released_pdf_sha256,
            "release_version": case.release_version,
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
            revoke_release(case)
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
        sections: list[DocumentSection],
        latest_job: AIGenerationJob | None,
    ) -> dict[str, Any]:
        status_value = "no_data"
        summary = "No evidence recorded yet."
        evidence: dict[str, Any] = {}

        if gate_key == "generation_contract":
            contract_error = generation_contract_error(document)
            if contract_error is not None:
                status_value = "failed"
                summary = f"Generation contract is incomplete: {contract_error}."
            elif latest_job is None:
                status_value = "no_data"
                summary = "No completed durable generation job is bound to this file."
            else:
                job_payload = (
                    latest_job.request_payload
                    if isinstance(latest_job.request_payload, dict)
                    else {}
                )
                recorded_hash = str(job_payload.get("generation_contract_sha256") or "")
                expected_hash = generation_contract_sha256(
                    document,
                    case,
                    job_payload.get("additional_requirements"),
                )
                completion_matches = _same_instant(
                    latest_job.completed_at,
                    document.completed_at,
                )
                if not recorded_hash:
                    status_value = "no_data"
                    summary = "The completed job has no requirements fingerprint."
                elif not hmac.compare_digest(recorded_hash, expected_hash):
                    status_value = "failed"
                    summary = (
                        "Current methodology or production requirements differ "
                        "from those used for generation."
                    )
                elif not completion_matches:
                    status_value = "failed"
                    summary = "The current artifact is not bound to the completed job."
                else:
                    status_value = "passed"
                    summary = "Methodology, APA, case requirements, and run are bound."
                evidence = {
                    "job_id": int(latest_job.id),
                    "recorded_contract_sha256": recorded_hash or None,
                    "current_contract_sha256": expected_hash,
                    "completion_matches": completion_matches,
                }
        elif gate_key == "citation_verification":
            event = _latest_event(events, "citation_gate")
            payload = _event_payload(event)
            if event:
                explicit = payload.get("status")
                if explicit in {"passed", "failed", "warning", "unchecked"}:
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
                uncertain = int(counts.get("uncertain") or 0)
                total_claims = int(payload.get("total_claims") or 0)
                checked_claims = int(payload.get("checked") or 0)
                if unsupported > 0:
                    status_value = "failed"
                elif total_claims == 0:
                    # Audit ran but extracted nothing — a finished thesis
                    # with zero cited claims is suspicious, not a pass.
                    status_value = "warning"
                elif checked_claims < total_claims or uncertain > 0:
                    # Missing abstracts, exhausted budget, or a failed judge
                    # are not evidence of support.
                    status_value = "unchecked"
                else:
                    status_value = "passed"
                summary = f"{checked_claims}/{total_claims} claims checked."
                if status_value == "warning":
                    summary += (
                        " No cited claims were extracted — verify citations manually."
                    )
                evidence = payload
        elif gate_key == "section_quality":
            quality_events = [
                event for event in events if event.event_type == "quality_gate"
            ]
            expected_sections = {section.section_index for section in sections}
            if quality_events or expected_sections:
                # The ledger is append-only and admin retry regenerates the
                # same document — judge each section by its LATEST event,
                # or stale unchecked/failed events block release forever.
                latest_by_section: dict[Any, DocumentProvenance] = {}
                for event in quality_events:  # events are ordered by id
                    payload = _event_payload(event)
                    section_key = payload.get("section_index")
                    latest_by_section[section_key] = event
                section_keys = expected_sections or set(latest_by_section)
                statuses = dict.fromkeys(section_keys, "unchecked")
                for section_key, event in latest_by_section.items():
                    if section_key in statuses:
                        statuses[section_key] = derive_quality_gate_status(
                            _event_payload(event)
                        )
                if settings.QUALITY_PANEL_ENABLED:
                    latest_panel_by_section: dict[Any, DocumentProvenance] = {}
                    for event in events:
                        if event.event_type != "panel_review":
                            continue
                        panel_payload = _event_payload(event)
                        latest_panel_by_section[
                            panel_payload.get("section_index")
                        ] = event
                    for section_key in statuses:
                        panel_event = latest_panel_by_section.get(section_key)
                        panel_status = (
                            _event_payload(panel_event).get("status")
                            if panel_event is not None
                            else "unchecked"
                        )
                        if panel_status == "failed":
                            statuses[section_key] = "failed"
                        elif (
                            panel_status != "passed"
                            and statuses[section_key] != "failed"
                        ):
                            statuses[section_key] = "unchecked"
                status_values = list(statuses.values())
                failed = status_values.count("failed")
                unchecked = status_values.count("unchecked")
                if failed:
                    status_value = "failed"
                elif unchecked:
                    status_value = "unchecked"
                else:
                    status_value = "passed"
                summary = (
                    f"{len(status_values) - failed - unchecked}/{len(status_values)} "
                    f"section gates passed · {failed} failed · "
                    f"{unchecked} unchecked."
                )
                evidence = {
                    "total": len(status_values),
                    "failed": failed,
                    "unchecked": unchecked,
                }
        elif gate_key in DETECTOR_GATE_KEYS:
            status_value = "no_data"
            summary = (
                "Record an artifact-bound external detector result and explicit "
                "release-manager decision before release."
            )
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
        elif gate_key == "source_availability":
            # The rebuilt pack (post-outline) is what sections actually cite;
            # fall back to the initial build for runs that never rebuilt.
            # No event -> default no_data (blocks until an audited override),
            # consistent with the other gates; gates are only computed at
            # release time, so old cases are not retroactively touched.
            event = _latest_event(events, "source_pack_rebuilt") or _latest_event(
                events, "source_pack_built"
            )
            if event:
                payload = _event_payload(event)
                pack_size = int(payload.get("pack_size") or 0)
                if pack_size == 0:
                    status_value = "failed"
                    summary = "Source pack is empty — generation ran closed-book."
                elif payload.get("underfilled") is True:
                    status_value = "warning"
                    summary = (
                        "Source base is thin; the topic-relevance threshold "
                        f"was relaxed to fill the pack ({pack_size} sources) — "
                        "review the sources before release."
                    )
                else:
                    status_value = "passed"
                    summary = f"{pack_size} on-topic sources in the pack."
                evidence = payload

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

    async def _clear_task_related_overrides(
        self, case_id: int, source_gate: str | None
    ) -> None:
        gate_keys = {"editorial_review"}
        if source_gate in RELEASE_GATE_CONFIG:
            gate_keys.add(str(source_gate))
        await self.db.execute(
            update(ReleaseGateResult)
            .where(
                ReleaseGateResult.production_case_id == case_id,
                ReleaseGateResult.gate_key.in_(gate_keys),
            )
            .values(
                status="no_data",
                override_reason=None,
                overridden_by_id=None,
                overridden_at=None,
            )
        )

    async def create_task(self, data: EditorTaskCreate, actor_id: int) -> EditorTask:
        case = await ProductionCaseService(self.db).get_case_for_update(
            data.production_case_id
        )
        revoke_release(case)
        await self._clear_task_related_overrides(case.id, data.source_gate)
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
        case = await ProductionCaseService(self.db).get_case_for_update(
            task.production_case_id
        )
        payload = data.model_dump(exclude_unset=True)
        if not user.is_admin:
            payload.pop("assigned_editor_id", None)
        if payload:
            revoke_release(case)
            await self._clear_task_related_overrides(
                task.production_case_id, task.source_gate
            )
        for key, value in payload.items():
            setattr(task, key, value)
        if task.status in {"resolved", "rejected"} and task.resolved_at is None:
            task.resolved_at = datetime.utcnow()
        elif task.status in {"open", "in_progress"}:
            task.resolved_at = None
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
            else:
                case.editorial_status = "needs_review"
