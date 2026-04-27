#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 6 — Multi-Agent Shared Memory

Covers GWT Sections 05, 06:
- Two agents share DB, private messages isolated
- Agent A shares memory, Agent B retrieves it
- Broadcast vs targeted shared memory
- Namespace isolation
- Private messages never visible to other agents
- Cross-agent retrieval policy
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from genesis_lib.memory.sqlite_backend import SQLiteBackend
from genesis_lib.memory.persistent_adapter import PersistentMemoryAdapter

# ── Test infrastructure ──────────────────────────────────────────────
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


def run_shared_memory_tests(make_backend, label, tmpdir):
    """Run shared memory tests against a backend factory."""

    print(f"\n{'='*60}")
    print(f"  Shared memory tests: {label}")
    print(f"{'='*60}")

    db_path = os.path.join(tmpdir, f"{label}_shared.db")
    backend = make_backend(db_path)
    backend.initialize_schema()

    # Create two agents sharing the same backend
    agent_a = PersistentMemoryAdapter(
        backend=backend, agent_id="coding-01", agent_name="CodingAgent",
        conversation_id="conv-1",
    )
    agent_b = PersistentMemoryAdapter(
        backend=backend, agent_id="planning-01", agent_name="PlanningAgent",
        conversation_id="conv-1",
    )

    # ── Private messages isolated ───────────────────────────────────
    agent_a.store("refactored the auth module", metadata={"role": "assistant"})
    agent_b.store("sprint planning for week 12", metadata={"role": "assistant"})

    items_a = agent_a.retrieve(k=10)
    items_b = agent_b.retrieve(k=10)
    check(f"{label}: agent A sees own msg", len(items_a) == 1 and items_a[0]["item"] == "refactored the auth module")
    check(f"{label}: agent B sees own msg", len(items_b) == 1 and items_b[0]["item"] == "sprint planning for week 12")
    check(f"{label}: agent A doesn't see B", all("sprint" not in i["item"] for i in items_a))
    check(f"{label}: agent B doesn't see A", all("refactored" not in i["item"] for i in items_b))

    # ── Agent A shares, Agent B retrieves ───────────────────────────
    agent_a.share("auth module now uses JWT", namespace="project-alpha")
    shared_b = agent_b.retrieve_shared(namespace="project-alpha")
    check(f"{label}: B retrieves A's shared", len(shared_b) == 1)
    check(f"{label}: shared content correct", "JWT" in shared_b[0]["content"])
    check(f"{label}: shared source is A", shared_b[0]["source_agent_id"] == "coding-01")

    # ── Broadcast: visible to all agents ────────────────────────────
    # Register a third agent
    backend.register_agent("review-01", "ReviewAgent", "review")
    agent_c = PersistentMemoryAdapter(
        backend=backend, agent_id="review-01", agent_name="ReviewAgent",
        conversation_id="conv-1",
    )

    # The broadcast share from above should be visible to all
    shared_c = agent_c.retrieve_shared(namespace="project-alpha")
    check(f"{label}: broadcast visible to third agent", len(shared_c) == 1)

    # ── Targeted: visible only to target ────────────────────────────
    agent_a.share("secret for planning only", namespace="project-alpha", target_agent_id="planning-01")

    shared_b2 = agent_b.retrieve_shared(namespace="project-alpha")
    shared_c2 = agent_c.retrieve_shared(namespace="project-alpha")

    # B should see both (broadcast + targeted)
    check(f"{label}: targeted visible to target B", len(shared_b2) == 2)
    # C should see only the broadcast, not the targeted one
    check(
        f"{label}: targeted NOT visible to C",
        len(shared_c2) == 1 and shared_c2[0]["content"] == "auth module now uses JWT",
    )

    # ── Namespace isolation ─────────────────────────────────────────
    agent_a.share("finding A", namespace="project-alpha")
    agent_a.share("finding B", namespace="project-beta")

    shared_alpha = agent_b.retrieve_shared(namespace="project-alpha")
    shared_beta = agent_b.retrieve_shared(namespace="project-beta")

    alpha_contents = [s["content"] for s in shared_alpha]
    beta_contents = [s["content"] for s in shared_beta]

    check(f"{label}: ns isolation - alpha has finding A", "finding A" in alpha_contents)
    check(f"{label}: ns isolation - alpha no finding B", "finding B" not in alpha_contents)
    check(f"{label}: ns isolation - beta has finding B", "finding B" in beta_contents)
    check(f"{label}: ns isolation - beta no finding A", "finding A" not in beta_contents)

    # ── Private messages never visible via shared ───────────────────
    # Agent B should not see A's private conversation messages via shared memory
    shared_default = agent_b.retrieve_shared(namespace="default")
    private_in_shared = any(
        "refactored" in s["content"] for s in shared_default
    )
    check(f"{label}: private msgs not in shared", not private_in_shared)

    # ── Cross-agent retrieval policy ────────────────────────────────
    db_path2 = os.path.join(tmpdir, f"{label}_crossagent.db")
    backend2 = make_backend(db_path2)
    backend2.initialize_schema()

    xa = PersistentMemoryAdapter(
        backend=backend2, agent_id="x-agent-a", agent_name="XA",
        conversation_id="conv-x",
        retrieval_config={"default_policy": "cross_agent", "shared_namespaces": ["default"]},
    )
    xb = PersistentMemoryAdapter(
        backend=backend2, agent_id="x-agent-b", agent_name="XB",
        conversation_id="conv-x",
    )

    xa.store("my own message", metadata={"role": "user"})
    xb.share("shared from B", namespace="default")

    cross_items = xa.retrieve(k=10, policy="cross_agent")
    check(f"{label}: cross_agent includes own msg", any(i["item"] == "my own message" for i in cross_items))
    check(f"{label}: cross_agent includes shared", any(i["item"] == "shared from B" for i in cross_items))
    check(
        f"{label}: cross_agent shared before own",
        cross_items[0]["metadata"].get("role") == "shared",
        f"first item role: {cross_items[0]['metadata'].get('role')}",
    )


# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  TEST GATE 6: Multi-Agent Shared Memory")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Run against SQLiteBackend
        run_shared_memory_tests(
            lambda path: SQLiteBackend(path),
            "sqlite",
            tmpdir,
        )

        # Run against SQLAlchemyBackend
        try:
            from genesis_lib.memory.sqlalchemy_backend import SQLAlchemyBackend
            sa_dir = os.path.join(tmpdir, "sa")
            os.makedirs(sa_dir, exist_ok=True)
            run_shared_memory_tests(
                lambda path: SQLAlchemyBackend(f"sqlite:///{path}"),
                "sqlalchemy",
                sa_dir,
            )
        except ImportError:
            print("\n  SKIP: SQLAlchemy not installed, skipping sqlalchemy tests")

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    total = passed + len(failures)
    print(f"  Results: {passed}/{total} passed")
    if failures:
        print(f"  FAILURES:")
        for f in failures:
            print(f"    - {f}")
        sys.exit(1)
    else:
        print("  All tests passed!")
        sys.exit(0)
