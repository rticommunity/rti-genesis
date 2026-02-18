"""
CodexBackend — OpenAI Codex CLI subprocess bridge.

Translates 'codex exec --json' JSONL event streams into normalised
CodingEvent objects.
"""

import json
import os
from typing import List, Optional

from .base import CodingBackend
from .events import CodingEvent


class CodexBackend(CodingBackend):

    def __init__(self, model: str = "gpt-5.3-codex"):
        super().__init__()
        self._model = model

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "codex"

    @property
    def cli_binary(self) -> str:
        return "codex"

    @property
    def api_key_env_vars(self) -> List[str]:
        return ["OPENAI_API_KEY", "CODEX_API_KEY"]

    # ------------------------------------------------------------------
    # Command building
    # ------------------------------------------------------------------

    def build_command(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> List[str]:
        # cwd is handled via subprocess cwd param, not in the command
        if session_id:
            return [
                "codex", "exec", "resume", session_id,
                "-m", self._model, "--json",
            ]
        return ["codex", "exec", "-m", self._model, "--json", prompt]

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def build_env(self) -> dict:
        env = os.environ.copy()
        if self._auth_mode == "subscription":
            env.pop("OPENAI_API_KEY", None)
            env.pop("CODEX_API_KEY", None)
        return env

    # ------------------------------------------------------------------
    # Event parsing
    # ------------------------------------------------------------------

    def parse_line(self, line: str) -> Optional[CodingEvent]:
        if not line:
            return None
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return None

        t = obj.get("type", "")
        item = obj.get("item", {})
        item_type = item.get("type", "")

        if t == "thread.started":
            return CodingEvent(
                kind="init",
                session_id=obj.get("thread_id", ""),
                raw=obj,
            )

        if t == "item.completed" and item_type == "agent_message":
            return CodingEvent(
                kind="text",
                text=item.get("text", ""),
                raw=obj,
            )

        if t == "item.completed" and item_type == "tool_call":
            # Arguments may be malformed JSON — degrade gracefully
            args_raw = item.get("arguments", "{}")
            try:
                tool_input = json.loads(args_raw)
            except (json.JSONDecodeError, ValueError):
                tool_input = {"_raw": args_raw}
            return CodingEvent(
                kind="tool_start",
                tool_name=item.get("name", ""),
                tool_input=tool_input,
                raw=obj,
            )

        if t == "item.completed" and item_type == "tool_output":
            return CodingEvent(
                kind="tool_result",
                tool_output=item.get("output", ""),
                raw=obj,
            )

        if t == "turn.completed":
            return CodingEvent(
                kind="done",
                raw=obj.get("usage", {}),
            )

        # turn.started and other unknown events are skipped
        return None
