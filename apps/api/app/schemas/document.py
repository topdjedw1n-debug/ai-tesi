"""
Document schemas for API requests and responses
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentStatus(str, Enum):
    """Document status enumeration"""

    DRAFT = "draft"
    GENERATING = "generating"
    OUTLINE_GENERATED = "outline_generated"
    SECTIONS_GENERATED = "sections_generated"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_QUALITY = "failed_quality"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_FAILED = "payment_failed"


class AIProvider(str, Enum):
    """AI provider enumeration"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class AIModel(str, Enum):
    """AI model enumeration (dynamically validated per provider)"""

    # OpenAI models
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    # Anthropic models
    CLAUDE_OPUS_4_8 = "claude-opus-4-8"
    CLAUDE_SONNET_5 = "claude-sonnet-5"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"


class DocumentBase(BaseModel):
    """Base document schema"""

    title: str = Field(min_length=1, max_length=500)
    topic: str = Field(min_length=10)
    language: str = Field(default="en", max_length=10)
    target_pages: int = Field(
        default=50, ge=3, le=1000
    )  # CRITICAL: Minimum 3 pages as per business rules
    citation_style: str = Field(default="apa", max_length=50)

    @staticmethod
    def _sanitize(text: str) -> str:
        # Remove HTML tags and excessive whitespace
        text = re.sub(r"<[^>]*>", "", text)
        text = re.sub(r"[\r\n\t]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        return cls._sanitize(v)

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        return cls._sanitize(v)

    @field_validator("citation_style", mode="before")
    @classmethod
    def normalize_citation_style(cls, v: str | None) -> str:
        # Response models also inherit this schema. Preserve legacy values on
        # reads so an old row cannot make list/detail response validation fail;
        # new writes are restricted by DocumentCreate below.
        return str(v or "apa").strip().lower()


class DocumentCreate(DocumentBase):
    """Schema for creating a new document"""

    # Default writer = the AI_FALLBACK_CHAIN head. The manager console sends
    # no model, so these defaults ARE the production writer — keep them in
    # sync with config.AI_FALLBACK_CHAIN (gpt-4 classic here silently routed
    # every console document to the $30/$60 model until 04.07.2026).
    ai_provider: AIProvider | None = Field(
        default=AIProvider.ANTHROPIC, description="AI provider: openai or anthropic"
    )
    ai_model: str | None = Field(default="claude-opus-4-8", description="AI model name")
    additional_requirements: str | None = Field(
        None,
        max_length=5000,
        description="Additional requirements, max 5000 characters",
    )

    @field_validator("citation_style")
    @classmethod
    def require_apa_for_mvp(cls, v: str) -> str:
        # The first production contour is deliberately APA-only. Other styles
        # need citation rules that the current generator cannot yet guarantee.
        if v != "apa":
            raise ValueError("citation_style must be apa for the current MVP")
        return v

    @field_validator("ai_provider", mode="before")
    @classmethod
    def validate_ai_provider(cls, v: str | AIProvider | None) -> AIProvider:
        """Validate AI provider enum"""
        if v is None:
            return AIProvider.ANTHROPIC
        if isinstance(v, str):
            v = v.lower()
            if v not in ["openai", "anthropic"]:
                raise ValueError("ai_provider must be 'openai' or 'anthropic'")
            return AIProvider(v)
        elif isinstance(v, AIProvider):
            return v
        else:
            raise ValueError("ai_provider must be 'openai' or 'anthropic'")

    @field_validator("ai_model")
    @classmethod
    def validate_ai_model(cls, v: str | None, info: Any) -> str:
        """Validate AI model matches provider"""
        provider_value = None
        if hasattr(info, "data"):
            provider = info.data.get("ai_provider")
            if isinstance(provider, AIProvider):
                provider_value = provider.value
            elif isinstance(provider, str):
                provider_value = provider.lower()

        if not v:
            # Provider-aware default so an explicit provider without a model
            # never produces a provider/model mismatch: openai gets its cheap
            # tier, everything else the chain-head writer.
            return "gpt-4o" if provider_value == "openai" else "claude-opus-4-8"

        # Valid models per provider (keep in sync with /generate/models and
        # cost_estimator pricing tables). gpt-4 classic retired as a default
        # (cost review 03.07.2026) but kept here for legacy docs; the cheap
        # tier (4o/4.1-mini/5.4-*) is what current runs use.
        openai_models = [
            "gpt-5.5",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]
        anthropic_models = [
            "claude-opus-4-8",
            "claude-sonnet-5",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
        ]

        if provider_value == "openai":
            if v not in openai_models:
                raise ValueError(
                    f"Invalid model for OpenAI provider. Valid models: {', '.join(openai_models)}"
                )
        elif provider_value == "anthropic":
            if v not in anthropic_models:
                raise ValueError(
                    f"Invalid model for Anthropic provider. Valid models: {', '.join(anthropic_models)}"
                )

        return v

    @field_validator("additional_requirements")
    @classmethod
    def sanitize_additional_requirements(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) > 5000:
            raise ValueError("additional_requirements must not exceed 5000 characters")
        v = re.sub(r"<[^>]*>", "", v)
        v = re.sub(r"[\r\n\t]", " ", v)
        return re.sub(r"\s+", " ", v).strip()


class DocumentUpdate(BaseModel):
    """Schema for updating document information"""

    title: str | None = Field(None, min_length=1, max_length=500)
    topic: str | None = Field(None, min_length=10)
    language: str | None = Field(None, max_length=10)
    target_pages: int | None = Field(
        None, ge=3, le=1000
    )  # CRITICAL: Minimum 3 pages as per business rules


class DocumentResponse(DocumentBase):
    """Schema for document API responses"""

    id: int
    user_id: int
    status: DocumentStatus
    is_archived: bool
    created_at: datetime
    updated_at: datetime | None
    word_count: int
    estimated_reading_time: int
    requirements_file_processed: bool = False
    release_status: str = "not_ready"
    outline: dict[str, Any] | None = None
    sections: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """Schema for document list responses"""

    documents: list[DocumentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ProvenanceEventResponse(BaseModel):
    """Single provenance ledger event"""

    id: int
    stage: str
    event_type: str
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentProvenanceResponse(BaseModel):
    """Chronological provenance ledger for a document"""

    document_id: int
    total: int
    events: list[ProvenanceEventResponse]


class DocumentFeedbackRequest(BaseModel):
    """Manager feedback on a generated document (internal MVP)"""

    text: str = Field(min_length=3, max_length=5000)

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        # Strip HTML but keep line breaks — feedback is freeform prose.
        sanitized = re.sub(r"<[^>]*>", "", v).strip()
        if len(sanitized) < 3:
            raise ValueError("Feedback text is too short")
        return sanitized


class DocumentFeedbackResponse(BaseModel):
    """Confirmation that feedback was recorded"""

    document_id: int
    event_id: int
    created_at: datetime | None = None


class OutlineRequest(BaseModel):
    """Schema for outline generation request"""

    document_id: int = Field(
        ..., gt=0, description="Document ID must be greater than 0"
    )
    additional_requirements: str | None = Field(
        None,
        max_length=5000,
        description="Additional requirements, max 5000 characters",
    )

    @field_validator("additional_requirements")
    @classmethod
    def sanitize_requirements(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) > 5000:
            raise ValueError("additional_requirements must not exceed 5000 characters")
        v = re.sub(r"<[^>]*>", "", v)
        v = re.sub(r"[\r\n\t]", " ", v)
        return re.sub(r"\s+", " ", v).strip()


class OutlineResponse(BaseModel):
    """Schema for outline generation response"""

    outline: dict[str, Any]
    estimated_sections: int
    estimated_word_count: int


class SectionRequest(BaseModel):
    """Schema for section generation request"""

    document_id: int = Field(
        ..., gt=0, description="Document ID must be greater than 0"
    )
    section_title: str
    section_index: int
    additional_requirements: str | None = Field(
        None,
        max_length=5000,
        description="Additional requirements, max 5000 characters",
    )

    @field_validator("section_title")
    @classmethod
    def validate_section_title(cls, v: str) -> str:
        v = re.sub(r"<[^>]*>", "", v)
        v = re.sub(r"[\r\n\t]", " ", v)
        return re.sub(r"\s+", " ", v).strip()

    @field_validator("additional_requirements")
    @classmethod
    def sanitize_section_requirements(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) > 5000:
            raise ValueError("additional_requirements must not exceed 5000 characters")
        v = re.sub(r"<[^>]*>", "", v)
        v = re.sub(r"[\r\n\t]", " ", v)
        return re.sub(r"\s+", " ", v).strip()


class SectionResponse(BaseModel):
    """Schema for section generation response"""

    content: str
    word_count: int
    citations: list[dict[str, Any]]
    estimated_reading_time: int


class DocumentVersionResponse(BaseModel):
    """Schema for document version responses"""

    id: int
    document_id: int
    version_number: int
    changes_summary: str | None
    created_at: datetime
    created_by: int

    model_config = ConfigDict(from_attributes=True)


class ExportRequest(BaseModel):
    """Schema for document export request"""

    format: str = Field(pattern="^(docx|pdf)$")
    include_metadata: bool = True
    include_citations: bool = True


class ExportResponse(BaseModel):
    """Schema for export response"""

    download_url: str
    expires_at: datetime
    file_size: int
    format: str


class AsyncGenerationRequest(BaseModel):
    """Schema for async document generation request"""

    document_id: int
    # Informational only — generation follows document.ai_model; a hardcoded
    # default here would just misreport the writer.
    model: str | None = Field(default=None)
    requirements: str | None = Field(
        default=None,
        max_length=5000,
        description="Optional additions for this run; durable intake is always retained",
    )


class AsyncGenerationResponse(BaseModel):
    """Schema for async generation response"""

    job_id: int
    status: str
    check_url: str


class JobStatusResponse(BaseModel):
    """Schema for job status response"""

    job_id: int
    status: str
    progress: int
    document_id: int | None = None
    error_message: str | None = None


class ActivityItem(BaseModel):
    """Schema for activity item"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str  # document_created, outline_generated, section_generated, document_completed, export_created
    title: str
    description: str
    timestamp: datetime
    status: str  # success, error, pending


class ActivityListResponse(BaseModel):
    """Schema for activity list response"""

    activities: list[ActivityItem]
