"""
Document related models
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Document(Base):
    """Document model"""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_id", "user_id"),
        Index("ix_documents_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Document metadata
    title = Column(String(500), nullable=False)
    topic = Column(String(500), nullable=False)
    language = Column(String(10), default="en")
    target_pages = Column(Integer, default=10)

    # Document state
    status = Column(String(50), default="draft")  # draft, generating, completed, failed
    is_public = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)

    # AI generation settings
    ai_provider = Column(String(50), default="openai")  # openai, anthropic
    ai_model = Column(String(100), default="gpt-4")
    temperature = Column(Float, default=0.7)

    # Content
    outline = Column(JSON)  # Store outline structure
    content = Column(Text)  # Full document content

    # File paths
    docx_path = Column(String(500))
    pdf_path = Column(String(500))
    custom_requirements_file_path = Column(String(500), nullable=True)

    # Usage tracking
    tokens_used = Column(Integer, default=0)
    generation_time_seconds = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    sections = relationship(
        "DocumentSection", back_populates="document", cascade="all, delete-orphan"
    )
    payment = relationship("Payment", back_populates="document", uselist=False)

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, status={self.status})>"


class DocumentSection(Base):
    """Document section model"""

    __tablename__ = "document_sections"
    __table_args__ = (Index("ix_document_sections_document_id", "document_id"),)

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    # Section metadata
    title = Column(String(500), nullable=False)
    section_index = Column(Integer, nullable=False)
    section_type = Column(
        String(50), default="content"
    )  # content, introduction, conclusion, etc.

    # Content
    content = Column(Text)
    word_count = Column(Integer, default=0)

    # Quality metrics
    grammar_score = Column(Float, nullable=True)  # 0-100, higher is better
    plagiarism_score = Column(
        Float, nullable=True
    )  # 0-100, lower is better (% plagiarism)
    ai_detection_score = Column(
        Float, nullable=True
    )  # 0-100, lower is better (% AI-generated)
    quality_score = Column(
        Float, nullable=True
    )  # 0-100, higher is better (overall quality)

    # Generation state
    status = Column(
        String(50), default="pending"
    )  # pending, generating, completed, failed
    tokens_used = Column(Integer, default=0)
    generation_time_seconds = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    document = relationship("Document", back_populates="sections")

    def __repr__(self) -> str:
        return (
            f"<DocumentSection(id={self.id}, title={self.title}, status={self.status})>"
        )


class DocumentOutline(Base):
    """Document outline model"""

    __tablename__ = "document_outlines"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    # Outline structure
    outline_data = Column(JSON, nullable=False)  # Store the full outline structure
    total_sections = Column(Integer, default=0)

    # Generation metadata
    ai_provider = Column(String(50))
    ai_model = Column(String(100))
    tokens_used = Column(Integer, default=0)
    generation_time_seconds = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # Job metadata
    job_type = Column(String(50), nullable=False)  # outline, section, etc.
    ai_provider = Column(String(50))
    ai_model = Column(String(100))

    # Job status and progress
    status = Column(String(50), default="queued")  # queued, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100 percentage

    # Usage tracking
    total_tokens = Column(Integer, default=0)
    cost_cents = Column(Integer, default=0)  # Cost in cents
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<AIGenerationJob(id={self.id}, user_id={self.user_id}, job_type={self.job_type})>"


class DocumentDraft(Base):
    """Auto-save drafts for documents"""

    __tablename__ = "document_drafts"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Draft content
    content = Column(Text, nullable=True)
    version = Column(Integer, default=1)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<DocumentDraft(id={self.id}, document_id={self.document_id}, version={self.version})>"
