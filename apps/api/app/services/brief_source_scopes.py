"""Search the nested brief as well as chapter titles, without changing the brief."""

import re
from typing import Any


def brief_source_scopes(requirements: str | None, outline: Any) -> list[str]:
    scopes = []
    text = requirements or ""
    # Supports both pasted one-line indices and uploaded multiline indices.
    markers = list(re.finditer(r"(?<![\w.])\d{1,2}(?:\.\d{1,2}){1,3}[.)]?\s+", text))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        heading = re.split(
            r"\n\s*\n|\b(?:CAPITOLO|CHAPTER)\s+\d+",
            text[marker.end() : end],
            maxsplit=1,
            flags=re.I,
        )[0]
        heading = re.sub(r"\s+", " ", heading).strip(" \t\n*•:;.")
        if heading:
            scopes.append(heading)

    def visit(items):
        for item in items if isinstance(items, list) else []:
            if isinstance(item, str) and item.strip():
                scopes.append(item.strip())
            elif isinstance(item, dict):
                if isinstance(item.get("title"), str):
                    scopes.append(item["title"].strip())
                visit(item.get("subsections"))

    if not scopes and isinstance(outline, dict):
        visit(outline.get("sections"))
    seen = set()
    return [
        scope
        for scope in scopes
        if scope and not (scope.casefold() in seen or seen.add(scope.casefold()))
    ]
