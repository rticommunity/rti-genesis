#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
SlackGenesisInterface — Slack bot for Genesis agents.

Provides a Slack bot (Socket Mode) that connects to Genesis agents via
MonitoredInterface, enabling users to interact with agents through Slack.

Features:
- /genesis-agents — Block Kit buttons for agent selection
- /genesis-connect <name> — connect by name
- /genesis-disconnect — remove session binding
- /genesis-status — show connected agent + conversation_id
- Messages forwarded to connected Genesis agent, replies in threads
"""

import asyncio
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logger = logging.getLogger(__name__)

# ── Pure Logic: Message Formatting ────────────────────────────────────────


def _format_for_slack(text: str) -> str:
    """Convert standard markdown to Slack mrkdwn format.

    Conversions:
    - **bold** → *bold*
    - [text](url) → <url|text>
    - Code blocks (triple backtick) pass through unchanged
    - Escape &, <, > for Slack

    Args:
        text: Standard markdown text.

    Returns:
        Slack mrkdwn formatted text.
    """
    if not text:
        return text

    # Extract code blocks to protect them from conversion
    code_blocks = []
    code_pattern = re.compile(r'(```[\s\S]*?```)')

    def _save_code_block(match):
        code_blocks.append(match.group(0))
        return f"\x00CODE_BLOCK_{len(code_blocks) - 1}\x00"

    text = code_pattern.sub(_save_code_block, text)

    # Escape HTML entities for Slack
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # Convert **bold** to *bold* (do this before italic conversion)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

    # Convert [text](url) to <url|text>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODE_BLOCK_{i}\x00", block)

    return text


# ── Pure Logic: Session Key ──────────────────────────────────────────────


def _session_key(channel: str, thread_ts: str = None) -> str:
    """Create a deterministic session key for a Slack context.

    Thread-based sessions: (channel, thread_ts) → unique key.
    Channel-based sessions when no thread: channel → key.

    Args:
        channel: Slack channel ID.
        thread_ts: Thread timestamp (None for channel-level).

    Returns:
        Session key string.
    """
    if thread_ts:
        return f"{channel}:{thread_ts}"
    return channel


# ── Configuration ────────────────────────────────────────────────────────


def load_config(config_path: str = None) -> dict:
    """Load Slack interface configuration.

    Hierarchy:
    1. Config JSON file values (base)
    2. Environment variables override JSON
    3. Hardcoded defaults for non-secret fields

    Args:
        config_path: Path to JSON config file. None to use env vars only.

    Returns:
        Configuration dictionary.
    """
    # Defaults
    config = {
        "slack": {
            "bot_token": "",
            "app_token": "",
            "respond_in_threads": True,
        },
        "genesis": {
            "default_agent_service": None,
            "request_timeout": 60.0,
            "discovery_wait": 5.0,
        },
    }

    # Load from file
    if config_path:
        if not os.path.exists(config_path):
            print(f"ERROR: Config file not found: {config_path}")
            sys.exit(1)
        with open(config_path, "r") as f:
            file_config = json.load(f)
        # Merge slack section
        if "slack" in file_config:
            config["slack"].update(file_config["slack"])
        # Merge genesis section
        if "genesis" in file_config:
            config["genesis"].update(file_config["genesis"])

    # Environment variable overrides
    env_bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if env_bot_token:
        config["slack"]["bot_token"] = env_bot_token

    env_app_token = os.environ.get("SLACK_APP_TOKEN")
    if env_app_token:
        config["slack"]["app_token"] = env_app_token

    # Validate required fields
    if not config["slack"]["bot_token"]:
        print("ERROR: Slack bot token is required.")
        print("Set SLACK_BOT_TOKEN environment variable or provide a config file.")
        sys.exit(1)

    if not config["slack"]["app_token"]:
        print("ERROR: Slack app token is required for Socket Mode.")
        print("Set SLACK_APP_TOKEN environment variable or provide a config file.")
        sys.exit(1)

    return config


# ── Full Interface ────────────────────────────────────────────────────────


class SlackGenesisInterface:
    """Slack bot interface for Genesis agents.

    Uses Socket Mode — no public URL required.
    Composition over MonitoredInterface (same pattern as MemoryWebGUI).
    """

    def __init__(self, config: dict):
        self.config = config
        self.interface = None  # MonitoredInterface — created in _init_genesis
        self.sessions = {}  # session_key -> {"conversation_id": str, "connected_agent_service": str}
        self.app = None  # Slack AsyncApp
        self.default_agent_service = config["genesis"].get("default_agent_service")
        self.request_timeout = config["genesis"].get("request_timeout", 60.0)
        self.discovery_wait = config["genesis"].get("discovery_wait", 5.0)
        self.respond_in_threads = config["slack"].get("respond_in_threads", True)

    # ── Genesis Lifecycle ─────────────────────────────────────────────

    async def _init_genesis(self):
        """Create MonitoredInterface and wait for agent discovery."""
        from genesis_lib.monitored_interface import MonitoredInterface

        logger.info("Initializing Genesis DDS...")
        self.interface = MonitoredInterface(
            interface_name="SlackBot",
            service_name="SlackBotService",
        )
        logger.info(f"Waiting {self.discovery_wait}s for DDS discovery...")
        await asyncio.sleep(self.discovery_wait)
        agent_count = len(self.interface.available_agents)
        logger.info(f"Discovery complete: {agent_count} agent(s) found.")

    async def _connect_agent_for_session(self, session_key: str, service_name: str) -> bool:
        """Connect a session to a specific agent."""
        if not self.interface:
            return False
        ok = await self.interface.connect_to_agent(service_name, timeout_seconds=10.0)
        if ok:
            conv_id = f"slack-{session_key}"
            self.sessions[session_key] = {
                "conversation_id": conv_id,
                "connected_agent_service": service_name,
            }
            logger.info(f"Session {session_key} connected to {service_name} (conv_id={conv_id})")
        return ok

    def _get_available_agents(self) -> list:
        """Get list of available agents as dicts."""
        if not self.interface:
            return []
        agents = []
        for agent_id, info in self.interface.available_agents.items():
            agents.append({
                "id": agent_id,
                "name": info.get("prefered_name", "Unknown"),
                "service_name": info.get("service_name", ""),
            })
        return agents

    def _build_agent_blocks(self, agents: list) -> list:
        """Build Slack Block Kit blocks for agent selection."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Select an agent to connect to:",
                },
            }
        ]
        buttons = []
        for agent in agents:
            buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": agent["name"]},
                "action_id": f"connect_agent_{agent['service_name']}",
                "value": agent["service_name"],
            })
        if buttons:
            blocks.append({
                "type": "actions",
                "elements": buttons,
            })
        return blocks

    # ── Slack Handler Registration ────────────────────────────────────

    def _register_handlers(self):
        """Register all Slack event/command handlers."""

        @self.app.command("/genesis-agents")
        async def handle_agents_command(ack, respond):
            await ack()
            agents = self._get_available_agents()
            if not agents:
                await respond("No Genesis agents are currently available.")
                return
            blocks = self._build_agent_blocks(agents)
            await respond(blocks=blocks)

        @self.app.command("/genesis-connect")
        async def handle_connect_command(ack, respond, command):
            await ack()
            service_name = command.get("text", "").strip()
            if not service_name:
                await respond("Usage: /genesis-connect <agent_service_name>")
                return

            channel = command.get("channel_id", "")
            thread_ts = None  # Slash commands don't have thread context
            key = _session_key(channel, thread_ts)

            ok = await self._connect_agent_for_session(key, service_name)
            if ok:
                # Find agent name
                agent_name = service_name
                for agent in self._get_available_agents():
                    if agent["service_name"] == service_name:
                        agent_name = agent["name"]
                        break
                await respond(f"Connected to {agent_name}!")
            else:
                await respond("Failed to connect to agent.")

        @self.app.command("/genesis-disconnect")
        async def handle_disconnect_command(ack, respond, command):
            await ack()
            channel = command.get("channel_id", "")
            key = _session_key(channel)
            if key in self.sessions:
                del self.sessions[key]
                await respond("Disconnected from agent.")
            else:
                await respond("No agent connected.")

        @self.app.command("/genesis-status")
        async def handle_status_command(ack, respond, command):
            await ack()
            channel = command.get("channel_id", "")
            # Check channel-level session
            key = _session_key(channel)
            session = self.sessions.get(key)
            if session:
                agent_name = session["connected_agent_service"]
                for agent in self._get_available_agents():
                    if agent["service_name"] == session["connected_agent_service"]:
                        agent_name = agent["name"]
                        break
                await respond(
                    f"Agent: {agent_name}\n"
                    f"Conversation ID: {session['conversation_id']}"
                )
            else:
                await respond("No agent connected. Use /genesis-agents to connect.")

        @self.app.action(re.compile(r"^connect_agent_"))
        async def handle_agent_button(ack, body, respond):
            await ack()
            action = body.get("actions", [{}])[0]
            service_name = action.get("value", "")
            channel = body.get("channel", {}).get("id", "")
            thread_ts = body.get("message", {}).get("thread_ts")

            key = _session_key(channel, thread_ts)
            ok = await self._connect_agent_for_session(key, service_name)
            if ok:
                agent_name = service_name
                for agent in self._get_available_agents():
                    if agent["service_name"] == service_name:
                        agent_name = agent["name"]
                        break
                await respond(f"Connected to {agent_name}!")
            else:
                await respond("Failed to connect to agent.")

        @self.app.event("message")
        async def handle_message(event, say):
            # Ignore subtypes (message_changed, bot_message, etc.)
            if event.get("subtype"):
                return

            # Ignore bot messages
            if event.get("bot_id"):
                return

            text = event.get("text", "")
            if not text:
                return

            channel = event.get("channel", "")
            thread_ts = event.get("thread_ts")
            message_ts = event.get("ts", "")

            # Determine session key: check thread first, then channel
            key = _session_key(channel, thread_ts) if thread_ts else None
            session = self.sessions.get(key) if key else None

            # Fall back to channel-level session
            if not session:
                channel_key = _session_key(channel)
                session = self.sessions.get(channel_key)
                if session:
                    key = channel_key

            # Auto-connect if no session
            if not session:
                agents = self._get_available_agents()
                auto_service = None

                if self.default_agent_service:
                    auto_service = self.default_agent_service
                elif len(agents) == 1:
                    auto_service = agents[0]["service_name"]
                else:
                    reply_ts = thread_ts or message_ts
                    await say(
                        text="No agent connected. Use /genesis-agents to select one.",
                        thread_ts=reply_ts if self.respond_in_threads else None,
                    )
                    return

                key = _session_key(channel, thread_ts)
                ok = await self._connect_agent_for_session(key, auto_service)
                if not ok:
                    reply_ts = thread_ts or message_ts
                    await say(
                        text="Failed to auto-connect to agent.",
                        thread_ts=reply_ts if self.respond_in_threads else None,
                    )
                    return
                session = self.sessions[key]

            # Send to Genesis agent
            reply_ts = thread_ts or message_ts
            try:
                response = await self.interface.send_request(
                    {
                        "message": text,
                        "conversation_id": session["conversation_id"],
                    },
                    timeout_seconds=self.request_timeout,
                )

                if response is None:
                    await say(
                        text="Agent timed out. Please try again.",
                        thread_ts=reply_ts if self.respond_in_threads else None,
                    )
                    return

                if response.get("status", 1) != 0:
                    error_msg = response.get("message", "Unknown error")
                    await say(
                        text=f"Agent error: {error_msg}",
                        thread_ts=reply_ts if self.respond_in_threads else None,
                    )
                    return

                reply_text = response.get("message", "")
                formatted = _format_for_slack(reply_text)
                await say(
                    text=formatted,
                    thread_ts=reply_ts if self.respond_in_threads else None,
                )

            except Exception as e:
                logger.error(f"Error handling message: {e}")
                try:
                    await say(
                        text="An error occurred processing your message.",
                        thread_ts=reply_ts if self.respond_in_threads else None,
                    )
                except Exception:
                    pass

    # ── Main ──────────────────────────────────────────────────────────

    async def start(self):
        """Initialize Genesis and start the Slack bot."""
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        # Initialize Genesis
        await self._init_genesis()

        # Build Slack app
        bot_token = self.config["slack"]["bot_token"]
        app_token = self.config["slack"]["app_token"]

        self.app = AsyncApp(token=bot_token)
        self._register_handlers()

        handler = AsyncSocketModeHandler(self.app, app_token)
        logger.info("Starting Slack bot (Socket Mode)...")

        try:
            await handler.start_async()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            if self.interface:
                await self.interface.close()


# ── CLI Entry Point ──────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Genesis Slack Bot Interface")
    parser.add_argument("--config", help="Path to JSON config file")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )

    config = load_config(args.config)
    bot = SlackGenesisInterface(config)
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
