#!/usr/bin/env python3
"""
CodingGenesisAgent — Genesis agent that delegates coding tasks to
Claude Code or Codex via subprocess on subscription pricing.

No genesis_lib modifications required.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import uuid

# Ensure genesis_lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.graph_monitoring import COMPONENT_TYPE, STATE, EDGE_TYPE
from genesis_lib.stream_publisher import StreamPublisher

# Local backend imports
sys.path.insert(0, os.path.dirname(__file__))
from backends import ClaudeBackend, CodexBackend, CodingBackend
from backends.auth import probe_auth
from backends.stream_reader import read_events

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Agent
# ------------------------------------------------------------------

class CodingGenesisAgent(MonitoredAgent):
    """Genesis agent that delegates work to Claude Code or Codex."""

    def __init__(
        self,
        backend="claude",
        agent_name="CodingAgent",
        base_service_name="CodingAgent",
        working_dir=None,
        timeout=300.0,
        domain_id=0,
        enable_agent_communication=True,
        **kwargs,
    ):
        # --- Store backend config BEFORE super().__init__() ---
        # so get_agent_capabilities() works when called during parent init.
        if backend == "claude":
            self._backend = ClaudeBackend()
        elif backend == "codex":
            self._backend = CodexBackend()
        else:
            raise ValueError(f"Unknown backend {backend!r}; use 'claude' or 'codex'")

        self._backend_name = backend
        self._working_dir = working_dir
        self._timeout = timeout
        self._sessions = {}       # conversation_id -> session_id
        self._active_proc = None  # currently running subprocess

        description = f"Coding agent powered by {backend} harness (subscription)"

        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_type="SPECIALIZED_AGENT",
            description=description,
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            **kwargs,
        )

        # --- Stream publisher for real-time event delivery ---
        self._stream_pub = StreamPublisher(self.app.participant)

        # --- Ensure working directory is a git repo (Codex requires it) ---
        if self._working_dir and backend == "codex":
            git_dir = os.path.join(self._working_dir, ".git")
            if not os.path.isdir(git_dir):
                logger.info("Initializing git repo in %s (required by Codex)", self._working_dir)
                subprocess.run(
                    ["git", "init"], cwd=self._working_dir,
                    capture_output=True, check=True,
                )

        # --- Auth probe (synchronous subprocess.run) ---
        auth_mode = probe_auth(self._backend, timeout=30.0)
        self._backend.set_auth_mode(auth_mode)
        logger.info(
            f"CodingGenesisAgent[{backend}] auth_mode={auth_mode}"
        )

        # --- Advertise coding capabilities ---
        self.set_agent_capabilities(
            supported_tasks=["coding", "debugging", "code-review", "refactoring"],
            additional_capabilities={
                "specializations": [f"{backend}-code", "software-engineering"],
                "capabilities": [
                    "code-generation", "file-editing", "shell-execution",
                ],
                "classification_tags": [
                    "code", "programming", "software", "debug", "refactor",
                ],
                "model_info": {
                    "backend": backend,
                    "harness": True,
                    "subscription": auth_mode == "subscription",
                },
            },
        )

    # ------------------------------------------------------------------
    # Conversation history (Genesis memory architecture)
    # ------------------------------------------------------------------

    def _build_prompt_with_history(self, message, conv_id):
        """Build a prompt that includes conversation history from Genesis memory.

        For backends without native session support (Claude), the conversation
        history is prepended to the prompt so the model has context from prior
        turns.  For backends with native sessions (Codex with active session_id),
        history is managed by the session and the raw message is returned.

        Uses self.memory (SimpleMemoryAdapter by default) which is inherited from
        GenesisAgent.  When context grows too large, Genesis memory plugins
        (compaction, summary, summary-plus-last, etc.) can be swapped in via
        the MemoryAdapter interface.
        """
        # Codex with an active session already has context — return raw message
        session_id = self._sessions.get(conv_id) if conv_id else None
        if session_id and self._backend.name == "codex":
            return message

        # Retrieve conversation history from Genesis memory
        memory_items = self.memory.retrieve(k=50)
        if not memory_items:
            return message

        # Build conversation transcript
        history_lines = []
        for entry in memory_items:
            item = entry.get("item", "")
            meta = entry.get("metadata") or {}
            role = meta.get("role", "user")
            if role == "user":
                history_lines.append(f"[User]: {item}")
            elif role == "assistant":
                # Truncate long assistant responses to keep prompt manageable
                text = item if len(item) <= 2000 else item[:2000] + "... (truncated)"
                history_lines.append(f"[Assistant]: {text}")

        history_block = "\n\n".join(history_lines)

        return (
            f"## Conversation History\n"
            f"Below is our conversation so far. Use this context to understand "
            f"follow-up requests.\n\n"
            f"{history_block}\n\n"
            f"## Current Request\n"
            f"{message}"
        )

    # ------------------------------------------------------------------
    # LLM abstract method stubs (not used — we delegate to subprocess)
    # ------------------------------------------------------------------

    async def _call_llm(self, messages, tools=None, tool_choice="auto"):
        raise NotImplementedError("CodingGenesisAgent delegates to subprocess")

    def _format_messages(self, user_message, system_prompt, memory_items):
        raise NotImplementedError("CodingGenesisAgent delegates to subprocess")

    def _extract_tool_calls(self, response):
        return None

    def _extract_text_response(self, response):
        return ""

    def _create_assistant_message(self, response):
        return {}

    async def _get_tool_schemas(self):
        return []

    def _get_tool_choice(self):
        return "none"

    # ------------------------------------------------------------------
    # Override get_agent_capabilities for the parent init call
    # ------------------------------------------------------------------

    def get_agent_capabilities(self):
        """Return hardcoded coding capabilities.

        Called during super().__init__() before set_agent_capabilities(),
        so we return a sensible default here.
        """
        backend = getattr(self, "_backend_name", "unknown")
        return {
            "agent_type": "specialized",
            "specializations": [f"{backend}-code", "software-engineering"],
            "capabilities": [
                "code-generation", "file-editing", "shell-execution",
            ],
            "classification_tags": [
                "code", "programming", "software", "debug", "refactor",
            ],
            "model_info": {
                "backend": backend,
                "harness": True,
                "subscription": True,
            },
            "default_capable": False,
            "performance_metrics": None,
        }

    # ------------------------------------------------------------------
    # Request handling (overrides the full LLM pipeline)
    # ------------------------------------------------------------------

    async def process_request(self, request):
        """Override process_request to bypass the LLM pipeline entirely.

        MonitoredAgent.process_request() → GenesisAgent.process_request()
        calls _format_messages → _call_llm etc. which we don't use.
        We override at this level and handle monitoring ourselves.
        """
        logger.debug("CodingGenesisAgent.process_request called")

        # Publish BUSY state
        try:
            self.graph.publish_node(
                component_id=self.app.agent_id,
                component_type=COMPONENT_TYPE["AGENT_SPECIALIZED"],
                state=STATE["BUSY"],
                attrs={
                    "agent_type": self.agent_type,
                    "service": self.base_service_name,
                    "agent_id": self.app.agent_id,
                    "reason": "Processing coding request",
                },
            )
        except Exception:
            pass

        try:
            result = await self._do_coding_request(request)
        except Exception as exc:
            logger.error("Error in _do_coding_request: %s", exc, exc_info=True)
            try:
                self.graph.publish_node(
                    component_id=self.app.agent_id,
                    component_type=COMPONENT_TYPE["AGENT_SPECIALIZED"],
                    state=STATE["DEGRADED"],
                    attrs={"reason": str(exc)[:500]},
                )
            except Exception:
                pass
            result = {
                "message": f"Error: {exc}",
                "status": 1,
                "conversation_id": request.get("conversation_id", ""),
            }

        # Publish READY state
        try:
            self.graph.publish_node(
                component_id=self.app.agent_id,
                component_type=COMPONENT_TYPE["AGENT_SPECIALIZED"],
                state=STATE["READY"],
                attrs={
                    "agent_type": self.agent_type,
                    "service": self.base_service_name,
                    "agent_id": self.app.agent_id,
                    "reason": f"Request complete: {str(result)[:200]}",
                },
            )
        except Exception:
            pass

        return result

    async def _do_coding_request(self, request):
        """Execute a coding task via subprocess with real-time stream publishing."""
        message = request.get("message", "")
        conv_id = request.get("conversation_id")
        # Use request_id from caller (web interface) or generate one
        request_id = request.get("request_id") or str(uuid.uuid4())
        session_id = self._sessions.get(conv_id) if conv_id else None

        # Build prompt with conversation history from Genesis memory
        prompt = self._build_prompt_with_history(message, conv_id)

        cmd = self._backend.build_command(prompt, session_id, self._working_dir)
        env = self._backend.build_env()

        logger.info("Spawning: %s", " ".join(cmd))

        # Pipe stdin so we can send the prompt for session resume commands
        # (Codex 'exec resume' reads the follow-up prompt from stdin)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self._working_dir,
        )
        self._active_proc = proc

        # Codex 'exec resume' reads the follow-up prompt from stdin;
        # Claude always uses -p on the command line, so stdin is not needed.
        if session_id and message and self._backend.name == "codex":
            proc.stdin.write(message.encode("utf-8"))
            proc.stdin.write(b"\n")
            await proc.stdin.drain()
        proc.stdin.close()

        # Read events inline so we can publish each one to the DDS stream
        events = []
        result_text = ""
        new_session_id = None
        timed_out = False

        async def _stream():
            nonlocal result_text, new_session_id
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                logger.debug("stdout: %s", line[:500])
                try:
                    event = self._backend.parse_line(line)
                except Exception:
                    continue
                if event is None:
                    continue

                events.append(event)

                # Accumulate text (same logic as read_events)
                if event.kind == "init" and event.session_id:
                    new_session_id = event.session_id
                elif event.kind == "text":
                    result_text += event.text
                elif event.kind == "done" and event.text:
                    result_text = event.text
                elif event.kind == "error":
                    result_text = f"Error: {event.text}"

                # Publish to DDS stream in real-time
                try:
                    content = ""
                    metadata = {}
                    if event.kind == "init":
                        content = event.session_id or ""
                    elif event.kind == "text":
                        content = event.text
                    elif event.kind == "tool_start":
                        content = event.tool_name
                        metadata = {"tool_input": event.tool_input}
                    elif event.kind == "tool_result":
                        content = event.tool_output
                        metadata = {"tool_name": event.tool_name}
                    elif event.kind == "done":
                        content = event.text or ""
                    elif event.kind == "error":
                        content = event.text
                    self._stream_pub.publish(
                        request_id=request_id,
                        chunk_type=event.kind,
                        content=content,
                        metadata=metadata,
                    )
                except Exception as exc:
                    logger.debug("Stream publish failed: %s", exc)

        try:
            try:
                await asyncio.wait_for(_stream(), timeout=self._timeout)
            except asyncio.TimeoutError:
                timed_out = True
                result_text = f"Request timed out after {self._timeout}s"
                try:
                    self._stream_pub.publish(
                        request_id=request_id,
                        chunk_type="error",
                        content=result_text,
                    )
                except Exception:
                    pass
        finally:
            if proc.returncode is None:
                # Let the process exit naturally (release session locks, etc.)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
            self._active_proc = None

        # Log subprocess result for debugging
        stderr_bytes = b""
        try:
            stderr_bytes = await asyncio.wait_for(proc.stderr.read(), timeout=5.0)
        except Exception:
            pass
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        logger.info(
            "Subprocess exit=%s events=%d result_len=%d",
            proc.returncode, len(events), len(result_text),
        )
        if stderr_text:
            logger.warning("Subprocess stderr: %s", stderr_text[:2000])

        # Publish graph edges for each tool the harness used
        for event in events:
            if getattr(event, "kind", None) == "tool_start":
                try:
                    self.graph.publish_edge(
                        source_id=self.app.agent_id,
                        target_id=f"{self._backend.name}:{event.tool_name}",
                        edge_type=EDGE_TYPE["SERVICE_TO_FUNCTION"],
                        attrs={
                            "tool": event.tool_name,
                            "backend": self._backend.name,
                        },
                        component_type=COMPONENT_TYPE["AGENT_SPECIALIZED"],
                    )
                except Exception:
                    pass  # monitoring must never crash the agent

        # Store session mapping
        if new_session_id is None:
            new_session_id = session_id
        if conv_id and new_session_id:
            self._sessions[conv_id] = new_session_id

        status = 1 if timed_out else 0
        tool_calls = sum(
            1 for e in events if getattr(e, "kind", None) == "tool_start"
        )

        logger.info(
            "Request complete: backend=%s session=%s tools=%d timed_out=%s",
            self._backend.name,
            new_session_id or "",
            tool_calls,
            timed_out,
        )

        # Store conversation turns in Genesis memory for multi-turn context.
        # Uses self.memory (SimpleMemoryAdapter) inherited from GenesisAgent.
        # Future memory plugins (compaction, summary) swap in via MemoryAdapter.
        try:
            self.memory.store(message, metadata={"role": "user", "conversation_id": conv_id or ""})
            if result_text and not timed_out:
                self.memory.store(result_text, metadata={"role": "assistant", "conversation_id": conv_id or ""})
        except Exception as exc:
            logger.debug("Memory store failed: %s", exc)

        return {
            "message": result_text,
            "status": status,
            "conversation_id": conv_id or "",
            "request_id": request_id,
        }

    # ------------------------------------------------------------------
    # Agent-to-agent communication
    # ------------------------------------------------------------------

    async def process_agent_request(self, request):
        """Handle requests from other agents via DDS RPC."""
        return await self.process_request(request)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self):
        """Terminate active subprocess, then close DDS resources."""
        if self._active_proc and self._active_proc.returncode is None:
            self._active_proc.terminate()
            try:
                await asyncio.wait_for(self._active_proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._active_proc.kill()
                await self._active_proc.wait()
        self._stream_pub.close()
        await super().close()


# ------------------------------------------------------------------
# CLI entrypoint
# ------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="CodingGenesisAgent")
    parser.add_argument(
        "--backend", choices=["claude", "codex"], default="claude",
        help="Coding harness backend (default: claude)",
    )
    parser.add_argument(
        "--working-dir", default=None,
        help="Working directory for the harness subprocess",
    )
    parser.add_argument(
        "--timeout", type=float, default=300.0,
        help="Subprocess timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--agent-name", default=None,
        help="Agent name (default: CodingAgent-<backend>)",
    )
    args = parser.parse_args()

    agent_name = args.agent_name or f"CodingAgent-{args.backend}"

    agent = CodingGenesisAgent(
        backend=args.backend,
        agent_name=agent_name,
        working_dir=args.working_dir,
        timeout=args.timeout,
    )

    try:
        print(f"CodingGenesisAgent [{args.backend}] running as '{agent_name}'")
        print("Press Ctrl+C to exit")
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print(f"\nShutting down {agent_name}...")
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
