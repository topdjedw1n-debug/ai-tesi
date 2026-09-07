"""Validate the executable part of a generated plan before it becomes a checkpoint."""

from typing import Any


def validate_outline(value: Any, *, generated: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("The outline must be a JSON object")
    sections = value.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("The outline must contain a non-empty sections array")
    normalized = []
    for index, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            raise ValueError(f"Section {index} must be an object")
        title = section.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Section {index} must have a non-empty title")
        item = {**section, "title": title.strip()}
        for field in ("estimated_words", "target_word_count", "word_count"):
            if field not in item:
                continue
            raw = item[field]
            # Legacy plans use null/zero for an unspecified optional target;
            # the worker has always fallen back to the next field or 500.
            if not generated and raw in (None, 0, "", "0"):
                item.pop(field)
                continue
            if isinstance(raw, str):
                raw = raw.strip().replace(",", "").replace(" ", "")
            try:
                number = int(raw)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    f"Section {index}: {field} must be a positive integer"
                ) from exc
            if (
                isinstance(raw, bool)
                or number <= 0
                or (isinstance(raw, float) and raw != number)
            ):
                raise ValueError(f"Section {index}: {field} must be a positive integer")
            item[field] = number
        if generated and not 1 <= item.get("estimated_words", 0) <= 3000:
            raise ValueError(
                f"Section {index}: estimated_words must be 1-3000; split longer chapters into sections"
            )
        normalized.append(item)
    return {**value, "sections": normalized}
