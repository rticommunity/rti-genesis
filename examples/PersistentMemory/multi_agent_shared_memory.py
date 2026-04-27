#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Multi-Agent Shared Memory Demo

Demonstrates two agents sharing one database:
1. Agent A stores findings and shares them
2. Agent B retrieves Agent A's shared memories
3. Demonstrates namespace isolation

Usage:
    python multi_agent_shared_memory.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from genesis_lib.memory.sqlite_backend import SQLiteBackend
from genesis_lib.memory.persistent_adapter import PersistentMemoryAdapter


def main():
    print("=" * 60)
    print("  Multi-Agent Shared Memory Demo")
    print("=" * 60)

    # Use a temporary database for the demo
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "shared_memory.db")
        backend = SQLiteBackend(db_path)
        backend.initialize_schema()

        # Create two agents sharing the same backend
        coding_agent = PersistentMemoryAdapter(
            backend=backend,
            agent_id="coding-agent",
            agent_name="CodingAgent",
            conversation_id="coding-conv",
        )
        planning_agent = PersistentMemoryAdapter(
            backend=backend,
            agent_id="planning-agent",
            agent_name="PlanningAgent",
            conversation_id="planning-conv",
        )

        # Agent A stores private conversation
        print("\n--- CodingAgent stores private conversation ---")
        coding_agent.store("Refactored auth module to use JWT", metadata={"role": "assistant"})
        coding_agent.store("Fixed SQL injection in user search", metadata={"role": "assistant"})
        print("  Stored 2 private messages")

        # Agent A shares a finding
        print("\n--- CodingAgent shares findings ---")
        coding_agent.share(
            "Auth module refactored to use JWT. New entry: src/auth/jwt_handler.py",
            namespace="project-alpha",
        )
        coding_agent.share(
            "SQL injection fix applied to user search endpoint",
            namespace="project-alpha",
        )
        coding_agent.share(
            "Performance report: API latency reduced 40%",
            namespace="project-beta",
        )
        print("  Shared 2 findings in project-alpha, 1 in project-beta")

        # Agent B retrieves shared memories
        print("\n--- PlanningAgent retrieves shared memories ---")
        alpha_shared = planning_agent.retrieve_shared(namespace="project-alpha")
        print(f"  project-alpha: {len(alpha_shared)} shared memories")
        for s in alpha_shared:
            print(f"    [{s['source_agent_id']}] {s['content'][:70]}")

        beta_shared = planning_agent.retrieve_shared(namespace="project-beta")
        print(f"  project-beta: {len(beta_shared)} shared memories")
        for s in beta_shared:
            print(f"    [{s['source_agent_id']}] {s['content'][:70]}")

        # Verify isolation
        print("\n--- Verifying isolation ---")
        planning_msgs = planning_agent.retrieve(k=10)
        print(f"  PlanningAgent private messages: {len(planning_msgs)}")
        coding_msgs = coding_agent.retrieve(k=10)
        print(f"  CodingAgent private messages: {len(coding_msgs)}")

        # Cross-agent retrieval
        print("\n--- Cross-agent retrieval ---")
        cross = planning_agent.retrieve(
            k=10, policy="cross_agent"
        )
        shared_items = [i for i in cross if i["metadata"].get("role") == "shared"]
        own_items = [i for i in cross if i["metadata"].get("role") != "shared"]
        print(f"  PlanningAgent cross-agent: {len(shared_items)} shared + {len(own_items)} own")

    print("\n" + "=" * 60)
    print("  Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
