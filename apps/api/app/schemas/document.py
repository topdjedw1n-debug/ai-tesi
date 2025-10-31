"""
Document schemas for API requests and responses
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentStatus(str, Enum):
    """Document status enumeration"""
    DRAFT = "draft"
    OUTLINE_GENERATED = "outline_generated"
    SECTIONS_GENERATED = "sections_generated"
    COMPLETED = "completed"


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
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"


class DocumentBase(BaseModel):
    """Base document schema"""
    title: str = Field(..., min_length=1, max_length=500)
    topic: str = Field(..., min_length=10)
    language: str = Field(default="en", max_length=10)
    target_pages: int = Field(default=50, ge=1, le=1000)

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


class DocumentCreate(DocumentBase):
    """Schema for creating a new document"""
    ai_provider: AIProvider | None = Field(default=AIProvider.OPENAI, description="AI provider: openai or anthropic")
    ai_model: str | None = Field(default="gpt-4", description="AI model name")
    additional_requirements: str | None = Field(None, max_length=5000, description="Additional requirements, max 5000 characters")

    @field_validator("ai_provider", mode="before")
    @classmethod
    def validate_ai_provider(cls, v):
        """Validate AI provider enum"""
        if v is None:
            return AIProvider.OPENAI
        if isinstance(v, str):
            v = v.lower()
            if v not in ["openai", "anthropic"]:
                raise ValueError("ai_provider must be 'openai' or 'anthropic'")
            return AIProvider(v)
        return v

    @field_validator("ai_model")
    @classmethod
    def validate_ai_model(cls, v, info):
        """Validate AI model matches provider"""
        if not v:
            return "gpt-4"  # Default

        provider_value = None
        if hasattr(info, "data"):
            provider = info.data.get("ai_provider")
            if isinstance(provider, AIProvider):
                provider_value = provider.value
            elif isinstance(provider, str):
                provider_value = provider.lower()

        # Valid models per provider
        openai_models = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
        anthropic_models = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]

        if provider_value == "openai":
            if v not in openai_models:
                raise ValueError(f"Invalid model for OpenAI provider. Valid models: {', '.join(openai_models)}")
        elif provider_value == "anthropic":
            if v not in anthropic_models:
                raise ValueError(f"Invalid model for Anthropic provider. Valid models: {', '.join(anthropic_models)}")

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
    target_pages: int | None = Field(None, ge=1, le=1000)


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
    outline: dict[str, Any] | None = None
    sections: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for document list responses"""
    documents: list[DocumentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class OutlineRequest(BaseModel):
    """Schema for outline generation request"""
    document_id: int = Field(..., gt=0, description="Document ID must be greater than 0")
    additional_requirements: str | None = Field(None, max_length=5000, description="Additional requirements, max 5000 characters")

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
    document_id: int = Field(..., gt=0, description="Document ID must be greater than 0")
    section_title: str
    section_index: int
    additional_requirements: str | None = Field(None, max_length=5000, description="Additional requirements, max 5000 characters")

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

    class Config:
        from_attributes = True


class ExportRequest(BaseModel):
    """Schema for document export request"""
    document_id: int = Field(..., gt=0, description="Document ID must be greater than 0")
    format: str = Field(..., pattern="^(docx|pdf)$")
    include_metadata: bool = True
    include_citations: bool = True


class ExportResponse(BaseModel):
    """Schema for export response"""
    download_url: str
    expires_at: datetime
    file_size: int
    format: str
