"""
CodexBackend — OpenAI Codex CLI subprocess bridge.

Translates 'codex exec --json' JSONL event streams into normalised
CodingEvent objects.

Codex CLI event types (observed from codex-cli 0.101.0):
  thread.started          → init
  item.completed/agent_message    → text
  item.completed/command_execution (completed) → tool_result
  item.completed/command_execution (in_progress via item.started) → tool_start
  item.completed/tool_call        → tool_start  (legacy/alternate path)
  item.completed/tool_output      → tool_result (legacy/alternate path)
  item.completed/reasoning        → skipped (internal chain-of-thought)
  item.started                    → tool_start (for command_execution)
  turn.completed                  → done
  turn.failed                     → error
  error                           → error
"""

import json
import os
from typing import List, Optional

from .base import CodingBackend
from .events import CodingEvent


class CodexBackend(CodingBackend):

    def __init__(self, model: str = "gpt-5.2-codex"):
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
                "-c", 'approval_policy="never"',
            ]
        return [
            "codex", "exec",
            "-m", self._model, "--json",
            "-c", 'approval_policy="never"',
            prompt,
        ]

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

        # -- Init --
        if t == "thread.started":
            return CodingEvent(
                kind="init",
                session_id=obj.get("thread_id", ""),
                raw=obj,
            )

        # -- Text response --
        if t == "item.completed" and item_type == "agent_message":
            return CodingEvent(
                kind="text",
                text=item.get("text", ""),
                raw=obj,
            )

        # -- Command execution (Codex's primary tool mechanism) --
        # item.started → tool_start with the command
        if t == "item.started" and item_type == "command_execution":
            return CodingEvent(
                kind="tool_start",
                tool_name="shell",
                tool_input={"cmd": item.get("command", "")},
                raw=obj,
            )

        # item.completed → tool_result with output and exit code
        if t == "item.completed" and item_type == "command_execution":
            return CodingEvent(
                kind="tool_result",
                tool_output=item.get("aggregated_output", ""),
                raw={"exit_code": item.get("exit_code"), **obj},
            )

        # -- Legacy/alternate tool_call path --
        if t == "item.completed" and item_type == "tool_call":
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

        # -- Done --
        if t == "turn.completed":
            return CodingEvent(
                kind="done",
                raw=obj.get("usage", {}),
            )

        # -- Errors --
        if t == "turn.failed":
            error = obj.get("error", {})
            return CodingEvent(
                kind="error",
                text=error.get("message", "Turn failed"),
                raw=obj,
            )

        if t == "error":
            return CodingEvent(
                kind="error",
                text=obj.get("message", "Unknown error"),
                raw=obj,
            )

        # reasoning, turn.started, and other unknown events are skipped
        return None
