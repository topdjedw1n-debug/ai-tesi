"""
Document related models
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Document(Base):
    """Document model"""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_id", "user_id"),
        Index("ix_documents_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Document metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=True)
    target_pages: Mapped[int] = mapped_column(Integer, default=10, nullable=True)

    # Document state
    status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=True
    )  # draft, generating, completed, failed
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    # AI generation settings
    ai_provider: Mapped[str] = mapped_column(
        String(50), default="openai", nullable=True
    )  # openai, anthropic
    ai_model: Mapped[str] = mapped_column(String(100), default="gpt-4", nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=True)

    # Content
    outline: Mapped[Any] = mapped_column(JSON, nullable=True)  # Store outline structure
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Full document content

    # File paths
    docx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_requirements_file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Usage tracking
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    generation_time_seconds: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    sections = relationship(
        "DocumentSection", back_populates="document", cascade="all, delete-orphan"
    )
    payment = relationship("Payment", back_populates="document", uselist=False)
    sources = relationship(
        "DocumentSource", back_populates="document", cascade="all, delete-orphan"
    )
    provenance_events = relationship(
        "DocumentProvenance", back_populates="document", cascade="all, delete-orphan"
    )
    production_case = relationship(
        "ProductionCase", back_populates="document", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, status={self.status})>"


class DocumentSection(Base):
    """Document section model"""

    __tablename__ = "document_sections"
    __table_args__ = (Index("ix_document_sections_document_id", "document_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False
    )

    # Section metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_type: Mapped[str] = mapped_column(
        String(50), default="content", nullable=True
    )  # content, introduction, conclusion, etc.

    # Content
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    # Quality metrics
    grammar_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # 0-100, higher is better
    plagiarism_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # 0-100, lower is better (% plagiarism)
    ai_detection_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # 0-100, lower is better (% AI-generated)
    quality_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # 0-100, higher is better (overall quality)

    # Claim faithfulness audit (advisory): per-claim verdicts from
    # claim_verifier.py - {"total", "checked", "counts", "claims": [...]}
    claim_verification: Mapped[Any] = mapped_column(JSON, nullable=True)

    # Reviewer panel report (quality_validator.py): {"valid", "overall_score",
    # "passed", "critical_override", "reviewers": [...], "advocate": {...}}
    quality_panel: Mapped[Any] = mapped_column(JSON, nullable=True)

    # Generation state
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=True
    )  # pending, generating, completed, failed
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    generation_time_seconds: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    document = relationship("Document", back_populates="sections")
    # No delete-orphan: deleting a section keeps its sources (section_id becomes NULL)
    sources = relationship("DocumentSource", back_populates="section")

    def __repr__(self) -> str:
        return (
            f"<DocumentSection(id={self.id}, title={self.title}, status={self.status})>"
        )


class DocumentOutline(Base):
    """Document outline model"""

    __tablename__ = "document_outlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False
    )

    # Outline structure
    outline_data: Mapped[Any] = mapped_column(
        JSON, nullable=False
    )  # Store the full outline structure
    total_sections: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    # Generation metadata
    ai_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    generation_time_seconds: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return f"<DocumentOutline(id={self.id}, document_id={self.document_id})>"


class AIGenerationJob(Base):
    """AI generation job model for tracking AI operations"""

    __tablename__ = "ai_generation_jobs"
    __table_args__ = (
        Index("ix_ai_generation_jobs_user_id", "user_id"),
        Index("ix_ai_generation_jobs_started_at", "started_at"),
        # NOTE: Consider adding unique constraint for (document_id, job_type) where status IN ('queued', 'running')
        # to provide additional protection against race conditions at DB level
        # Example: UniqueConstraint('document_id', 'job_type', name='uq_active_job_per_document', postgresql_where=status.in_(['queued', 'running']))
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=True
    )

    # Job metadata
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # outline, section, etc.
    ai_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Job status and progress
    status: Mapped[str] = mapped_column(
        String(50), default="queued", nullable=True
    )  # queued, running, completed, failed
    progress: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )  # 0-100 percentage

    # Usage tracking
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    cost_cents: Mapped[int] = mapped_column(
        Integer, default=0, nullable=True
    )  # Cost in cents
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AIGenerationJob(id={self.id}, user_id={self.user_id}, job_type={self.job_type})>"


class DocumentDraft(Base):
    """Auto-save drafts for documents"""

    __tablename__ = "document_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    # Draft content
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<DocumentDraft(id={self.id}, document_id={self.document_id}, version={self.version})>"


class DocumentProvenance(Base):
    """Provenance event for a document's generation pipeline (append-only audit trail)"""

    __tablename__ = "document_provenance"
    __table_args__ = (
        Index("ix_document_provenance_document_id", "document_id"),
        Index("ix_document_provenance_document_id_stage", "document_id", "stage"),
        Index("ix_document_provenance_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    # Event metadata
    stage: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # retrieval, outline, generation, quality, verification, export
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # sources_retrieved, source_verified, citation_flagged, etc.
    payload: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )  # Arbitrary structured event data

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    # Relationships
    document = relationship("Document", back_populates="provenance_events")

    def __repr__(self) -> str:
        return (
            f"<DocumentProvenance(id={self.id}, document_id={self.document_id}, "
            f"stage={self.stage}, event_type={self.event_type})>"
        )


class DocumentSource(Base):
    """Persisted source retrieved for a document (mirrors SourceDoc in rag_retriever.py)"""

    __tablename__ = "document_sources"
    __table_args__ = (
        Index("ix_document_sources_document_id", "document_id"),
        Index("ix_document_sources_section_id", "section_id"),
        Index("ix_document_sources_verification_status", "verification_status"),
        Index(
            "uq_document_sources_document_id_doi",
            "document_id",
            "doi",
            unique=True,
            postgresql_where=text("doi IS NOT NULL"),
            sqlite_where=text("doi IS NOT NULL"),
        ),
        Index(
            "uq_document_sources_document_id_citation_key",
            "document_id",
            "citation_key",
            unique=True,
            postgresql_where=text("citation_key IS NOT NULL"),
            sqlite_where=text("citation_key IS NOT NULL"),
        ),
        Index(
            "ix_document_sources_is_in_upfront_pack",
            "document_id",
            "is_in_upfront_pack",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True
    )

    # Raw retrieval metadata (matches SourceDoc dataclass keys)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    authors: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )  # list[str] of author names
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # e.g. Semantic Scholar paper ID
    venue: Mapped[str | None] = mapped_column(String(500), nullable=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    doi: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # normalized lowercase

    # Verification state
    verification_status: Mapped[str] = mapped_column(
        String(50), default="unverified", nullable=True
    )  # unverified, verified, mismatched, not_found, failed
    canonical_metadata: Mapped[Any] = mapped_column(
        JSON, nullable=True
    )  # Normalized record from Crossref/OpenAlex/S2/arXiv after verification

    # Upfront topic-locked source pack (source_pack.py). Pack rows carry a
    # stable, pack-scoped citation_key and an on_topic_score; per-section cited
    # rows leave these NULL / False.
    citation_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # stable pack-scoped key, e.g. Rossi2021 / Rossi2021b
    on_topic_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # topic-relevance [0,1] vs document.topic at pack-build time
    is_in_upfront_pack: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    document = relationship("Document", back_populates="sources")
    section = relationship("DocumentSection", back_populates="sources")

    def __repr__(self) -> str:
        return (
            f"<DocumentSource(id={self.id}, document_id={self.document_id}, "
            f"verification_status={self.verification_status})>"
        )


class ProductionCase(Base):
    """Internal production case wrapping a document for Phase 2 operations."""

    __tablename__ = "production_cases"
    __table_args__ = (
        Index("ix_production_cases_document_id", "document_id"),
        Index("ix_production_cases_client_user_id", "client_user_id"),
        Index("ix_production_cases_manager_id", "manager_id"),
        Index("ix_production_cases_editor_id", "editor_id"),
        Index("ix_production_cases_release_status", "release_status"),
        UniqueConstraint("document_id", name="uq_production_cases_document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    client_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    editor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    citation_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requirements_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    intake_status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=False
    )
    generation_status: Mapped[str] = mapped_column(
        String(50), default="not_started", nullable=False
    )
    qa_status: Mapped[str] = mapped_column(
        String(50), default="no_data", nullable=False
    )
    editorial_status: Mapped[str] = mapped_column(
        String(50), default="not_started", nullable=False
    )
    payment_status: Mapped[str] = mapped_column(
        String(50), default="not_required", nullable=False
    )
    delivery_status: Mapped[str] = mapped_column(
        String(50), default="not_ready", nullable=False
    )
    release_status: Mapped[str] = mapped_column(
        String(50), default="not_ready", nullable=False
    )

    human_minutes_budget: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    human_minutes_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    document = relationship("Document", back_populates="production_case")
    client = relationship("User", foreign_keys=[client_user_id])
    manager = relationship("User", foreign_keys=[manager_id])
    editor = relationship("User", foreign_keys=[editor_id])
    release_gates = relationship(
        "ReleaseGateResult",
        back_populates="production_case",
        cascade="all, delete-orphan",
    )
    editor_tasks = relationship(
        "EditorTask",
        back_populates="production_case",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<ProductionCase(id={self.id}, document_id={self.document_id}, "
            f"release_status={self.release_status})>"
        )


class ReleaseGateResult(Base):
    """Release gate state for a production case."""

    __tablename__ = "release_gate_results"
    __table_args__ = (
        Index("ix_release_gate_results_case_id", "production_case_id"),
        Index("ix_release_gate_results_gate_key", "gate_key"),
        UniqueConstraint(
            "production_case_id", "gate_key", name="uq_release_gate_case_gate"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    production_case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("production_cases.id", ondelete="CASCADE"), nullable=False
    )
    gate_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="no_data", nullable=False)
    severity: Mapped[str] = mapped_column(
        String(50), default="blocking", nullable=False
    )
    blocking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[Any] = mapped_column(JSON, nullable=True)
    override_allowed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    overridden_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    overridden_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    production_case = relationship("ProductionCase", back_populates="release_gates")
    overridden_by = relationship("User", foreign_keys=[overridden_by_id])

    def __repr__(self) -> str:
        return (
            f"<ReleaseGateResult(id={self.id}, case_id={self.production_case_id}, "
            f"gate_key={self.gate_key}, status={self.status})>"
        )


class EditorTask(Base):
    """Finding-specific task assigned to an editor."""

    __tablename__ = "editor_tasks"
    __table_args__ = (
        Index("ix_editor_tasks_case_id", "production_case_id"),
        Index("ix_editor_tasks_assigned_editor_id", "assigned_editor_id"),
        Index("ix_editor_tasks_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    production_case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("production_cases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True
    )
    assigned_editor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    source_gate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finding_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    minutes_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    production_case = relationship("ProductionCase", back_populates="editor_tasks")
    document = relationship("Document")
    section = relationship("DocumentSection")
    assigned_editor = relationship("User", foreign_keys=[assigned_editor_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return (
            f"<EditorTask(id={self.id}, case_id={self.production_case_id}, "
            f"status={self.status})>"
        )
