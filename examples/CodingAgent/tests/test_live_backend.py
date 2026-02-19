#!/usr/bin/env python3
"""
Live backend tests — run real CLI subprocesses.

Skips if the CLI is not installed.
Covers spec: 14-end-to-end.txt (subprocess-level).
"""

import asyncio
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backends.claude_backend import ClaudeBackend
from backends.codex_backend import CodexBackend
from backends.stream_reader import read_events

failures = []
passed = 0


def check(name, condition, detail=""):
    global passed
    if condition:
        passed += 1
    else:
        msg = f"FAIL: {name}"
        if detail:
            msg += f" — {detail}"
        failures.append(msg)
        print(msg)


async def test_claude_live():
    """Run a real Claude Code subprocess and verify events."""
    print("\n--- Claude live backend test ---")

    if not shutil.which("claude"):
        print("SKIP: 'claude' CLI not installed")
        return

    cb = ClaudeBackend()
    cb.set_auth_mode("subscription")

    cmd = cb.build_command("Reply with only: GENESIS_TEST_OK")
    env = cb.build_env()

    print(f"Running: {' '.join(cmd)}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    events, text, sid, timed_out = await read_events(proc, cb, timeout=60.0)

    # Wait for process to finish
    if proc.returncode is None:
        await proc.wait()

    print(f"  Events: {len(events)}")
    print(f"  Text: {text[:100]!r}")
    print(f"  Session: {sid}")
    print(f"  Return code: {proc.returncode}")

    check("claude-live: has events", len(events) > 0)
    check("claude-live: has text", len(text) > 0)
    check("claude-live: not timed out", timed_out is False)
    # Session ID might not always be present depending on claude version
    # but text should contain something
    kinds = {e.kind for e in events}
    check("claude-live: has text event", "text" in kinds or "done" in kinds)


async def test_codex_live():
    """Run a real Codex subprocess and verify events."""
    print("\n--- Codex live backend test ---")

    if not shutil.which("codex"):
        print("SKIP: 'codex' CLI not installed")
        return

    xb = CodexBackend()
    xb.set_auth_mode("subscription")

    cmd = xb.build_command("Reply with only: GENESIS_CODEX_TEST_OK")
    env = xb.build_env()

    print(f"Running: {' '.join(cmd)}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    events, text, sid, timed_out = await read_events(proc, xb, timeout=60.0)

    if proc.returncode is None:
        await proc.wait()

    print(f"  Events: {len(events)}")
    print(f"  Text: {text[:100]!r}")
    print(f"  Session: {sid}")
    print(f"  Return code: {proc.returncode}")

    check("codex-live: has events", len(events) > 0)
    check("codex-live: has text", len(text) > 0)
    check("codex-live: not timed out", timed_out is False)


async def main():
    await test_claude_live()
    await test_codex_live()


asyncio.run(main())

print(f"\n{'='*60}")
total = passed + len(failures)
if total == 0:
    print("All backends skipped (no CLI installed)")
    sys.exit(0)

print(f"Results: {passed}/{total} passed, {len(failures)} failed")
if failures:
    print("\nFailures:")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("All tests passed!")
    sys.exit(0)
