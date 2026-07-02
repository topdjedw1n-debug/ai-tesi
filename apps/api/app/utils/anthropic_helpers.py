"""Anthropic response helpers shared by every messages.create() call site."""

from typing import Any


def response_text(response: Any) -> str:
    """Concatenate the text blocks of an Anthropic message response.

    Claude 4+/5 models may emit a thinking block FIRST, so
    ``response.content[0].text`` crashes with "'ThinkingBlock' object has no
    attribute 'text'" (found live: sonnet-5 humanization, 03.07.2026). Only
    blocks of type "text" carry the answer.
    """
    parts = [
        block.text
        for block in getattr(response, "content", []) or []
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts)
