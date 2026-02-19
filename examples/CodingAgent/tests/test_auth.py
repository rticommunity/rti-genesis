#!/usr/bin/env python3
"""
Unit tests for auth probing logic.

Covers spec: 01-auth-probing.txt
Uses mocking (unittest.mock) — no DDS or real CLI required.
"""

import os
import sys
import io
from unittest.mock import patch, MagicMock
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backends.claude_backend import ClaudeBackend
from backends.codex_backend import CodexBackend
from backends.auth import probe_auth

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
# CLI detection
# ====================================================================
print("--- CLI detection ---")

# Claude CLI not found
with patch("backends.base.shutil.which", return_value=None):
    try:
        probe_auth(ClaudeBackend(), timeout=5.0)
        check("claude-cli-missing: raises", False, "Should have raised RuntimeError")
    except RuntimeError as e:
        check("claude-cli-missing: raises", True)
        check("claude-cli-missing: msg", "not found" in str(e).lower(), str(e))

# Codex CLI not found
with patch("backends.base.shutil.which", return_value=None):
    try:
        probe_auth(CodexBackend(), timeout=5.0)
        check("codex-cli-missing: raises", False, "Should have raised RuntimeError")
    except RuntimeError as e:
        check("codex-cli-missing: raises", True)
        check("codex-cli-missing: msg", "not found" in str(e).lower(), str(e))

# Claude CLI found
with patch("backends.base.shutil.which", return_value="/usr/local/bin/claude"):
    cb = ClaudeBackend()
    check("claude-cli-found", cb.check_cli_installed())

# Codex CLI found
with patch("backends.base.shutil.which", return_value="/usr/local/bin/codex"):
    xb = CodexBackend()
    check("codex-cli-found", xb.check_cli_installed())


# ====================================================================
# No auth available (neither subscription nor API key)
# ====================================================================
print("\n--- No auth available ---")

# Claude: no subscription, no API key
env_no_keys = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")}
with patch("backends.base.shutil.which", return_value="/usr/local/bin/claude"), \
     patch("subprocess.run", return_value=MagicMock(returncode=1)), \
     patch.dict(os.environ, env_no_keys, clear=True):
    try:
        probe_auth(ClaudeBackend(), timeout=5.0)
        check("claude-no-auth: raises", False, "Should have raised RuntimeError")
    except RuntimeError as e:
        msg = str(e)
        check("claude-no-auth: raises", True)
        check("claude-no-auth: no auth available", "No auth available" in msg, msg)
        check("claude-no-auth: mentions login", "claude login" in msg, msg)

# Codex: no subscription, no API key
env_no_keys = {k: v for k, v in os.environ.items()
               if k not in ("OPENAI_API_KEY", "CODEX_API_KEY")}
with patch("backends.base.shutil.which", return_value="/usr/local/bin/codex"), \
     patch("subprocess.run", return_value=MagicMock(returncode=1)), \
     patch.dict(os.environ, env_no_keys, clear=True):
    try:
        probe_auth(CodexBackend(), timeout=5.0)
        check("codex-no-auth: raises", False, "Should have raised RuntimeError")
    except RuntimeError as e:
        msg = str(e)
        check("codex-no-auth: raises", True)
        check("codex-no-auth: no auth available", "No auth available" in msg, msg)
        check("codex-no-auth: mentions login", "codex login" in msg, msg)


# ====================================================================
# Subscription probe succeeds
# ====================================================================
print("\n--- Subscription probe ---")

with patch("backends.base.shutil.which", return_value="/usr/local/bin/claude"), \
     patch("subprocess.run", return_value=MagicMock(returncode=0)):
    mode = probe_auth(ClaudeBackend(), timeout=5.0)
    check("claude-subscription: mode", mode == "subscription")

with patch("backends.base.shutil.which", return_value="/usr/local/bin/codex"), \
     patch("subprocess.run", return_value=MagicMock(returncode=0)):
    mode = probe_auth(CodexBackend(), timeout=5.0)
    check("codex-subscription: mode", mode == "subscription")


# ====================================================================
# API key fallback with warning
# ====================================================================
print("\n--- API key fallback ---")

# Claude: subscription fails, API key present
env_with_key = os.environ.copy()
env_with_key["ANTHROPIC_API_KEY"] = "sk-ant-test123"
captured_stderr = io.StringIO()
with patch("backends.base.shutil.which", return_value="/usr/local/bin/claude"), \
     patch("subprocess.run", return_value=MagicMock(returncode=1)), \
     patch.dict(os.environ, env_with_key, clear=True), \
     patch("sys.stderr", captured_stderr):
    mode = probe_auth(ClaudeBackend(), timeout=5.0)
    check("claude-fallback: mode", mode == "api_key")
    warning_output = captured_stderr.getvalue()
    check("claude-fallback: WARNING", "WARNING" in warning_output, warning_output[:200])
    check("claude-fallback: Falling back", "Falling back" in warning_output, warning_output[:200])
    check("claude-fallback: claude login", "claude login" in warning_output)
    check("claude-fallback: setup-token", "setup-token" in warning_output)
    check("claude-fallback: 5-10x", "5-10x" in warning_output)

# Codex: subscription fails, API key present
env_with_key = os.environ.copy()
env_with_key["OPENAI_API_KEY"] = "sk-openai-test456"
env_with_key.pop("CODEX_API_KEY", None)
captured_stderr = io.StringIO()
with patch("backends.base.shutil.which", return_value="/usr/local/bin/codex"), \
     patch("subprocess.run", return_value=MagicMock(returncode=1)), \
     patch.dict(os.environ, env_with_key, clear=True), \
     patch("sys.stderr", captured_stderr):
    mode = probe_auth(CodexBackend(), timeout=5.0)
    check("codex-fallback: mode", mode == "api_key")
    warning_output = captured_stderr.getvalue()
    check("codex-fallback: WARNING", "WARNING" in warning_output)
    check("codex-fallback: codex login", "codex login" in warning_output)


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
