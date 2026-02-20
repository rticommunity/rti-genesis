#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 12 — Enterprise Pathway End-to-End Test

REQUIRES PostgreSQL: gated on GENESIS_TEST_PG_URL.

Tests:
- Same tests as local pathway but against PostgreSQL
- Multi-agent: two agents share one PostgreSQL DB
- Shared memory: Agent A publishes, Agent B retrieves
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

pg_url = os.environ.get("GENESIS_TEST_PG_URL")
if not pg_url:
    print("GENESIS_TEST_PG_URL not set — skipping enterprise pathway tests")
    sys.exit(0)

try:
    from genesis_lib.memory.sqlalchemy_backend import SQLAlchemyBackend
except ImportError:
    print("SQLAlchemy not installed — skipping enterprise pathway tests")
    sys.exit(0)

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


def cleanup(backend):
    from sqlalchemy import text
    with backend._engine.begin() as conn:
        conn.execute(text("DELETE FROM compaction_log WHERE agent_id LIKE 'e2e-pg-%'"))
        conn.execute(text("DELETE FROM shared_memories WHERE source_agent_id LIKE 'e2e-pg-%'"))
        conn.execute(text("DELETE FROM summaries WHERE agent_id LIKE 'e2e-pg-%'"))
        conn.execute(text("DELETE FROM messages WHERE agent_id LIKE 'e2e-pg-%'"))
        conn.execute(text("DELETE FROM memory_config WHERE agent_id LIKE 'e2e-pg-%' OR agent_id IS NULL"))
        conn.execute(text("DELETE FROM agents WHERE agent_id LIKE 'e2e-pg-%'"))


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST GATE 12: Enterprise Pathway E2E")
    print("=" * 60)

    backend = SQLAlchemyBackend(pg_url)
    backend.initialize_schema()

    try:
        # ── Basic persistence ───────────────────────────────────────
        adapter = PersistentMemoryAdapter(
            backend=backend, agent_id="e2e-pg-01", agent_name="PGAgent",
            conversation_id="e2e-pg-conv",
        )
        adapter.store("PG E2E message", metadata={"role": "user"})
        items = adapter.retrieve(k=10)
        check("pg: message persisted", len(items) == 1)

        # ── Multi-agent ─────────────────────────────────────────────
        adapter2 = PersistentMemoryAdapter(
            backend=backend, agent_id="e2e-pg-02", agent_name="PGAgent2",
            conversation_id="e2e-pg-conv2",
        )
        adapter2.store("PG agent 2 message", metadata={"role": "user"})

        items1 = adapter.retrieve(k=10)
        items2 = adapter2.retrieve(k=10)
        check("pg: multi-agent isolation", len(items1) == 1 and len(items2) == 1)

        # ── Shared memory ───────────────────────────────────────────
        adapter.share("PG shared from agent 1", namespace="pg-e2e")
        shared = adapter2.retrieve_shared(namespace="pg-e2e")
        check("pg: shared memory", len(shared) >= 1)

    finally:
        cleanup(backend)
        backend.close()

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
