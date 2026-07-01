"""Production case schemas for the internal QA-first platform."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

CASE_STATUS_VALUES = {
    "draft",
    "ready",
    "not_started",
    "running",
    "completed",
    "failed",
    "failed_quality",
    "no_data",
    "passed",
    "needs_review",
    "not_required",
    "pending",
    "in_progress",
    "paid",
    "refunded",
    "not_ready",
    "blocked",
    "approved",
    "released",
    "delivered",
}

GATE_KEYS = {
    "citation_verification",
    "claim_support",
    "section_quality",
    "plagiarism_proxy",
    "ai_detection_proxy",
    "editorial_review",
    "delivery_package",
}

GATE_STATUSES = {"passed", "failed", "warning", "no_data", "overridden"}
TASK_STATUSES = {"open", "in_progress", "resolved", "rejected"}


def _validate_choice(
    value: str | None, allowed: set[str], field_name: str
) -> str | None:
    if value is None:
        return value
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}")
    return normalized


class ProductionCaseCreate(BaseModel):
    document_id: int = Field(gt=0)
    manager_id: int | None = Field(default=None, gt=0)
    editor_id: int | None = Field(default=None, gt=0)
    deadline_at: datetime | None = None
    citation_style: str | None = Field(default=None, max_length=50)
    requirements_text: str | None = Field(default=None, max_length=10000)


class ProductionCaseUpdate(BaseModel):
    manager_id: int | None = Field(default=None, gt=0)
    editor_id: int | None = Field(default=None, gt=0)
    deadline_at: datetime | None = None
    citation_style: str | None = Field(default=None, max_length=50)
    requirements_text: str | None = Field(default=None, max_length=10000)
    intake_status: str | None = None
    generation_status: str | None = None
    qa_status: str | None = None
    editorial_status: str | None = None
    payment_status: str | None = None
    delivery_status: str | None = None
    release_status: str | None = None
    human_minutes_budget: int | None = Field(default=None, ge=0)
    human_minutes_used: int | None = Field(default=None, ge=0)
    cost_cents: int | None = Field(default=None, ge=0)
    release_notes: str | None = Field(default=None, max_length=5000)

    @field_validator(
        "intake_status",
        "generation_status",
        "qa_status",
        "editorial_status",
        "payment_status",
        "delivery_status",
        "release_status",
    )
    @classmethod
    def validate_case_status(cls, value: str | None) -> str | None:
        return _validate_choice(value, CASE_STATUS_VALUES, "status")


class ProductionCaseResponse(BaseModel):
    id: int
    document_id: int
    client_user_id: int
    manager_id: int | None = None
    editor_id: int | None = None
    deadline_at: datetime | None = None
    citation_style: str | None = None
    requirements_text: str | None = None
    intake_status: str
    generation_status: str
    qa_status: str
    editorial_status: str
    payment_status: str
    delivery_status: str
    release_status: str
    human_minutes_budget: int
    human_minutes_used: int
    cost_cents: int
    release_notes: str | None = None
    released_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document: dict[str, Any] | None = None
    client_email: str | None = None
    manager_email: str | None = None
    editor_email: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductionCaseListResponse(BaseModel):
    cases: list[ProductionCaseResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ReleaseGateResponse(BaseModel):
    id: int | None = None
    production_case_id: int
    gate_key: str
    status: str
    severity: str = "blocking"
    blocking: bool = True
    source: str | None = None
    summary: str | None = None
    evidence: dict[str, Any] | None = None
    override_allowed: bool = False
    override_reason: str | None = None
    overridden_by_id: int | None = None
    overridden_at: datetime | None = None
    last_checked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GateOverrideRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class ManualDetectorResultRequest(BaseModel):
    detector_name: str = Field(min_length=2, max_length=200)
    result_percent: float = Field(ge=0, le=100)
    threshold_percent: float = Field(ge=0, le=100)
    checked_at: datetime
    report_ref: str = Field(min_length=3, max_length=500)
    reason: str = Field(min_length=10, max_length=2000)


class ReleaseRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=5000)


class EditorTaskCreate(BaseModel):
    production_case_id: int = Field(gt=0)
    assigned_editor_id: int = Field(gt=0)
    section_id: int | None = Field(default=None, gt=0)
    source_gate: str | None = Field(default=None, max_length=100)
    finding_key: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)


class EditorTaskUpdate(BaseModel):
    assigned_editor_id: int | None = Field(default=None, gt=0)
    status: str | None = None
    resolution_notes: str | None = Field(default=None, max_length=5000)
    minutes_spent: int | None = Field(default=None, ge=0)

    @field_validator("status")
    @classmethod
    def validate_task_status(cls, value: str | None) -> str | None:
        return _validate_choice(value, TASK_STATUSES, "status")


class EditorTaskResolveRequest(BaseModel):
    resolution_notes: str = Field(min_length=1, max_length=5000)
    minutes_spent: int = Field(ge=0)
    status: str = Field(default="resolved")

    @field_validator("status")
    @classmethod
    def validate_resolution_status(cls, value: str) -> str:
        normalized = _validate_choice(value, {"resolved", "rejected"}, "status")
        return normalized or "resolved"


class EditorTaskResponse(BaseModel):
    id: int
    production_case_id: int
    document_id: int
    section_id: int | None = None
    assigned_editor_id: int
    created_by_id: int | None = None
    source_gate: str | None = None
    finding_key: str | None = None
    title: str
    description: str | None = None
    status: str
    resolution_notes: str | None = None
    minutes_spent: int
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document_title: str | None = None
    section_title: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EditorTaskListResponse(BaseModel):
    tasks: list[EditorTaskResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
