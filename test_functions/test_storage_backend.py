#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 1+2 — StorageBackend (SQLite) + Tokenizer

Covers GWT Sections 01, 03, 05, 08:
- Schema creation is idempotent
- register_agent creates/updates entries
- insert_message / get_messages CRUD
- Multi-agent isolation
- WAL mode, foreign keys
- Tokenizer word estimate and pluggable factory
"""

import os
import sys
import tempfile

# Ensure genesis_lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from genesis_lib.memory.sqlite_backend import SQLiteBackend
from genesis_lib.memory.tokenizer import (
    WordEstimateTokenizer,
    TiktokenTokenizer,
    create_tokenizer,
)

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


def run_backend_tests(backend, label):
    """Run all backend tests against the given backend instance."""
    global passed

    print(f"\n{'='*60}")
    print(f"  Backend: {label}")
    print(f"{'='*60}")

    # ── Schema creation is idempotent ───────────────────────────────
    backend.initialize_schema()
    backend.initialize_schema()  # second call must not raise
    check(f"{label}: schema idempotent", True)

    # ── register_agent creates entry ────────────────────────────────
    backend.register_agent("agent-01", "TestAgent", "general")
    backend.register_agent("agent-01", "TestAgent", "general")  # upsert
    check(f"{label}: register_agent upsert", True)

    # ── insert_message and get_messages ─────────────────────────────
    mid1 = backend.insert_message(
        "agent-01", "conv-1", "user", "Hello world", 3, {"key": "val"}, sequence=1
    )
    mid2 = backend.insert_message(
        "agent-01", "conv-1", "assistant", "Hi there", 3, None, sequence=2
    )
    check(f"{label}: insert_message returns ids", mid1 is not None and mid2 is not None)

    msgs = backend.get_messages("agent-01", "conv-1")
    check(f"{label}: get_messages returns 2", len(msgs) == 2)
    check(
        f"{label}: messages in chronological order",
        msgs[0]["content"] == "Hello world" and msgs[1]["content"] == "Hi there",
    )
    check(
        f"{label}: message has role metadata",
        msgs[0]["role"] == "user" and msgs[1]["role"] == "assistant",
    )
    check(
        f"{label}: sequence numbers monotonic",
        msgs[0]["sequence"] < msgs[1]["sequence"],
    )

    # ── get_message_by_id ───────────────────────────────────────────
    msg = backend.get_message_by_id(mid1)
    check(f"{label}: get_message_by_id", msg is not None and msg["content"] == "Hello world")

    # ── get_token_count ─────────────────────────────────────────────
    tc = backend.get_token_count("agent-01", "conv-1")
    check(f"{label}: get_token_count", tc == 6, f"expected 6, got {tc}")

    # ── get_next_sequence ───────────────────────────────────────────
    nxt = backend.get_next_sequence("agent-01", "conv-1")
    check(f"{label}: get_next_sequence", nxt == 3, f"expected 3, got {nxt}")

    # ── Multi-agent isolation ───────────────────────────────────────
    backend.register_agent("agent-02", "OtherAgent", "coding")
    backend.insert_message("agent-02", "conv-1", "user", "Secret from B", 4, sequence=1)
    msgs_a = backend.get_messages("agent-01", "conv-1")
    msgs_b = backend.get_messages("agent-02", "conv-1")
    check(f"{label}: agent isolation - A sees own", len(msgs_a) == 2)
    check(f"{label}: agent isolation - B sees own", len(msgs_b) == 1)
    check(
        f"{label}: agent isolation - B content",
        msgs_b[0]["content"] == "Secret from B",
    )

    # ── Multiple conversations scoped correctly ─────────────────────
    backend.insert_message("agent-01", "conv-2", "user", "Different convo", 3, sequence=1)
    msgs_c1 = backend.get_messages("agent-01", "conv-1")
    msgs_c2 = backend.get_messages("agent-01", "conv-2")
    check(f"{label}: conversation scoping - conv-1", len(msgs_c1) == 2)
    check(f"{label}: conversation scoping - conv-2", len(msgs_c2) == 1)

    # ── since_sequence filter ───────────────────────────────────────
    msgs_since = backend.get_messages("agent-01", "conv-1", since_sequence=2)
    check(f"{label}: since_sequence filter", len(msgs_since) == 1 and msgs_since[0]["sequence"] == 2)

    # ── limit filter ────────────────────────────────────────────────
    msgs_lim = backend.get_messages("agent-01", "conv-1", limit=1)
    check(f"{label}: limit filter", len(msgs_lim) == 1)

    # ── Summaries ───────────────────────────────────────────────────
    sid = backend.insert_summary(
        "agent-01", "conv-1", level=1,
        content="Summary of msgs 1-2", token_count=5,
        span_start_seq=1, span_end_seq=2, child_ids=None,
    )
    check(f"{label}: insert_summary returns id", sid is not None)

    sums = backend.get_summaries("agent-01", "conv-1")
    check(f"{label}: get_summaries returns 1", len(sums) == 1)
    check(f"{label}: summary content", sums[0]["content"] == "Summary of msgs 1-2")
    check(f"{label}: summary span", sums[0]["span_start_seq"] == 1 and sums[0]["span_end_seq"] == 2)

    backend.update_summary_state(sid, "superseded")
    sums_active = backend.get_summaries("agent-01", "conv-1", state="active")
    sums_super = backend.get_summaries("agent-01", "conv-1", state="superseded")
    check(f"{label}: update_summary_state - no active", len(sums_active) == 0)
    check(f"{label}: update_summary_state - superseded", len(sums_super) == 1)

    # ── Shared memory ──────────────────────────────────────────────
    backend.insert_shared_memory("agent-01", "shared finding", namespace="project-x")
    shared = backend.get_shared_memories("agent-02", namespace="project-x")
    check(f"{label}: broadcast shared memory visible", len(shared) == 1)
    check(f"{label}: shared memory content", shared[0]["content"] == "shared finding")

    # Targeted shared memory
    backend.insert_shared_memory(
        "agent-01", "targeted to B", target_agent_id="agent-02", namespace="project-x"
    )
    shared_b = backend.get_shared_memories("agent-02", namespace="project-x")
    check(f"{label}: targeted shared visible to target", len(shared_b) == 2)

    # Agent-03 shouldn't see targeted memory for agent-02
    backend.register_agent("agent-03", "ThirdAgent")
    shared_c = backend.get_shared_memories("agent-03", namespace="project-x")
    # agent-03 sees only the broadcast, not the one targeted to agent-02
    check(
        f"{label}: targeted shared NOT visible to others",
        len(shared_c) == 1 and shared_c[0]["content"] == "shared finding",
    )

    # ── Compaction log ─────────────────────────────────────────────
    backend.insert_compaction_log(
        "agent-01", "conv-1",
        level=1, messages_before=10, tokens_before=1000,
        tokens_after=200, summaries_created=2,
        strategy="llm_summarize", duration_ms=500,
    )
    check(f"{label}: insert_compaction_log", True)

    # ── Config ─────────────────────────────────────────────────────
    backend.set_config("compaction.chunk_size", "15")
    backend.set_config("compaction.chunk_size", "10", agent_id="agent-01")
    global_cfg = backend.get_config()
    agent_cfg = backend.get_config(agent_id="agent-01")
    check(f"{label}: global config", global_cfg.get("compaction.chunk_size") == "15")
    check(
        f"{label}: agent config overrides global",
        agent_cfg.get("compaction.chunk_size") == "10",
    )


def run_sqlite_specific_tests(db_path):
    """Tests specific to SQLiteBackend (WAL mode, foreign keys)."""
    import sqlite3

    print(f"\n{'='*60}")
    print("  SQLite-specific tests")
    print(f"{'='*60}")

    conn = sqlite3.connect(db_path)
    jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
    check("sqlite: WAL mode", jm == "wal", f"got {jm}")

    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    # Note: foreign_keys PRAGMA is per-connection, so this new connection
    # won't have it set. We verify it in the backend's connection instead.
    conn.close()

    # Verify via backend
    backend = SQLiteBackend(db_path)
    fk_val = backend._conn.execute("PRAGMA foreign_keys").fetchone()[0]
    check("sqlite: foreign_keys=ON", fk_val == 1, f"got {fk_val}")
    backend.close()


def run_tokenizer_tests():
    """Test Gate 2 — Tokenizer tests. Covers GWT Section 08."""

    print(f"\n{'='*60}")
    print("  Tokenizer tests")
    print(f"{'='*60}")

    # WordEstimateTokenizer
    tok = WordEstimateTokenizer()
    count = tok.count("Hello world this is a test")
    check("tokenizer: word estimate returns > 0", count > 0, f"got {count}")
    check("tokenizer: word estimate consistent", tok.count("Hello world") == tok.count("Hello world"))
    check("tokenizer: empty string returns 0", tok.count("") == 0)

    # Ratio correctness: 6 words * 1.3 = 7.8 → ceil = 8
    count6 = tok.count("one two three four five six")
    check("tokenizer: word estimate ratio", count6 == 8, f"expected 8, got {count6}")

    # Factory: word_estimate
    tok2 = create_tokenizer({"type": "word_estimate"})
    check("tokenizer: factory word_estimate", isinstance(tok2, WordEstimateTokenizer))

    # Factory: default (no config)
    tok3 = create_tokenizer()
    check("tokenizer: factory default", isinstance(tok3, WordEstimateTokenizer))

    # Factory: tiktoken (optional)
    try:
        import tiktoken
        tok4 = create_tokenizer({"type": "tiktoken", "model": "gpt-4"})
        check("tokenizer: tiktoken available", isinstance(tok4, TiktokenTokenizer))
        tc = tok4.count("Hello world")
        check("tokenizer: tiktoken count > 0", tc > 0, f"got {tc}")
    except ImportError:
        print("  SKIP: tiktoken not installed, skipping tiktoken tests")

    # Factory: unknown type
    try:
        create_tokenizer({"type": "unknown_type"})
        check("tokenizer: unknown type raises", False, "no exception raised")
    except ValueError:
        check("tokenizer: unknown type raises", True)


# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  TEST GATE 1+2+5: StorageBackend + Tokenizer + Dual-Pathway")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_sqlite.db")

        # Run backend tests against SQLiteBackend
        sqlite_db = SQLiteBackend(db_path)
        sqlite_db.initialize_schema()
        run_backend_tests(sqlite_db, "sqlite")
        sqlite_db.close()

        # SQLite-specific tests
        run_sqlite_specific_tests(db_path)

        # Run backend tests against SQLAlchemyBackend (pointed at SQLite)
        try:
            from genesis_lib.memory.sqlalchemy_backend import SQLAlchemyBackend
            sa_db_path = os.path.join(tmpdir, "test_sa.db")
            sa_db = SQLAlchemyBackend(f"sqlite:///{sa_db_path}")
            sa_db.initialize_schema()
            run_backend_tests(sa_db, "sqlalchemy")
            sa_db.close()
        except ImportError:
            print("\n  SKIP: SQLAlchemy not installed, skipping sqlalchemy backend tests")

    # Tokenizer tests
    run_tokenizer_tests()

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
