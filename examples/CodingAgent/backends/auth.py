"""
Auth probing — detect subscription vs API-key auth at startup.

Uses synchronous subprocess.run() so it is safe to call from __init__.
"""

import os
import subprocess
import sys
from typing import Optional

from .base import CodingBackend


def probe_auth(backend: CodingBackend, timeout: float = 30.0) -> str:
    """Probe authentication and return 'subscription' or 'api_key'.

    Raises RuntimeError if no auth method is available.
    """
    # 1. Check CLI installed
    if not backend.check_cli_installed():
        cli = backend.cli_binary
        if cli == "claude":
            install = "npm install -g @anthropic-ai/claude-code"
        else:
            install = "npm install -g @openai/codex"
        raise RuntimeError(
            f"{cli.title()} Code CLI not found. "
            f"Install with: {install}"
        )

    # 2. Build probe command and environment (strip API keys)
    cmd = backend.probe_command()
    env = os.environ.copy()
    for var in backend.api_key_env_vars:
        env.pop(var, None)

    # 3. Run probe
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        if result.returncode == 0:
            return "subscription"
    except subprocess.TimeoutExpired:
        pass  # Fall through to API-key check
    except Exception:
        pass

    # 4. Check for API key fallback
    for var in backend.api_key_env_vars:
        if os.environ.get(var):
            _print_api_key_warning(backend)
            return "api_key"

    # 5. No auth at all
    cli = backend.cli_binary
    key_names = " or ".join(backend.api_key_env_vars)
    raise RuntimeError(
        f"No auth available for {cli}. "
        f"Run '{cli} login' or set {key_names}."
    )


def _print_api_key_warning(backend: CodingBackend) -> None:
    """Print a coloured warning box to stderr."""
    cli = backend.cli_binary
    key_name = backend.api_key_env_vars[0]

    yellow = "\033[33m"
    red = "\033[31m"
    bold = "\033[1m"
    reset = "\033[0m"

    lines = [
        f"{bold}{red}{'='*62}{reset}",
        f"{bold}{yellow}  WARNING: No subscription auth found for {cli.title()} Code.{reset}",
        f"{yellow}  Falling back to {key_name} (API billing).{reset}",
        f"{yellow}  This may cost 5-10x more than subscription pricing.{reset}",
        f"{yellow}{reset}",
    ]

    if cli == "claude":
        lines += [
            f"{yellow}  To set up subscription auth:{reset}",
            f"{yellow}    1. Run: claude login{reset}",
            f"{yellow}    2. Complete the OAuth flow in your browser{reset}",
            f"{yellow}    3. Restart this agent{reset}",
            f"{yellow}{reset}",
            f"{yellow}  For long-lived/headless environments:{reset}",
            f"{yellow}    1. Run: claude setup-token{reset}",
            f"{yellow}    2. Export: CLAUDE_CODE_OAUTH_TOKEN=<token>{reset}",
            f"{yellow}    3. Restart this agent{reset}",
        ]
    else:
        lines += [
            f"{yellow}  To set up subscription auth:{reset}",
            f"{yellow}    1. Run: codex login{reset}",
            f"{yellow}    2. Complete the OAuth flow in your browser{reset}",
            f"{yellow}    3. Restart this agent{reset}",
        ]

    lines.append(f"{bold}{red}{'='*62}{reset}")

    for line in lines:
        print(line, file=sys.stderr)
