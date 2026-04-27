"""
ClaudeBackend — Claude Code CLI subprocess bridge.

Translates 'claude -p --output-format stream-json' event streams into
normalised CodingEvent objects.
"""

import json
import os
from typing import List, Optional

from .base import CodingBackend
from .events import CodingEvent


class ClaudeBackend(CodingBackend):

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "claude"

    @property
    def cli_binary(self) -> str:
        return "claude"

    @property
    def api_key_env_vars(self) -> List[str]:
        return ["ANTHROPIC_API_KEY"]

    # ------------------------------------------------------------------
    # Command building
    # ------------------------------------------------------------------

    def build_command(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> List[str]:
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--permission-mode", "bypassPermissions",
        ]
        if session_id:
            cmd += ["--session-id", session_id]
        # cwd is handled by subprocess cwd= parameter, not a CLI flag
        return cmd

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def build_env(self) -> dict:
        env = os.environ.copy()
        if self._auth_mode == "subscription":
            env.pop("ANTHROPIC_API_KEY", None)
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
        s = obj.get("subtype", "")

        if t == "system" and s == "init":
            return CodingEvent(
                kind="init",
                session_id=obj.get("session_id", ""),
                raw=obj,
            )

        if t == "assistant" and s == "text":
            return CodingEvent(
                kind="text",
                text=obj.get("text", ""),
                raw=obj,
            )

        if t == "assistant" and s == "tool_use":
            tool = obj.get("tool", {})
            return CodingEvent(
                kind="tool_start",
                tool_name=tool.get("name", ""),
                tool_input=tool.get("input", {}),
                raw=obj,
            )

        if t == "tool" and s == "result":
            return CodingEvent(
                kind="tool_result",
                tool_output=obj.get("content", ""),
                raw=obj,
            )

        if t == "result":
            return CodingEvent(
                kind="done",
                text=obj.get("result", ""),
                raw=obj,
            )

        return None
