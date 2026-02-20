#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Persistent Memory Agent Demo

Demonstrates a Genesis agent using PersistentMemoryAdapter:
- Conversation history persists across restarts
- Automatic compaction when context grows large
- Configurable local (SQLite) or enterprise (PostgreSQL) pathways

Usage:
    python persistent_memory_agent.py --config config/local_memory.json
    python persistent_memory_agent.py --config config/enterprise_memory.json
"""

import argparse
import asyncio
import os
import sys
import signal

# Ensure genesis_lib is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from genesis_lib.memory.persistent_adapter import PersistentMemoryAdapter


async def run_demo(config_path: str, agent_id: str):
    """Run a simple interactive demo with persistent memory."""

    print(f"Loading config from: {config_path}")
    adapter = PersistentMemoryAdapter.from_config(
        config_path, agent_id=agent_id, agent_name="PersistentMemoryDemo"
    )

    # Retrieve any prior conversation history
    prior = adapter.retrieve(k=10, policy="last_k")
    if prior:
        print(f"\n--- Prior conversation history ({len(prior)} items) ---")
        for item in prior:
            role = item["metadata"].get("role", "unknown")
            content = item["item"][:80]
            print(f"  [{role}] {content}")
        print("--- End prior history ---\n")
    else:
        print("\nNo prior conversation history found. Starting fresh.\n")

    print("Persistent Memory Agent Demo")
    print("Type messages to store them. They will persist across restarts.")
    print("Commands: /history, /compact, /share <msg>, /quit\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("Goodbye! Your conversation is saved.")
            break
        elif user_input == "/history":
            items = adapter.retrieve(k=20, policy="last_k")
            print(f"\n--- Conversation history ({len(items)} items) ---")
            for item in items:
                role = item["metadata"].get("role", "unknown")
                print(f"  [{role}] {item['item'][:100]}")
            print("---\n")
            continue
        elif user_input == "/compact":
            adapter.compact()
            print("Compaction triggered.\n")
            continue
        elif user_input.startswith("/share "):
            content = user_input[7:]
            adapter.share(content, namespace="demo")
            print(f"Shared: {content}\n")
            continue

        # Store user message
        adapter.store(user_input, metadata={"role": "user"})

        # Simulate assistant response
        response = f"I received your message: '{user_input[:50]}'. It has been persisted."
        adapter.store(response, metadata={"role": "assistant"})
        print(f"Assistant: {response}\n")


def main():
    parser = argparse.ArgumentParser(description="Persistent Memory Agent Demo")
    parser.add_argument(
        "--config",
        default="config/local_memory.json",
        help="Path to memory config JSON file",
    )
    parser.add_argument(
        "--agent-id",
        default="demo-agent-01",
        help="Agent identifier (stable across restarts)",
    )
    args = parser.parse_args()

    asyncio.run(run_demo(args.config, args.agent_id))


if __name__ == "__main__":
    main()
