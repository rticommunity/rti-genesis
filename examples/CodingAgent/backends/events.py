"""
CodingEvent — Normalized event model for coding harness streams.

Both Claude Code and Codex produce backend-specific JSON events.
This dataclass is the API boundary: everything above it is backend-agnostic.
"""

from dataclasses import dataclass, field
from typing import Dict, Any

VALID_KINDS = {"init", "text", "tool_start", "tool_result", "done", "error"}


@dataclass
class CodingEvent:
    kind: str
    session_id: str = ""
    text: str = ""
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in VALID_KINDS:
            raise ValueError(
                f"Invalid CodingEvent kind {self.kind!r}; "
                f"must be one of {sorted(VALID_KINDS)}"
            )
