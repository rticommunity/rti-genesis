#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Slack Interface — Unit Tests (Test Gates 3, 4)

Covers GWT Sections 03, 06, 08, 15:
- Slack mrkdwn conversion
- Session key construction (channel, thread)
- Configuration loading (file, env var, overrides, both tokens required)

Uses Genesis check/failures/sys.exit pattern. No pytest.
No real Slack tokens or DDS network required.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slack_interface import (
    _format_for_slack,
    _session_key,
    load_config,
)

# ── Test Infrastructure ──────────────────────────────────────────────────
failures = []
passed = 0


def check(name, condition, detail=""):
    global passed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failures.append(name)
        msg = f"  FAIL: {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


# ── Test Gate 3: mrkdwn Conversion (GWT §06) ────────────────────────────

def test_mrkdwn_conversion():
    print(f"\n{'='*60}")
    print("  Slack mrkdwn Conversion Tests (GWT §06)")
    print(f"{'='*60}")

    # **bold** → *bold*
    result = _format_for_slack("**bold text**")
    check("mrkdwn: bold conversion",
          result == "*bold text*",
          f"got: '{result}'")

    # [text](url) → <url|text>
    result = _format_for_slack("[click here](https://example.com)")
    check("mrkdwn: link conversion",
          result == "<https://example.com|click here>",
          f"got: '{result}'")

    # Triple-backtick code block preserved unchanged
    code = "```python\nprint('hello')\n```"
    result = _format_for_slack(code)
    check("mrkdwn: code block preserved",
          result == code,
          f"got: '{result}'")

    # Plain text passes through
    result = _format_for_slack("Hello world")
    check("mrkdwn: plain text unchanged",
          result == "Hello world",
          f"got: '{result}'")

    # HTML entities escaped
    result = _format_for_slack("a < b & c > d")
    check("mrkdwn: HTML entities escaped",
          "&lt;" in result and "&amp;" in result and "&gt;" in result,
          f"got: '{result}'")

    # Mixed content: bold + link
    result = _format_for_slack("**bold** and [link](https://x.com)")
    check("mrkdwn: mixed bold + link",
          "*bold*" in result and "<https://x.com|link>" in result,
          f"got: '{result}'")

    # Empty string
    result = _format_for_slack("")
    check("mrkdwn: empty string", result == "")

    # None returns None
    result = _format_for_slack(None)
    check("mrkdwn: None returns None", result is None)

    # Code block with surrounding text
    text = "Here is code:\n```\nfoo()\n```\nAnd **bold**."
    result = _format_for_slack(text)
    check("mrkdwn: code block preserved with surrounding text",
          "```\nfoo()\n```" in result and "*bold*" in result,
          f"got: '{result}'")


# ── Test Gate 3: Session Key (GWT §03) ──────────────────────────────────

def test_session_key():
    print(f"\n{'='*60}")
    print("  Session Key Tests (GWT §03)")
    print(f"{'='*60}")

    # Channel-level session (no thread)
    key = _session_key("C12345", None)
    check("session: channel only → channel key",
          key == "C12345",
          f"got: '{key}'")

    # Thread-level session
    key = _session_key("C12345", "1234567890.123456")
    check("session: channel + thread → thread key",
          key == "C12345:1234567890.123456",
          f"got: '{key}'")

    # Different channels → different keys
    key1 = _session_key("C12345")
    key2 = _session_key("C67890")
    check("session: different channels → different keys",
          key1 != key2)

    # Same channel + same thread → same key
    key1 = _session_key("C12345", "ts1")
    key2 = _session_key("C12345", "ts1")
    check("session: same channel + thread → same key",
          key1 == key2)

    # Same channel, different threads → different keys
    key1 = _session_key("C12345", "ts1")
    key2 = _session_key("C12345", "ts2")
    check("session: same channel, different threads → different keys",
          key1 != key2)


# ── Test Gate 4: Configuration (GWT §08) ────────────────────────────────

def test_config():
    print(f"\n{'='*60}")
    print("  Slack Configuration Tests (GWT §08)")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # load_config reads both tokens from file
        config_data = {
            "slack": {"bot_token": "xoxb-file", "app_token": "xapp-file"},
            "genesis": {"request_timeout": 30.0},
        }
        config_path = os.path.join(tmpdir, "test_config.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # Clear any env vars first
        env_bot = os.environ.pop("SLACK_BOT_TOKEN", None)
        env_app = os.environ.pop("SLACK_APP_TOKEN", None)
        try:
            config = load_config(config_path)
            check("config: reads bot_token from file",
                  config["slack"]["bot_token"] == "xoxb-file")
            check("config: reads app_token from file",
                  config["slack"]["app_token"] == "xapp-file")
            check("config: reads genesis settings",
                  config["genesis"]["request_timeout"] == 30.0)
        finally:
            if env_bot:
                os.environ["SLACK_BOT_TOKEN"] = env_bot
            if env_app:
                os.environ["SLACK_APP_TOKEN"] = env_app

        # Missing app_token raises clear error
        env_bot = os.environ.pop("SLACK_BOT_TOKEN", None)
        env_app = os.environ.pop("SLACK_APP_TOKEN", None)
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test"
        try:
            try:
                load_config(None)
                check("config: missing app_token exits", False, "no SystemExit raised")
            except SystemExit as e:
                check("config: missing app_token exits", e.code == 1)
        finally:
            del os.environ["SLACK_BOT_TOKEN"]
            if env_bot:
                os.environ["SLACK_BOT_TOKEN"] = env_bot
            if env_app:
                os.environ["SLACK_APP_TOKEN"] = env_app

        # Env vars override file values
        env_bot = os.environ.pop("SLACK_BOT_TOKEN", None)
        env_app = os.environ.pop("SLACK_APP_TOKEN", None)
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-env-override"
        os.environ["SLACK_APP_TOKEN"] = "xapp-env-override"
        try:
            config = load_config(config_path)
            check("config: env var overrides bot_token",
                  config["slack"]["bot_token"] == "xoxb-env-override")
            check("config: env var overrides app_token",
                  config["slack"]["app_token"] == "xapp-env-override")
        finally:
            del os.environ["SLACK_BOT_TOKEN"]
            del os.environ["SLACK_APP_TOKEN"]
            if env_bot:
                os.environ["SLACK_BOT_TOKEN"] = env_bot
            if env_app:
                os.environ["SLACK_APP_TOKEN"] = env_app

        # Missing both tokens exits
        env_bot = os.environ.pop("SLACK_BOT_TOKEN", None)
        env_app = os.environ.pop("SLACK_APP_TOKEN", None)
        try:
            try:
                load_config(None)
                check("config: missing both tokens exits", False, "no SystemExit raised")
            except SystemExit as e:
                check("config: missing both tokens exits", e.code == 1)
        finally:
            if env_bot:
                os.environ["SLACK_BOT_TOKEN"] = env_bot
            if env_app:
                os.environ["SLACK_APP_TOKEN"] = env_app

        # Defaults for non-secret fields
        minimal_config = {
            "slack": {"bot_token": "xoxb-test", "app_token": "xapp-test"},
        }
        minimal_path = os.path.join(tmpdir, "minimal.json")
        with open(minimal_path, "w") as f:
            json.dump(minimal_config, f)

        env_bot = os.environ.pop("SLACK_BOT_TOKEN", None)
        env_app = os.environ.pop("SLACK_APP_TOKEN", None)
        try:
            config = load_config(minimal_path)
            check("config: default timeout",
                  config["genesis"]["request_timeout"] == 60.0)
            check("config: default discovery_wait",
                  config["genesis"]["discovery_wait"] == 5.0)
            check("config: default respond_in_threads",
                  config["slack"]["respond_in_threads"] is True)
        finally:
            if env_bot:
                os.environ["SLACK_BOT_TOKEN"] = env_bot
            if env_app:
                os.environ["SLACK_APP_TOKEN"] = env_app


# ── Test Gate 7: Interface Init (GWT §01, §02) ──────────────────────────

def test_interface_init():
    print(f"\n{'='*60}")
    print("  Interface Init Tests (GWT §01, §02)")
    print(f"{'='*60}")

    from slack_interface import SlackGenesisInterface

    config = {
        "slack": {"bot_token": "xoxb-test", "app_token": "xapp-test", "respond_in_threads": True},
        "genesis": {"default_agent_service": None, "request_timeout": 60.0, "discovery_wait": 5.0},
    }
    iface = SlackGenesisInterface(config)

    # Interface is None before _init_genesis
    check("init: interface is None before genesis init",
          iface.interface is None)

    # Sessions dict is empty
    check("init: sessions empty on creation",
          len(iface.sessions) == 0)

    # Session management
    iface.sessions["C12345:ts1"] = {
        "conversation_id": "slack-C12345:ts1",
        "connected_agent_service": "TestService",
    }
    check("init: session stored",
          "C12345:ts1" in iface.sessions)

    # Session removal
    del iface.sessions["C12345:ts1"]
    check("init: session removed",
          "C12345:ts1" not in iface.sessions)


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Slack Interface — Unit Tests")
    print("  (Test Gates 3, 4, 7: Pure Logic + Config + Init)")
    print("=" * 60)

    test_mrkdwn_conversion()
    test_session_key()
    test_config()
    test_interface_init()

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    total = passed + len(failures)
    print(f"  Results: {passed}/{total} passed")
    if failures:
        print("  FAILURES:")
        for f in failures:
            print(f"    - {f}")
        sys.exit(1)
    else:
        print("  All tests passed!")
        sys.exit(0)
