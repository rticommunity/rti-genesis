#!/usr/bin/env python3
"""
Mock subprocess tests for read_events helper — no DDS required.

Tests the stream-reading logic in isolation using mock AsyncProcess
objects that simulate Claude Code / Codex stdout streams.

Covers specs: 08-request-processing.txt, 09-multi-turn-sessions.txt,
              10-error-handling.txt (parse / timeout / empty).
"""

import asyncio
import json
import os
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


# ------------------------------------------------------------------
# Mock async process
# ------------------------------------------------------------------

class MockAsyncStdout:
    """Simulates an async line iterator over subprocess stdout."""

    def __init__(self, lines):
        self._lines = [
            (l.encode("utf-8") + b"\n") if isinstance(l, str) else l
            for l in lines
        ]
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._lines):
            raise StopAsyncIteration
        line = self._lines[self._index]
        self._index += 1
        return line


class MockProcess:
    """Minimal mock of asyncio.subprocess.Process."""

    def __init__(self, stdout_lines):
        self.stdout = MockAsyncStdout(stdout_lines)
        self.returncode = 0


class HangingStdout:
    """Simulates a process that never finishes producing output."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(100)  # effectively hang
        raise StopAsyncIteration


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

async def run_tests():
    global passed

    cb = ClaudeBackend()
    xb = CodexBackend()

    # ---- Text accumulation: 3 events concatenated ----
    print("--- Text accumulation ---")
    lines = [
        json.dumps({"type": "assistant", "subtype": "text", "text": "Hello "}),
        json.dumps({"type": "assistant", "subtype": "text", "text": "world"}),
        json.dumps({"type": "assistant", "subtype": "text", "text": "!"}),
        json.dumps({"type": "result", "subtype": "success", "result": ""}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, cb, timeout=10.0)
    check("accumulate-3: text", text == "Hello world!", repr(text))
    check("accumulate-3: events count", len(events) == 4)
    check("accumulate-3: not timed out", to is False)

    # ---- Done override: done with text replaces accumulated ----
    print("\n--- Done override ---")
    lines = [
        json.dumps({"type": "assistant", "subtype": "text", "text": "partial output"}),
        json.dumps({"type": "result", "subtype": "success", "result": "The final answer is 42"}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, cb, timeout=10.0)
    check("done-override: text", text == "The final answer is 42", repr(text))

    # ---- Done without text: preserves accumulated ----
    print("\n--- Done without text (codex) ---")
    lines = [
        json.dumps({"type": "item.completed", "item": {"id": "0", "type": "agent_message", "text": "GENESIS_CODEX_TEST_OK"}}),
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, xb, timeout=10.0)
    check("done-no-text: text preserved", text == "GENESIS_CODEX_TEST_OK", repr(text))

    # ---- Tool call counting ----
    print("\n--- Tool call counting ---")
    lines = [
        json.dumps({"type": "assistant", "subtype": "tool_use", "tool": {"name": "Read", "input": {}}}),
        json.dumps({"type": "tool", "subtype": "result", "content": "file contents"}),
        json.dumps({"type": "assistant", "subtype": "tool_use", "tool": {"name": "Edit", "input": {}}}),
        json.dumps({"type": "tool", "subtype": "result", "content": "edited"}),
        json.dumps({"type": "assistant", "subtype": "tool_use", "tool": {"name": "Bash", "input": {}}}),
        json.dumps({"type": "tool", "subtype": "result", "content": "ok"}),
        json.dumps({"type": "result", "subtype": "success", "result": "Done"}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, cb, timeout=10.0)
    tool_count = sum(1 for e in events if e.kind == "tool_start")
    check("tool-count: 3", tool_count == 3)

    # ---- Zero tool calls ----
    lines = [
        json.dumps({"type": "assistant", "subtype": "text", "text": "Just text"}),
        json.dumps({"type": "result", "subtype": "success", "result": "Just text"}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, cb, timeout=10.0)
    tool_count = sum(1 for e in events if e.kind == "tool_start")
    check("tool-count-zero: 0", tool_count == 0)

    # ---- Session ID extraction (Claude) ----
    print("\n--- Session ID extraction ---")
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "sess-new-001"}),
        json.dumps({"type": "assistant", "subtype": "text", "text": "hi"}),
        json.dumps({"type": "result", "subtype": "success", "result": "hi"}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, cb, timeout=10.0)
    check("session-id-claude: value", sid == "sess-new-001")

    # ---- Session ID extraction (Codex) ----
    lines = [
        json.dumps({"type": "thread.started", "thread_id": "019c7199-abcd"}),
        json.dumps({"type": "item.completed", "item": {"id": "0", "type": "agent_message", "text": "ok"}}),
        json.dumps({"type": "turn.completed", "usage": {}}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, xb, timeout=10.0)
    check("session-id-codex: value", sid == "019c7199-abcd")

    # ---- Malformed JSON resilience ----
    print("\n--- Malformed JSON resilience ---")
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
        "not json at all",
        "{broken json",
        json.dumps({"type": "assistant", "subtype": "text", "text": "after noise"}),
        "",
        json.dumps({"type": "result", "subtype": "success", "result": "after noise"}),
    ]
    proc = MockProcess(lines)
    events, text, sid, to = await read_events(proc, cb, timeout=10.0)
    check("malformed-resilience: session_id", sid == "s1")
    check("malformed-resilience: text", text == "after noise", repr(text))
    # Only 3 valid events: init, text, done
    check("malformed-resilience: event count", len(events) == 3, str(len(events)))

    # ---- Timeout handling ----
    print("\n--- Timeout handling ---")
    proc = MockProcess([])
    proc.stdout = HangingStdout()
    events, text, sid, to = await read_events(proc, cb, timeout=0.5)
    check("timeout: message contains timed out", "timed out" in text.lower(), repr(text))
    check("timeout: timed_out flag", to is True)

    # ---- Empty response ----
    print("\n--- Empty response ---")
    proc = MockProcess([])
    events, text, sid, to = await read_events(proc, cb, timeout=5.0)
    check("empty: text empty", text == "")
    check("empty: no session_id", sid is None)
    check("empty: no events", len(events) == 0)
    check("empty: not timed out", to is False)


# ------------------------------------------------------------------
# Conversation history tests (no DDS required)
# ------------------------------------------------------------------

def run_history_tests():
    """Test _build_prompt_with_history logic using a lightweight mock."""
    global passed

    print("\n--- Conversation history (Genesis memory) ---")

    from genesis_lib.memory import SimpleMemoryAdapter

    # Create a minimal object that mimics the relevant CodingGenesisAgent attrs
    class FakeAgent:
        def __init__(self, backend_name):
            self.memory = SimpleMemoryAdapter()
            self._sessions = {}
            self._backend = type("B", (), {"name": backend_name})()

    # Import the method we want to test
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from coding_genesis_agent import CodingGenesisAgent

    # --- Test 1: No history returns raw message ---
    agent = FakeAgent("claude")
    result = CodingGenesisAgent._build_prompt_with_history(agent, "hello", None)
    check("history: no history returns raw message", result == "hello")

    # --- Test 2: History is prepended for Claude ---
    agent = FakeAgent("claude")
    agent.memory.store("Write a snake game", metadata={"role": "user"})
    agent.memory.store("I created snake.py", metadata={"role": "assistant"})
    result = CodingGenesisAgent._build_prompt_with_history(agent, "Add obstacles", "conv1")
    check("history: contains prior user msg", "[User]: Write a snake game" in result)
    check("history: contains prior assistant msg", "[Assistant]: I created snake.py" in result)
    check("history: contains current request", "Add obstacles" in result)
    check("history: current request at end", result.endswith("Add obstacles"))

    # --- Test 3: Codex with active session skips history ---
    agent = FakeAgent("codex")
    agent._sessions["conv1"] = "sess-123"
    agent.memory.store("Prior message", metadata={"role": "user"})
    result = CodingGenesisAgent._build_prompt_with_history(agent, "Follow up", "conv1")
    check("history: codex with session returns raw", result == "Follow up")

    # --- Test 4: Codex without session includes history ---
    agent = FakeAgent("codex")
    agent.memory.store("First request", metadata={"role": "user"})
    agent.memory.store("First response", metadata={"role": "assistant"})
    result = CodingGenesisAgent._build_prompt_with_history(agent, "Second request", "conv2")
    check("history: codex no session includes history", "[User]: First request" in result)
    check("history: codex no session has current", "Second request" in result)

    # --- Test 5: Long assistant responses are truncated ---
    agent = FakeAgent("claude")
    long_text = "x" * 5000
    agent.memory.store("question", metadata={"role": "user"})
    agent.memory.store(long_text, metadata={"role": "assistant"})
    result = CodingGenesisAgent._build_prompt_with_history(agent, "next", "c1")
    check("history: long response truncated", "... (truncated)" in result)
    check("history: truncated to ~2000 chars", len(result) < 3000)

    # --- Test 6: Multiple turns build up ---
    agent = FakeAgent("claude")
    for i in range(5):
        agent.memory.store(f"Question {i}", metadata={"role": "user"})
        agent.memory.store(f"Answer {i}", metadata={"role": "assistant"})
    result = CodingGenesisAgent._build_prompt_with_history(agent, "Final question", "c1")
    for i in range(5):
        check(f"history: multi-turn has question {i}", f"Question {i}" in result)
        check(f"history: multi-turn has answer {i}", f"Answer {i}" in result)


run_history_tests()

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

asyncio.run(run_tests())

print(f"\n{'='*60}")
total = passed + len(failures)
print(f"Results: {passed}/{total} passed, {len(failures)} failed")
if failures:
    print("\nFailures:")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("All tests passed!")
    sys.exit(0)
