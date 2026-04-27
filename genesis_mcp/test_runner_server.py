import asyncio
import json
import os
import shlex
import sys
import time
from typing import Dict, Any, Optional

# Try FastMCP first (newer API), fall back to Server.run_stdio if available
SERVER_NAME = "genesis-runner"
_decorator = None
_run_server = None
try:  # Preferred path
    from mcp.server.fastmcp import FastMCP  # type: ignore

    _mcp = FastMCP(SERVER_NAME)
    _decorator = _mcp.tool

    def _run_server() -> None:
        _mcp.run()

except Exception:
    try:
        from mcp.server import Server  # type: ignore

        _srv = Server(SERVER_NAME)
        if not hasattr(_srv, "run_stdio"):
            raise RuntimeError("MCP Server missing run_stdio; please upgrade 'mcp' package")
        if not hasattr(_srv, "tool"):
            raise RuntimeError("MCP Server missing tool decorator; please upgrade 'mcp' or install a newer SDK")
        _decorator = _srv.tool

        async def _run_server_async() -> None:
            await _srv.run_stdio()

        def _run_server() -> None:
            asyncio.run(_run_server_async())

    except Exception as e:  # pragma: no cover
        print(
            "ERROR: MCP SDK import failed or is too old.\n"
            "Try: source venv/bin/activate && pip install -U mcp\n"
            f"Details: {e}",
            file=sys.stderr,
        )
        sys.exit(2)


def repo_root() -> str:
    # genesis_mcp/test_runner_server.py -> .. -> repo root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_rtiddsspy() -> str:
    rti_bin = os.environ.get("RTI_BIN_DIR")
    if rti_bin and os.path.exists(os.path.join(rti_bin, "rtiddsspy")):
        return os.path.join(rti_bin, "rtiddsspy")
    nddshome = os.environ.get("NDDSHOME", "")
    candidate = os.path.join(nddshome, "bin", "rtiddsspy")
    return candidate if os.path.exists(candidate) else ""


async def _run_shell(cmd: str, timeout: int = 600, env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    start = time.time()
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env or os.environ.copy(),
        cwd=cwd or repo_root(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        code = proc.returncode
    except asyncio.TimeoutError:
        proc.kill()
        stdout, stderr = await proc.communicate()
        code = 124
    duration = time.time() - start
    return {
        "exit_code": code,
        "stdout": stdout.decode(errors="ignore"),
        "stderr": stderr.decode(errors="ignore"),
        "duration_sec": round(duration, 3),
    }


def _safe_tail(path: str, lines: int = 120) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.readlines()
        return "".join(data[-lines:])
    except Exception as e:  # pragma: no cover
        return f"(unable to read {path}: {e})"


@_decorator("preflight", description="Report Python version, NDDSHOME, rtiddsspy path, OPENAI_API_KEY presence")
async def preflight() -> str:
    python = sys.executable
    version = sys.version.split("\n")[0]
    ndds = os.environ.get("NDDSHOME", "unset")
    spy = _resolve_rtiddsspy() or "missing"
    openai = "SET" if os.environ.get("OPENAI_API_KEY") else "unset"
    return json.dumps(
        {
            "python": python,
            "version": version,
            "repo_root": repo_root(),
            "NDDSHOME": ndds,
            "rtiddsspy": spy,
            "OPENAI_API_KEY": openai,
        },
        indent=2,
    )


@_decorator("run_triage", description="Run triage suite and return exit code with last stdout/stderr")
async def run_triage(timeout_sec: int = 1200) -> str:
    cmd = "bash -lc './run_scripts/run_triage_suite.sh'"
    res = await _run_shell(cmd, timeout=timeout_sec, cwd=repo_root())
    return json.dumps(res, indent=2)


@_decorator("run_all_tests", description="Run full test suite and return exit code with last stdout/stderr")
async def run_all_tests(timeout_sec: int = 1800) -> str:
    cmd = "bash -lc './run_scripts/run_all_tests.sh'"
    res = await _run_shell(cmd, timeout=timeout_sec, cwd=repo_root())
    return json.dumps(res, indent=2)


@_decorator("run_active_test", description="Run a single test script from run_scripts/active by filename")
async def run_active_test(name: str, timeout_sec: int = 600) -> str:
    active_dir = os.path.join(repo_root(), "run_scripts", "active")
    script_path = os.path.normpath(os.path.join(active_dir, name))
    if not script_path.startswith(active_dir) or not os.path.exists(script_path):
        return f"ERROR: Not found or invalid: {name}"
    # Choose runner based on extension
    if script_path.endswith(".py"):
        cmd = f"bash -lc 'PYTHONPATH=$PYTHONPATH:{shlex.quote(repo_root())} python {shlex.quote(script_path)}'"
    else:
        cmd = f"bash -lc 'bash {shlex.quote(script_path)}'"
    res = await _run_shell(cmd, timeout=timeout_sec, cwd=repo_root())
    return json.dumps(res, indent=2)


@_decorator("tail_log", description="Tail a file under ./logs/ with optional line count")
async def tail_log(filename: str, lines: int = 200) -> str:
    logs_dir = os.path.join(repo_root(), "logs")
    path = os.path.normpath(os.path.join(logs_dir, filename))
    if not path.startswith(logs_dir) or not os.path.exists(path):
        return f"ERROR: Log not found: {filename}"
    return _safe_tail(path, lines)


@_decorator("sweep_dds", description="Run an rtiddsspy sweep for core topics (-printSample) and return a short tail")
async def sweep_dds(duration_sec: int = 6) -> str:
    spy = _resolve_rtiddsspy()
    if not spy:
        return "ERROR: rtiddsspy not found (set NDDSHOME or RTI_BIN_DIR)"
    topics = [
        "FunctionCapability",
        "CalculatorServiceRequest",
        "CalculatorServiceReply",
        "MonitoringEvent",
        "ChainEvent",
    ]
    qos_args = ""
    spy_qos = os.path.join(repo_root(), "spy_transient.xml")
    if os.path.exists(spy_qos):
        qos_args = f"-qosFile {shlex.quote(spy_qos)} -qosProfile SpyLib::TransientReliable"
    cmd = (
        f"bash -lc '{shlex.quote(spy)} -printSample {qos_args} "
        + " ".join(f"-topic {shlex.quote(t)}" for t in topics)
        + "'"
    )
    res = await _run_shell(cmd, timeout=duration_sec, cwd=repo_root())
    return json.dumps(res, indent=2)


if __name__ == "__main__":
    _run_server()
