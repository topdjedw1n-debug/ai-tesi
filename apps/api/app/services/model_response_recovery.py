"""Keep incomplete provider output out of persisted generation checkpoints."""

import re
from dataclasses import dataclass


def section_output_budget(prompt: str, model: str) -> int:
    """Reserve enough output for the writer's existing per-section word target."""
    match = re.search(r"Section Length: write approximately (\d+) words", prompt)
    base = 8000 if model.startswith("gpt-5") else 4000
    return min(16000, max(base, int(match.group(1)) * 4)) if match else base


class IncompleteModelResponse(ValueError):
    pass


@dataclass
class ModelResponseRecovery:
    max_tokens: int = 4000

    @property
    def timeout_seconds(self) -> float:
        # Longer non-streaming responses need more time. The independent
        # worker heartbeat and cancellation remain active during this wait.
        return min(600.0, max(180.0, self.max_tokens * 0.045))

    def validate(self, content: str | None, stop_reason: str | None) -> str:
        if stop_reason in ("max_tokens", "length"):
            # Reissue the same task and model with room for a complete answer;
            # never concatenate partial JSON or duplicate section paragraphs.
            self.max_tokens = min(self.max_tokens * 2, 16000)
            raise IncompleteModelResponse("Model output reached its token limit")
        if not isinstance(content, str) or not content.strip():
            raise IncompleteModelResponse("Model returned empty text")
        return content
