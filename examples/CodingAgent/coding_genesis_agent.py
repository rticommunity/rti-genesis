#!/usr/bin/env python3
"""
CodingGenesisAgent — Genesis agent that delegates coding tasks to
Claude Code or Codex via subprocess on subscription pricing.

No genesis_lib modifications required.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import argparse
import asyncio
import logging
import os
import sys

# Ensure genesis_lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.graph_monitoring import COMPONENT_TYPE, STATE, EDGE_TYPE

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
    # Request handling
    # ------------------------------------------------------------------

    async def _process_request(self, request):
        """Execute a coding task via subprocess."""
        message = request.get("message", "")
        conv_id = request.get("conversation_id")
        session_id = self._sessions.get(conv_id) if conv_id else None

        cmd = self._backend.build_command(message, session_id, self._working_dir)
        env = self._backend.build_env()

        logger.info("Spawning: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self._working_dir,
        )
        self._active_proc = proc

        try:
            events, result_text, new_session_id, timed_out = await read_events(
                proc, self._backend, self._timeout,
            )
        finally:
            if proc.returncode is None:
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

        # DDS InterfaceAgentReply: message, status, conversation_id
        return {
            "message": result_text,
            "status": status,
            "conversation_id": conv_id or "",
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
