"""Boundary contracts for the narrow APA generation contour."""

from datetime import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError
from app.schemas.document import (
    AsyncGenerationRequest,
    DocumentCreate,
    DocumentResponse,
)
from app.services.custom_requirements_service import (
    MAX_GENERATION_REQUIREMENTS_CHARS,
    combine_generation_requirements,
)


def test_new_document_rejects_non_apa_style():
    with pytest.raises(PydanticValidationError, match="citation_style must be apa"):
        DocumentCreate(
            title="Legacy style thesis",
            topic="A sufficiently long academic research topic",
            citation_style="chicago",
        )


def test_response_can_serialize_legacy_citation_style():
    response = DocumentResponse.model_validate(
        {
            "id": 1,
            "user_id": 2,
            "title": "Legacy thesis",
            "topic": "A sufficiently long legacy academic research topic",
            "language": "it",
            "target_pages": 40,
            "citation_style": "Chicago",
            "status": "draft",
            "is_archived": False,
            "created_at": datetime(2026, 7, 10),
            "updated_at": None,
            "word_count": 0,
            "estimated_reading_time": 1,
        }
    )
    assert response.citation_style == "chicago"


def test_per_run_requirements_are_bounded():
    with pytest.raises(PydanticValidationError):
        AsyncGenerationRequest(document_id=1, requirements="x" * 5001)


def test_combined_generation_context_fails_instead_of_truncating():
    with pytest.raises(ValidationError, match="generation limit"):
        combine_generation_requirements(
            "p" * 50_000,
            "r" * (MAX_GENERATION_REQUIREMENTS_CHARS - 50_000),
        )
