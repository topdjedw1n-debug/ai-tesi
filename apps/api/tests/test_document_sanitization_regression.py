"""ISSUE-003: normalized empty input poisoned the persisted document list.

Found by /qa on 2026-09-07.
Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
"""

import pytest
from pydantic import ValidationError

from app.schemas.document import DocumentCreate, DocumentUpdate


@pytest.mark.parametrize("schema", [DocumentCreate, DocumentUpdate])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),
        ("title", "<div></div>"),
        ("topic", " " * 20),
        ("topic", "<div></div>"),
        ("topic", "<div>short</div>"),
    ],
)
def test_rejects_input_that_becomes_empty_or_too_short(schema, field, value):
    payload = {"title": "Valid title", "topic": "Valid academic topic", field: value}
    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize("schema", [DocumentCreate, DocumentUpdate])
def test_preserves_normalized_valid_content(schema):
    document = schema(title="<b>Titolo</b>", topic="  Assistenza\n infermieristica  ")
    assert document.title == "Titolo"
    assert document.topic == "Assistenza infermieristica"


def test_partial_update_can_omit_text_fields():
    assert DocumentUpdate(target_pages=18).model_dump(exclude_unset=True) == {
        "target_pages": 18
    }
