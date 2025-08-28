#!/usr/bin/env python3
"""
MCP Test Runner Server (Prototype)

Exposes Genesis test runners as MCP tools so agents that cannot run DDS locally
can request tests from a preconfigured environment and get structured results.

Dependencies:
  pip install mcp jsonschema

Start:
  cd <repo-root>
  python tools/mcp_test_runner/server.py

Clients connect via MCP command transport to this process.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shlex
import sys
from typing import Any, Dict, List

LOG_DIR = pathlib.Path(__file__).resolve().parents[2] / "logs"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _redact_env(env: Dict[str, str]) -> Dict[str, str]:
    redacted = {}
    for k, v in env.items():
        if any(tok in k.upper() for tok in ("KEY", "TOKEN", "SECRET")):
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted


async def run_script(args: List[str], timeout: int = 900) -> Dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return {
            "status": "error",
            "exit_code": 124,
            "summary": f"Timeout after {timeout}s: {' '.join(map(shlex.quote, args))}",
            "output": "",
            "artifacts": _collect_artifacts(),
        }
    exit_code = proc.returncode
    status = "pass" if exit_code == 0 else "fail"
    return {
        "status": status,
        "exit_code": exit_code,
        "summary": f"{' '.join(args)} → {status}",
        "output": (out.decode("utf-8", errors="replace") if out else ""),
        "artifacts": _collect_artifacts(),
    }


def _collect_artifacts(limit: int = 50) -> List[str]:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted([p.name for p in LOG_DIR.glob("*.log")], reverse=True)
        return files[:limit]
    except Exception:
        return []


def _tail_file(path: pathlib.Path, max_lines: int = 200) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:])
    except Exception as e:
        return f"<error reading {path.name}: {e}>"


async def main() -> None:
    try:
        # Lazy import to avoid hard dependency if not used
        from mcp.server import Server
        from mcp.types import Tool, TextContent
    except Exception as e:
        print("ERROR: mcp package not available. Install with 'pip install mcp'", file=sys.stderr)
        raise

    server = Server("genesis-test-runner")

    @server.tool()
    async def env_info() -> TextContent:
        """Return environment information (DDS, Python, repo root)."""
        info = {
            "python": sys.version,
            "repo_root": str(REPO_ROOT),
            "nddshome": os.environ.get("NDDSHOME", "<unset>"),
            "rtiddsspy": str((pathlib.Path(os.environ.get("NDDSHOME", "")) / "bin" / "rtiddsspy")) if os.environ.get("NDDSHOME") else "<unknown>",
            "env": _redact_env({k: v for k, v in os.environ.items() if k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}),
        }
        return TextContent(type="text", text=json.dumps(info))

    @server.tool()
    async def run_triage_suite() -> TextContent:
        """Run the fail-fast triage suite and return a summary with artifacts."""
        res = await run_script(["bash", "run_scripts/run_triage_suite.sh"], timeout=1800)
        return TextContent(type="text", text=json.dumps(res))

    @server.tool()
    async def run_all_tests() -> TextContent:
        """Run the full test suite (long)."""
        res = await run_script(["bash", "run_scripts/run_all_tests.sh"], timeout=7200)
        return TextContent(type="text", text=json.dumps(res))

    SAFE_TESTS = {
        "viewer_contract": ["python", "run_scripts/test_viewer_contract.py"],
        "monitoring_graph": ["python", "run_scripts/test_monitoring_graph_state.py"],
        "monitoring_interface_pipeline": ["python", "run_scripts/test_monitoring_interface_agent_pipeline.py"],
        "math": ["bash", "run_scripts/run_math.sh"],
    }

    @server.tool()
    async def run_named_test(name: str) -> TextContent:
        """Run a whitelisted test by name (e.g., 'viewer_contract', 'math')."""
        cmd = SAFE_TESTS.get(name)
        if not cmd:
            return TextContent(type="text", text=json.dumps({"status": "error", "summary": f"unknown test: {name}"}))
        res = await run_script(cmd, timeout=900)
        return TextContent(type="text", text=json.dumps(res))

    @server.tool()
    async def list_logs() -> TextContent:
        """List recent log files under logs/."""
        return TextContent(type="text", text=json.dumps({"logs": _collect_artifacts()}))

    @server.tool()
    async def read_log(name: str, max_lines: int = 200) -> TextContent:
        """Tail a specific log file by name (under logs/)."""
        path = LOG_DIR / name
        return TextContent(type="text", text=_tail_file(path, max_lines=max_lines))

    await server.run_stdio_async()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

