#!/usr/bin/env python3
"""
Unit tests for CodingEvent, backend parsers, command builders, and env sanitization.

Covers specs: 02, 03, 04, 05, 06, 13.
Direct Python execution (no pytest).
"""

import json
import os
import sys

# Ensure the CodingAgent package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backends.events import CodingEvent, VALID_KINDS
from backends.base import CodingBackend
from backends.claude_backend import ClaudeBackend
from backends.codex_backend import CodexBackend

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


# ====================================================================
# Spec 06: CodingEvent dataclass
# ====================================================================

print("--- CodingEvent dataclass ---")

# Defaults
e = CodingEvent(kind="text", text="hello")
check("event-defaults: kind", e.kind == "text")
check("event-defaults: text", e.text == "hello")
check("event-defaults: session_id", e.session_id == "")
check("event-defaults: tool_name", e.tool_name == "")
check("event-defaults: tool_input", e.tool_input == {})
check("event-defaults: tool_output", e.tool_output == "")
check("event-defaults: raw", e.raw == {})

# Valid kinds
for kind in VALID_KINDS:
    e = CodingEvent(kind=kind)
    check(f"event-valid-kind-{kind}", e.kind == kind)

# Invalid kind
try:
    CodingEvent(kind="invalid_kind")
    check("event-invalid-kind", False, "Should have raised ValueError")
except ValueError as ex:
    check("event-invalid-kind", "Invalid CodingEvent kind" in str(ex))

# ====================================================================
# Spec 04: Claude backend parsing
# ====================================================================

print("\n--- Claude backend parsing ---")
cb = ClaudeBackend()

# system/init
ev = cb.parse_line('{"type":"system","subtype":"init","session_id":"sess-abc-123"}')
check("claude-init: kind", ev.kind == "init")
check("claude-init: session_id", ev.session_id == "sess-abc-123")

# assistant/text
ev = cb.parse_line('{"type":"assistant","subtype":"text","text":"I will help you refactor"}')
check("claude-text: kind", ev.kind == "text")
check("claude-text: text", ev.text == "I will help you refactor")

# assistant/text empty
ev = cb.parse_line('{"type":"assistant","subtype":"text","text":""}')
check("claude-text-empty: kind", ev.kind == "text")
check("claude-text-empty: text", ev.text == "")

# assistant/tool_use
line = json.dumps({
    "type": "assistant", "subtype": "tool_use",
    "tool": {"name": "Write", "input": {"file_path": "/tmp/hello.py", "content": "print(42)"}}
})
ev = cb.parse_line(line)
check("claude-tool_use: kind", ev.kind == "tool_start")
check("claude-tool_use: tool_name", ev.tool_name == "Write")
check("claude-tool_use: tool_input file_path", ev.tool_input.get("file_path") == "/tmp/hello.py")

# tool/result
ev = cb.parse_line('{"type":"tool","subtype":"result","tool_use_id":"tu-001","content":"File written successfully"}')
check("claude-tool_result: kind", ev.kind == "tool_result")
check("claude-tool_result: tool_output", ev.tool_output == "File written successfully")

# result
ev = cb.parse_line('{"type":"result","subtype":"success","result":"The script has been created at /tmp/hello.py"}')
check("claude-done: kind", ev.kind == "done")
check("claude-done: text", ev.text == "The script has been created at /tmp/hello.py")

# Unknown event type
ev = cb.parse_line('{"type":"progress","subtype":"thinking","thinking":"..."}')
check("claude-unknown: None", ev is None)

# Empty line
ev = cb.parse_line("")
check("claude-empty: None", ev is None)

# Malformed JSON
ev = cb.parse_line("this is not json")
check("claude-malformed: None", ev is None)

# ====================================================================
# Spec 05: Codex backend parsing
# ====================================================================

print("\n--- Codex backend parsing ---")
xb = CodexBackend()

# thread.started
ev = xb.parse_line('{"type":"thread.started","thread_id":"019c7199-a895-74f2-a004-3b2efce37bc3"}')
check("codex-init: kind", ev.kind == "init")
check("codex-init: session_id", ev.session_id == "019c7199-a895-74f2-a004-3b2efce37bc3")

# agent_message
ev = xb.parse_line('{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"GENESIS_CODEX_TEST_OK"}}')
check("codex-text: kind", ev.kind == "text")
check("codex-text: text", ev.text == "GENESIS_CODEX_TEST_OK")

# agent_message multiline
ev = xb.parse_line('{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Line 1\\nLine 2\\nLine 3"}}')
check("codex-text-multiline: Line1", "Line 1" in ev.text)
check("codex-text-multiline: Line3", "Line 3" in ev.text)

# tool_call
line = json.dumps({
    "type": "item.completed",
    "item": {"id": "item_1", "type": "tool_call", "name": "shell", "arguments": '{"cmd":"ls -la"}'}
})
ev = xb.parse_line(line)
check("codex-tool_call: kind", ev.kind == "tool_start")
check("codex-tool_call: tool_name", ev.tool_name == "shell")
check("codex-tool_call: tool_input cmd", ev.tool_input.get("cmd") == "ls -la")

# tool_call with malformed arguments
line = json.dumps({
    "type": "item.completed",
    "item": {"id": "item_1", "type": "tool_call", "name": "shell", "arguments": "not valid json"}
})
try:
    ev = xb.parse_line(line)
    check("codex-tool_call-malformed: no exception", True)
    check("codex-tool_call-malformed: kind", ev.kind == "tool_start")
    check("codex-tool_call-malformed: _raw fallback", "_raw" in ev.tool_input)
except Exception as ex:
    check("codex-tool_call-malformed: no exception", False, str(ex))

# tool_output
line = json.dumps({
    "type": "item.completed",
    "item": {"id": "item_2", "type": "tool_output", "output": "total 42\ndrwxr-xr-x  5 user staff 160 Jan  1 00:00 ."}
})
ev = xb.parse_line(line)
check("codex-tool_output: kind", ev.kind == "tool_result")
check("codex-tool_output: content", "total 42" in ev.tool_output)

# turn.completed
ev = xb.parse_line('{"type":"turn.completed","usage":{"input_tokens":11161,"cached_input_tokens":6912,"output_tokens":24}}')
check("codex-done: kind", ev.kind == "done")
check("codex-done: raw input_tokens", ev.raw.get("input_tokens") == 11161)
check("codex-done: raw output_tokens", ev.raw.get("output_tokens") == 24)

# turn.started is skipped
ev = xb.parse_line('{"type":"turn.started"}')
check("codex-turn_started: None", ev is None)

# Empty / malformed
check("codex-empty: None", xb.parse_line("") is None)
check("codex-malformed: None", xb.parse_line("not json at all") is None)

# ====================================================================
# Spec 03: Command building — Claude
# ====================================================================

print("\n--- Claude command building ---")
cb = ClaudeBackend()

cmd = cb.build_command("Write a hello world script")
check("claude-cmd-basic: -p", "-p" in cmd)
check("claude-cmd-basic: prompt", "Write a hello world script" in cmd)
check("claude-cmd-basic: stream-json", "stream-json" in cmd)
check("claude-cmd-basic: --verbose", "--verbose" in cmd)
check("claude-cmd-basic: --permission-mode", "--permission-mode" in cmd)
check("claude-cmd-basic: bypassPermissions", "bypassPermissions" in cmd)

cmd = cb.build_command("Continue the refactor", session_id="sess-abc-123")
check("claude-cmd-session: --session-id", "--session-id" in cmd)
check("claude-cmd-session: value", "sess-abc-123" in cmd)
check("claude-cmd-session: -p", "-p" in cmd)
check("claude-cmd-session: --output-format", "--output-format" in cmd)
check("claude-cmd-session: --verbose", "--verbose" in cmd)

# cwd is handled by subprocess cwd= parameter, not a CLI flag
cmd = cb.build_command("Fix the tests", cwd="/home/user/project")
check("claude-cmd-cwd: no --cwd flag", "--cwd" not in cmd)

cmd = cb.build_command("Continue", session_id="sess-xyz", cwd="/tmp/work")
sid_idx = cmd.index("--session-id")
check("claude-cmd-both: session follows flag", cmd[sid_idx + 1] == "sess-xyz")
check("claude-cmd-both: no --cwd flag", "--cwd" not in cmd)
of_idx = cmd.index("--output-format")
check("claude-cmd-both: format follows flag", cmd[of_idx + 1] == "stream-json")

# ====================================================================
# Spec 03: Command building — Codex
# ====================================================================

print("\n--- Codex command building ---")
xb = CodexBackend()

cmd = xb.build_command("Write unit tests")
check("codex-cmd-basic", cmd == ["codex", "exec", "-m", "gpt-5.3-codex", "--json", "Write unit tests"])

xb2 = CodexBackend(model="gpt-5.2-codex")
cmd = xb2.build_command("Debug the API")
check("codex-cmd-custom-model: -m", "-m" in cmd)
check("codex-cmd-custom-model: value", "gpt-5.2-codex" in cmd)

cmd = xb.build_command("ignored", session_id="019c7199-a895-74f2")
check("codex-cmd-resume", cmd == ["codex", "exec", "resume", "019c7199-a895-74f2", "-m", "gpt-5.3-codex", "--json"])
check("codex-cmd-resume: no prompt", "ignored" not in cmd)

# Codex cwd is NOT in command
cmd = xb.build_command("Fix bugs", cwd="/home/user/project")
check("codex-cmd-cwd-absent", "/home/user/project" not in cmd)

# ====================================================================
# Spec 02: Environment sanitization
# ====================================================================

print("\n--- Environment sanitization ---")

# Claude subscription mode
cb = ClaudeBackend()
cb.set_auth_mode("subscription")
old_key = os.environ.get("ANTHROPIC_API_KEY")
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test123"
env = cb.build_env()
check("claude-env-sub: no ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY" not in env)
check("claude-env-sub: HOME preserved", "HOME" in env)
check("claude-env-sub: PATH preserved", "PATH" in env)

# Claude api_key mode
cb.set_auth_mode("api_key")
env = cb.build_env()
check("claude-env-api: ANTHROPIC_API_KEY present", env.get("ANTHROPIC_API_KEY") == "sk-ant-test123")

# Restore
if old_key is not None:
    os.environ["ANTHROPIC_API_KEY"] = old_key
else:
    os.environ.pop("ANTHROPIC_API_KEY", None)

# Codex subscription mode
xb = CodexBackend()
xb.set_auth_mode("subscription")
old_oai = os.environ.get("OPENAI_API_KEY")
old_codex = os.environ.get("CODEX_API_KEY")
os.environ["OPENAI_API_KEY"] = "sk-openai-test456"
os.environ["CODEX_API_KEY"] = "sk-codex-test789"
env = xb.build_env()
check("codex-env-sub: no OPENAI_API_KEY", "OPENAI_API_KEY" not in env)
check("codex-env-sub: no CODEX_API_KEY", "CODEX_API_KEY" not in env)
check("codex-env-sub: HOME preserved", "HOME" in env)

# Codex api_key mode
xb.set_auth_mode("api_key")
env = xb.build_env()
check("codex-env-api: OPENAI_API_KEY present", env.get("OPENAI_API_KEY") == "sk-openai-test456")

# Restore
if old_oai is not None:
    os.environ["OPENAI_API_KEY"] = old_oai
else:
    os.environ.pop("OPENAI_API_KEY", None)
if old_codex is not None:
    os.environ["CODEX_API_KEY"] = old_codex
else:
    os.environ.pop("CODEX_API_KEY", None)

# ====================================================================
# Spec 13: Backend protocol / ABC enforcement
# ====================================================================

print("\n--- Backend protocol ---")

# ABC enforcement: cannot instantiate without implementing abstracts
try:
    class BadBackend(CodingBackend):
        pass
    BadBackend()
    check("abc-enforcement", False, "Should raise TypeError")
except TypeError:
    check("abc-enforcement", True)

# ClaudeBackend satisfies protocol
try:
    c = ClaudeBackend()
    check("claude-protocol: name", c.name == "claude")
    check("claude-protocol: instantiate", True)
except TypeError:
    check("claude-protocol: instantiate", False, "Unexpected TypeError")

# CodexBackend satisfies protocol
try:
    x = CodexBackend()
    check("codex-protocol: name", x.name == "codex")
    check("codex-protocol: instantiate", True)
except TypeError:
    check("codex-protocol: instantiate", False, "Unexpected TypeError")

# Auth mode propagation
cb = ClaudeBackend()
cb.set_auth_mode("subscription")
check("auth-propagation: subscription", cb._auth_mode == "subscription")
cb.set_auth_mode("api_key")
check("auth-propagation: api_key", cb._auth_mode == "api_key")

# ====================================================================
# Spec 06: Cross-backend normalization equivalence
# ====================================================================

print("\n--- Cross-backend normalization ---")

# Both produce text events with same kind
claude_ev = ClaudeBackend().parse_line('{"type":"assistant","subtype":"text","text":"Hello world"}')
codex_ev = CodexBackend().parse_line('{"type":"item.completed","item":{"id":"i","type":"agent_message","text":"Hello world"}}')
check("cross-text: both kind text", claude_ev.kind == "text" and codex_ev.kind == "text")
check("cross-text: same text", claude_ev.text == codex_ev.text == "Hello world")

# Both produce init events
claude_ev = ClaudeBackend().parse_line('{"type":"system","subtype":"init","session_id":"sess-001"}')
codex_ev = CodexBackend().parse_line('{"type":"thread.started","thread_id":"thread-001"}')
check("cross-init: both kind init", claude_ev.kind == "init" and codex_ev.kind == "init")
check("cross-init: claude session_id", claude_ev.session_id == "sess-001")
check("cross-init: codex session_id", codex_ev.session_id == "thread-001")

# Both produce tool_start events
claude_ev = ClaudeBackend().parse_line(json.dumps({
    "type": "assistant", "subtype": "tool_use",
    "tool": {"name": "Write", "input": {}}
}))
codex_ev = CodexBackend().parse_line(json.dumps({
    "type": "item.completed",
    "item": {"id": "i", "type": "tool_call", "name": "shell", "arguments": "{}"}
}))
check("cross-tool: both kind tool_start", claude_ev.kind == "tool_start" and codex_ev.kind == "tool_start")
check("cross-tool: non-empty tool_name", claude_ev.tool_name != "" and codex_ev.tool_name != "")

# ====================================================================
# Summary
# ====================================================================

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
