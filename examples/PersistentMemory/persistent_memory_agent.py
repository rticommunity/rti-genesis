#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
PersistentMemoryAgent — Genesis agent with database-backed conversation memory.

Extends MonitoredAgent (proper Genesis agent) and implements the abstract LLM
methods for the Anthropic Claude API. Uses PersistentMemoryAdapter as the
memory backend so conversation history survives restarts.

The full MonitoredAgent pipeline handles:
- DDS registration, discovery, and RPC
- State machine monitoring (READY -> BUSY -> READY)
- Graph topology publishing
- Chain event tracking
- Memory store/retrieve via the adapter

This agent implements the LLM provider interface:
- _call_llm() — Anthropic Messages API
- _format_messages() — Anthropic message format (system separate)
- _extract_text_response(), _extract_tool_calls(), etc.

Usage:
    python persistent_memory_agent.py --config config/local_memory.json
    python persistent_memory_agent.py --config config/enterprise_memory.json
"""

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.memory.persistent_adapter import PersistentMemoryAdapter

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful assistant with persistent memory. Your conversation "
    "history is stored in a database and survives across restarts. You can "
    "recall previous conversations naturally. Be concise and helpful."
)


class PersistentMemoryAgent(MonitoredAgent):
    """Genesis agent with persistent memory and Anthropic Claude backend.

    Follows the standard Genesis agent pattern:
    - MonitoredAgent handles process_request() with full monitoring
    - GenesisAgent handles memory.retrieve/store and orchestration
    - This class implements the 7 abstract LLM provider methods
    """

    def __init__(
        self,
        config_path="config/local_memory.json",
        agent_name="MemoryAgent",
        base_service_name="MemoryAgent",
        agent_id="memory-agent-01",
        model="claude-sonnet-4-20250514",
        domain_id=0,
        enable_agent_communication=True,
        **kwargs,
    ):
        self._config_path = config_path
        self._agent_id_config = agent_id
        self._model = model
        self._system_prompt = SYSTEM_PROMPT

        # Build PersistentMemoryAdapter BEFORE super().__init__
        adapter = PersistentMemoryAdapter.from_config(
            config_path, agent_id=agent_id, agent_name=agent_name,
        )

        # Verify Anthropic API key
        self._api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            logger.warning("ANTHROPIC_API_KEY not set — agent will echo instead of calling LLM")

        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_type="SPECIALIZED_AGENT",
            description="Agent with persistent database-backed memory",
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            memory_adapter=adapter,
            **kwargs,
        )

        # Advertise capabilities
        self.set_agent_capabilities(
            supported_tasks=["conversation", "memory-demo"],
            additional_capabilities={
                "specializations": ["persistent-memory", "conversation"],
                "capabilities": [
                    "persistent-history", "memory-compaction",
                    "shared-memory", "context-recall",
                ],
                "classification_tags": [
                    "memory", "conversation", "assistant", "demo",
                ],
                "model_info": {
                    "model": self._model,
                    "provider": "anthropic",
                    "persistent_memory": True,
                },
            },
        )

        # Log restored history
        prior = self.memory.retrieve(k=5, policy="last_k")
        if prior:
            logger.info(f"Restored {len(prior)} prior conversation items from persistent memory")

    def get_agent_capabilities(self):
        """Return capabilities dict for DDS advertisement during init."""
        return {
            "agent_type": "specialized",
            "specializations": ["persistent-memory", "conversation"],
            "capabilities": ["persistent-history", "memory-compaction", "shared-memory"],
            "classification_tags": ["memory", "conversation", "assistant"],
            "model_info": {"persistent_memory": True},
            "default_capable": False,
            "performance_metrics": None,
        }

    # ── LLM Provider Interface (7 abstract methods) ──────────────

    async def _call_llm(self, messages, tools=None, tool_choice="auto"):
        """Call Anthropic Claude Messages API."""
        # Extract last user message for echo fallback
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "").strip()
                break

        if not self._api_key:
            return {"text": f"[echo — no ANTHROPIC_API_KEY] {last_user_msg}"}

        try:
            import anthropic
        except ImportError:
            return {"text": f"[echo — anthropic not installed] {last_user_msg}"}

        # Separate system message from conversation (Anthropic format)
        system_text = self._system_prompt
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

        # Ensure proper message alternation (Claude API requirement)
        api_messages = self._fix_message_ordering(api_messages)

        try:
            client = anthropic.Anthropic(api_key=self._api_key)
            response = client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system_text,
                messages=api_messages,
            )
            return {"text": response.content[0].text, "_raw": response}
        except Exception as e:
            logger.error("Anthropic API error: %s", e)
            return {"text": f"[LLM error: {e}]"}

    def _format_messages(self, user_message, system_prompt, memory_items):
        """Format conversation history in Anthropic message format.

        Anthropic takes system prompt separately, so we include it as a
        system-role message for the pipeline, and extract it in _call_llm.
        """
        messages = [{"role": "system", "content": system_prompt or self._system_prompt}]

        for entry in memory_items:
            item = entry["item"]
            meta = entry.get("metadata", {})
            role = meta.get("role", "user")

            if role in ("tool", "assistant_tool"):
                continue
            if role not in ("user", "assistant"):
                role = "user"

            # Mark summaries from compaction
            if meta.get("is_summary"):
                item = f"[Summary of earlier conversation] {item}"

            messages.append({"role": role, "content": str(item)})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _extract_tool_calls(self, response):
        """No tool calling in this demo agent."""
        return None

    def _extract_text_response(self, response):
        """Extract text from our response dict."""
        if isinstance(response, dict):
            return response.get("text", "")
        return str(response)

    def _create_assistant_message(self, response):
        """Create assistant message for conversation history."""
        text = self._extract_text_response(response)
        return {"role": "assistant", "content": text}

    async def _get_tool_schemas(self):
        """No tools — pure conversation agent. Returns empty to use simple path."""
        return []

    def _get_tool_choice(self):
        return "none"

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _fix_message_ordering(messages):
        """Ensure messages alternate user/assistant (Claude API requirement)."""
        if not messages:
            return [{"role": "user", "content": "[conversation start]"}]
        fixed = []
        for msg in messages:
            if fixed and fixed[-1]["role"] == msg["role"]:
                fixed[-1]["content"] += "\n" + msg["content"]
            else:
                fixed.append(dict(msg))
        if fixed and fixed[0]["role"] != "user":
            fixed.insert(0, {"role": "user", "content": "[conversation resumed]"})
        return fixed

    async def close(self):
        await super().close()


# ── CLI entrypoint ───────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="PersistentMemoryAgent")
    parser.add_argument(
        "--config", default="config/local_memory.json",
        help="Path to memory config JSON file",
    )
    parser.add_argument(
        "--agent-id", default="memory-agent-01",
        help="Agent identifier (stable across restarts for memory continuity)",
    )
    parser.add_argument(
        "--agent-name", default="MemoryAgent",
        help="Agent display name",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-20250514",
        help="Anthropic model name",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    agent = PersistentMemoryAgent(
        config_path=args.config,
        agent_name=args.agent_name,
        agent_id=args.agent_id,
        model=args.model,
    )

    try:
        print(f"PersistentMemoryAgent '{args.agent_name}' running (agent_id={args.agent_id})")
        print(f"  Memory config: {args.config}")
        print(f"  Model: {args.model}")
        print("Press Ctrl+C to exit")
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print(f"\nShutting down {args.agent_name}...")
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
