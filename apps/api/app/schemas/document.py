"""
Document schemas for API requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    """Document status enumeration"""
    DRAFT = "draft"
    OUTLINE_GENERATED = "outline_generated"
    SECTIONS_GENERATED = "sections_generated"
    COMPLETED = "completed"


class DocumentBase(BaseModel):
    """Base document schema"""
    title: str = Field(..., min_length=1, max_length=500)
    topic: str = Field(..., min_length=10)
    language: str = Field(default="en", max_length=10)
    target_pages: int = Field(default=50, ge=1, le=1000)


class DocumentCreate(DocumentBase):
    """Schema for creating a new document"""
    pass


class DocumentUpdate(BaseModel):
    """Schema for updating document information"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    topic: Optional[str] = Field(None, min_length=10)
    language: Optional[str] = Field(None, max_length=10)
    target_pages: Optional[int] = Field(None, ge=1, le=1000)


class DocumentResponse(DocumentBase):
    """Schema for document API responses"""
    id: int
    user_id: int
    status: DocumentStatus
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]
    word_count: int
    estimated_reading_time: int
    outline: Optional[Dict[str, Any]] = None
    sections: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for document list responses"""
    documents: List[DocumentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class OutlineRequest(BaseModel):
    """Schema for outline generation request"""
    document_id: int
    additional_requirements: Optional[str] = None


class OutlineResponse(BaseModel):
    """Schema for outline generation response"""
    outline: Dict[str, Any]
    estimated_sections: int
    estimated_word_count: int


class SectionRequest(BaseModel):
    """Schema for section generation request"""
    document_id: int
    section_title: str
    section_index: int
    additional_requirements: Optional[str] = None


class SectionResponse(BaseModel):
    """Schema for section generation response"""
    content: str
    word_count: int
    citations: List[Dict[str, Any]]
    estimated_reading_time: int


class DocumentVersionResponse(BaseModel):
    """Schema for document version responses"""
    id: int
    document_id: int
    version_number: int
    changes_summary: Optional[str]
    created_at: datetime
    created_by: int
    
    class Config:
        from_attributes = True


class ExportRequest(BaseModel):
    """Schema for document export request"""
    document_id: int
    format: str = Field(..., regex="^(docx|pdf)$")
    include_metadata: bool = True
    include_citations: bool = True


class ExportResponse(BaseModel):
    """Schema for export response"""
    download_url: str
    expires_at: datetime
    file_size: int
    format: str
