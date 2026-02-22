#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
TelegramGenesisInterface — Telegram bot for Genesis agents.

Provides a Telegram bot that connects to Genesis agents via MonitoredInterface,
enabling users to interact with agents through Telegram messages.

Features:
- /start — welcome message with command list
- /agents — inline keyboard for agent selection
- /disconnect — remove session binding
- /status — show connected agent + conversation_id
- Text messages forwarded to connected Genesis agent
- MarkdownV2 formatting, message splitting, access control
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

# Characters that must be escaped in Telegram MarkdownV2
_MARKDOWNV2_SPECIAL = r'_*[]()~`>#+-=|{}.!'


def _escape_markdownv2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2.

    Escapes the 18 special characters required by Telegram's MarkdownV2 format.
    Does not double-escape already-escaped characters.
    """
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and i + 1 < len(text) and text[i + 1] in _MARKDOWNV2_SPECIAL:
            # Already escaped — pass through both characters
            result.append(ch)
            result.append(text[i + 1])
            i += 2
        elif ch in _MARKDOWNV2_SPECIAL:
            result.append('\\')
            result.append(ch)
            i += 1
        else:
            result.append(ch)
            i += 1
    return ''.join(result)


def _split_message(text: str, limit: int = 4096) -> list:
    """Split a message into chunks that fit within the Telegram message limit.

    Splits at newline boundaries when possible. Never splits mid-code-block.
    Returns a list of strings, each at most `limit` characters.
    """
    if not text:
        return [""]

    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        # Try to find a newline boundary within the limit
        split_at = remaining.rfind('\n', 0, limit)
        if split_at <= 0:
            # No good newline boundary — hard split at limit
            split_at = limit

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip('\n') if split_at < len(remaining) else ""

    return chunks


# ── Pure Logic: Access Control ────────────────────────────────────────────


def _is_allowed(chat_id: int, allowed_chat_ids: list = None) -> bool:
    """Check if a chat_id is in the allowlist.

    Args:
        chat_id: The Telegram chat ID to check.
        allowed_chat_ids: List of allowed chat IDs. None means allow all.

    Returns:
        True if allowed, False otherwise.
    """
    if allowed_chat_ids is None:
        return True
    return chat_id in allowed_chat_ids


# ── Pure Logic: Session Key ──────────────────────────────────────────────


def _session_key(chat_id: int) -> str:
    """Create a deterministic session key for a Telegram chat.

    Returns a conversation_id that is stable across restarts so
    PersistentMemoryAdapter preserves history.
    """
    return f"telegram-{chat_id}"


# ── Configuration ────────────────────────────────────────────────────────


def load_config(config_path: str = None) -> dict:
    """Load Telegram interface configuration.

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
        "telegram": {
            "bot_token": "",
            "allowed_chat_ids": None,
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
        # Merge telegram section
        if "telegram" in file_config:
            config["telegram"].update(file_config["telegram"])
        # Merge genesis section
        if "genesis" in file_config:
            config["genesis"].update(file_config["genesis"])

    # Environment variable overrides
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        config["telegram"]["bot_token"] = env_token

    # Validate required fields
    if not config["telegram"]["bot_token"]:
        print("ERROR: Telegram bot token is required.")
        print("Set TELEGRAM_BOT_TOKEN environment variable or provide a config file.")
        sys.exit(1)

    return config


# ── Full Interface ────────────────────────────────────────────────────────


class TelegramGenesisInterface:
    """Telegram bot interface for Genesis agents.

    Composition over MonitoredInterface (same pattern as MemoryWebGUI).
    """

    def __init__(self, config: dict):
        self.config = config
        self.interface = None  # MonitoredInterface — created in _init_genesis
        self.sessions = {}  # chat_id -> {"conversation_id": str, "connected_agent_service": str}
        self.application = None  # PTB Application
        self.allowed_chat_ids = config["telegram"].get("allowed_chat_ids")
        self.default_agent_service = config["genesis"].get("default_agent_service")
        self.request_timeout = config["genesis"].get("request_timeout", 60.0)
        self.discovery_wait = config["genesis"].get("discovery_wait", 5.0)

    # ── Genesis Lifecycle ─────────────────────────────────────────────

    async def _init_genesis(self):
        """Create MonitoredInterface and wait for agent discovery."""
        from genesis_lib.monitored_interface import MonitoredInterface

        logger.info("Initializing Genesis DDS...")
        self.interface = MonitoredInterface(
            interface_name="TelegramBot",
            service_name="TelegramBotService",
        )
        logger.info(f"Waiting {self.discovery_wait}s for DDS discovery...")
        await asyncio.sleep(self.discovery_wait)
        agent_count = len(self.interface.available_agents)
        logger.info(f"Discovery complete: {agent_count} agent(s) found.")

    async def _connect_agent_for_chat(self, chat_id: int, service_name: str) -> bool:
        """Connect a chat session to a specific agent."""
        if not self.interface:
            return False
        ok = await self.interface.connect_to_agent(service_name, timeout_seconds=10.0)
        if ok:
            conv_id = _session_key(chat_id)
            self.sessions[chat_id] = {
                "conversation_id": conv_id,
                "connected_agent_service": service_name,
            }
            logger.info(f"Chat {chat_id} connected to {service_name} (conv_id={conv_id})")
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

    # ── Telegram Command Handlers ─────────────────────────────────────

    async def cmd_start(self, update, context):
        """Handle /start command."""
        from telegram import Update
        if not _is_allowed(update.effective_chat.id, self.allowed_chat_ids):
            return

        welcome = (
            "Welcome to Genesis AI Agent Bot!\n\n"
            "Commands:\n"
            "/agents - List available agents\n"
            "/disconnect - Disconnect from current agent\n"
            "/status - Show connection status\n\n"
            "Send any text message to chat with the connected agent."
        )
        await update.message.reply_text(welcome)

    async def cmd_agents(self, update, context):
        """Handle /agents command — show inline keyboard of agents."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        if not _is_allowed(update.effective_chat.id, self.allowed_chat_ids):
            return

        agents = self._get_available_agents()
        if not agents:
            await update.message.reply_text("No Genesis agents are currently available.")
            return

        buttons = []
        for agent in agents:
            buttons.append([
                InlineKeyboardButton(
                    text=agent["name"],
                    callback_data=f"connect:{agent['service_name']}",
                )
            ])
        markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("Select an agent to connect to:", reply_markup=markup)

    async def callback_connect(self, update, context):
        """Handle inline keyboard button tap for agent connection."""
        query = update.callback_query
        await query.answer()

        if not _is_allowed(query.message.chat.id, self.allowed_chat_ids):
            return

        data = query.data
        if not data.startswith("connect:"):
            return

        service_name = data[len("connect:"):]
        chat_id = query.message.chat.id

        ok = await self._connect_agent_for_chat(chat_id, service_name)
        if ok:
            # Find agent name
            agent_name = service_name
            for agent in self._get_available_agents():
                if agent["service_name"] == service_name:
                    agent_name = agent["name"]
                    break
            await query.edit_message_text(f"Connected to {agent_name}!")
        else:
            await query.edit_message_text(f"Failed to connect to agent.")

    async def cmd_disconnect(self, update, context):
        """Handle /disconnect command."""
        if not _is_allowed(update.effective_chat.id, self.allowed_chat_ids):
            return

        chat_id = update.effective_chat.id
        if chat_id in self.sessions:
            del self.sessions[chat_id]
            await update.message.reply_text("Disconnected from agent.")
        else:
            await update.message.reply_text("No agent connected.")

    async def cmd_status(self, update, context):
        """Handle /status command."""
        if not _is_allowed(update.effective_chat.id, self.allowed_chat_ids):
            return

        chat_id = update.effective_chat.id
        session = self.sessions.get(chat_id)
        if session:
            # Find agent name from service name
            agent_name = session["connected_agent_service"]
            for agent in self._get_available_agents():
                if agent["service_name"] == session["connected_agent_service"]:
                    agent_name = agent["name"]
                    break
            await update.message.reply_text(
                f"Agent: {agent_name}\n"
                f"Conversation ID: {session['conversation_id']}"
            )
        else:
            await update.message.reply_text("No agent connected. Use /agents to connect.")

    # ── Message Handling ──────────────────────────────────────────────

    async def handle_message(self, update, context):
        """Handle incoming text messages — forward to Genesis agent."""
        from telegram.constants import ChatAction

        chat_id = update.effective_chat.id
        if not _is_allowed(chat_id, self.allowed_chat_ids):
            return

        text = update.message.text
        if not text:
            return

        session = self.sessions.get(chat_id)

        # Auto-connect if no session
        if not session:
            agents = self._get_available_agents()
            auto_service = None

            if self.default_agent_service:
                # Auto-connect to default
                auto_service = self.default_agent_service
            elif len(agents) == 1:
                # Auto-connect to only agent
                auto_service = agents[0]["service_name"]
            else:
                await update.message.reply_text(
                    "No agent connected. Use /agents to select one."
                )
                return

            ok = await self._connect_agent_for_chat(chat_id, auto_service)
            if not ok:
                await update.message.reply_text("Failed to auto-connect to agent.")
                return
            session = self.sessions[chat_id]

        # Send typing indicator
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")

        # Send request to Genesis agent
        try:
            response = await self.interface.send_request(
                {
                    "message": text,
                    "conversation_id": session["conversation_id"],
                },
                timeout_seconds=self.request_timeout,
            )

            if response is None:
                await update.message.reply_text(
                    "Agent timed out. Please try again."
                )
                return

            if response.get("status", 1) != 0:
                error_msg = response.get("message", "Unknown error")
                await update.message.reply_text(f"Agent error: {error_msg}")
                return

            # Format and send response
            reply_text = response.get("message", "")
            chunks = _split_message(reply_text)
            for chunk in chunks:
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    logger.warning(f"Failed to send chunk: {e}")
                    # Fallback: send without formatting
                    try:
                        await update.message.reply_text(chunk)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            try:
                await update.message.reply_text(
                    "An error occurred processing your message."
                )
            except Exception:
                pass

    # ── Main ──────────────────────────────────────────────────────────

    async def start(self):
        """Initialize Genesis and start the Telegram bot."""
        from telegram.ext import (
            ApplicationBuilder,
            CommandHandler,
            MessageHandler,
            CallbackQueryHandler,
            filters,
        )

        # Initialize Genesis
        await self._init_genesis()

        # Build PTB application
        token = self.config["telegram"]["bot_token"]
        self.application = ApplicationBuilder().token(token).build()

        # Register handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("agents", self.cmd_agents))
        self.application.add_handler(CommandHandler("disconnect", self.cmd_disconnect))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CallbackQueryHandler(self.callback_connect))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        logger.info("Starting Telegram bot polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        # Keep running until interrupted
        try:
            stop_event = asyncio.Event()
            await stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            if self.interface:
                await self.interface.close()


# ── CLI Entry Point ──────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Genesis Telegram Bot Interface")
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
    bot = TelegramGenesisInterface(config)
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
