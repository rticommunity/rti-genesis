#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 11 — Optional PostgreSQL Integration Tests

Gated on GENESIS_TEST_PG_URL environment variable. Covers GWT Section 16:
Runs the full test suite against a real PostgreSQL instance.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Gate: skip if no PostgreSQL URL ──────────────────────────────────
pg_url = os.environ.get("GENESIS_TEST_PG_URL")
if not pg_url:
    print("GENESIS_TEST_PG_URL not set — skipping PostgreSQL tests")
    sys.exit(0)

try:
    from genesis_lib.memory.sqlalchemy_backend import SQLAlchemyBackend
except ImportError:
    print("SQLAlchemy not installed — skipping PostgreSQL tests")
    sys.exit(0)

from genesis_lib.memory.persistent_adapter import PersistentMemoryAdapter
from genesis_lib.memory.tokenizer import WordEstimateTokenizer

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


def cleanup_test_data(backend):
    """Remove test data from PostgreSQL."""
    from sqlalchemy import text
    with backend._engine.begin() as conn:
        conn.execute(text("DELETE FROM compaction_log WHERE agent_id LIKE 'pg-test-%'"))
        conn.execute(text("DELETE FROM shared_memories WHERE source_agent_id LIKE 'pg-test-%'"))
        conn.execute(text("DELETE FROM summaries WHERE agent_id LIKE 'pg-test-%'"))
        conn.execute(text("DELETE FROM messages WHERE agent_id LIKE 'pg-test-%'"))
        conn.execute(text("DELETE FROM memory_config WHERE agent_id LIKE 'pg-test-%'"))
        conn.execute(text("DELETE FROM agents WHERE agent_id LIKE 'pg-test-%'"))


if __name__ == "__main__":
    print("=" * 60)
    print(f"  TEST GATE 11: PostgreSQL Integration ({pg_url[:30]}...)")
    print("=" * 60)

    backend = SQLAlchemyBackend(pg_url)
    backend.initialize_schema()

    try:
        # ── Backend basics ──────────────────────────────────────────
        backend.register_agent("pg-test-01", "PGTestAgent", "test")
        backend.register_agent("pg-test-01", "PGTestAgent", "test")  # upsert
        check("pg: register_agent", True)

        mid = backend.insert_message(
            "pg-test-01", "pg-conv-1", "user", "Hello PG", 3, sequence=1
        )
        check("pg: insert_message", mid is not None)

        msgs = backend.get_messages("pg-test-01", "pg-conv-1")
        check("pg: get_messages", len(msgs) == 1 and msgs[0]["content"] == "Hello PG")

        # ── Adapter ─────────────────────────────────────────────────
        adapter = PersistentMemoryAdapter(
            backend=backend, agent_id="pg-test-02", agent_name="PGAdapter",
            conversation_id="pg-conv-2",
        )
        adapter.store("PG persistence test", metadata={"role": "user"})
        items = adapter.retrieve(k=10)
        check("pg: adapter store/retrieve", len(items) == 1)

        # ── Shared memory ───────────────────────────────────────────
        adapter.share("PG shared finding", namespace="pg-ns")
        adapter2 = PersistentMemoryAdapter(
            backend=backend, agent_id="pg-test-03", agent_name="PGReader",
            conversation_id="pg-conv-3",
        )
        shared = adapter2.retrieve_shared(namespace="pg-ns")
        check("pg: shared memory cross-agent", len(shared) >= 1)

        # ── Multi-agent isolation ───────────────────────────────────
        items2 = adapter2.retrieve(k=10)
        check("pg: multi-agent isolation", len(items2) == 0)

        # ── Config ──────────────────────────────────────────────────
        backend.set_config("pg.test.key", "pg_value", agent_id="pg-test-01")
        cfg = backend.get_config(agent_id="pg-test-01")
        check("pg: config set/get", cfg.get("pg.test.key") == "pg_value")

    finally:
        cleanup_test_data(backend)
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
