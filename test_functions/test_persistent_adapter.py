#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 3+4 — PersistentMemoryAdapter + Config

Covers GWT Sections 01, 02, 03, 07, 13:
- Store and retrieve round-trip
- Items include original text verbatim and role metadata
- Sequence numbers monotonic
- Restart persistence
- MemoryAdapter compatibility
- last_k retrieval policy
- Config file loading, env var, defaults
"""

import json
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


def run_adapter_tests(make_backend, label, tmpdir):
    """Run adapter tests against a backend factory."""

    print(f"\n{'='*60}")
    print(f"  Adapter tests: {label}")
    print(f"{'='*60}")

    # ── Store and retrieve round-trip ───────────────────────────────
    db_path = os.path.join(tmpdir, f"{label}_roundtrip.db")
    backend = make_backend(db_path)
    backend.initialize_schema()
    adapter = PersistentMemoryAdapter(
        backend=backend, agent_id="test-01", agent_name="TestAgent",
        conversation_id="conv-1",
    )

    adapter.store("Hello world", metadata={"role": "user"})
    adapter.store("Hi there", metadata={"role": "assistant"})

    items = adapter.retrieve(k=10)
    check(f"{label}: store/retrieve round-trip count", len(items) == 2, f"got {len(items)}")
    check(
        f"{label}: original text verbatim",
        items[0]["item"] == "Hello world" and items[1]["item"] == "Hi there",
    )
    check(
        f"{label}: role metadata preserved",
        items[0]["metadata"]["role"] == "user"
        and items[1]["metadata"]["role"] == "assistant",
    )

    # ── Sequence numbers monotonic ──────────────────────────────────
    msgs = backend.get_messages("test-01", "conv-1")
    seqs = [m["sequence"] for m in msgs]
    check(
        f"{label}: sequence numbers monotonic",
        all(seqs[i] < seqs[i + 1] for i in range(len(seqs) - 1)),
        f"sequences: {seqs}",
    )

    # ── Restart persistence ─────────────────────────────────────────
    db_path2 = os.path.join(tmpdir, f"{label}_restart.db")
    backend1 = make_backend(db_path2)
    backend1.initialize_schema()
    a1 = PersistentMemoryAdapter(
        backend=backend1, agent_id="persist-agent", agent_name="PA",
        conversation_id="conv-restart",
    )
    a1.store("msg1", metadata={"role": "user"})
    a1.store("msg2", metadata={"role": "assistant"})

    # Simulate restart — create new backend and adapter with same DB
    del a1
    if hasattr(backend1, 'close'):
        backend1.close()

    backend2 = make_backend(db_path2)
    backend2.initialize_schema()
    a2 = PersistentMemoryAdapter(
        backend=backend2, agent_id="persist-agent", agent_name="PA",
        conversation_id="conv-restart",
    )
    items2 = a2.retrieve(k=10)
    check(f"{label}: restart persistence count", len(items2) == 2, f"got {len(items2)}")
    check(
        f"{label}: restart persistence content",
        items2[0]["item"] == "msg1" and items2[1]["item"] == "msg2",
    )
    if hasattr(backend2, 'close'):
        backend2.close()

    # ── MemoryAdapter compatibility ─────────────────────────────────
    db_path3 = os.path.join(tmpdir, f"{label}_compat.db")
    backend3 = make_backend(db_path3)
    backend3.initialize_schema()
    adapter3 = PersistentMemoryAdapter(
        backend=backend3, agent_id="compat-agent", agent_name="CA",
    )
    # store() and retrieve() signatures match SimpleMemoryAdapter
    adapter3.store("test item")
    adapter3.store("test item 2", metadata={"role": "assistant"})
    result = adapter3.retrieve()
    check(f"{label}: store/retrieve compat signatures", len(result) == 2)

    # summarize, promote, prune should not raise NotImplementedError
    try:
        adapter3.summarize()
        adapter3.promote("some_id")
        adapter3.prune()
        check(f"{label}: MemoryAdapter methods don't raise", True)
    except NotImplementedError:
        check(f"{label}: MemoryAdapter methods don't raise", False, "raised NotImplementedError")

    # ── retrieve(k=10) returns last 10 in chronological order ───────
    db_path4 = os.path.join(tmpdir, f"{label}_lastk.db")
    backend4 = make_backend(db_path4)
    backend4.initialize_schema()
    adapter4 = PersistentMemoryAdapter(
        backend=backend4, agent_id="lastk-agent", agent_name="LK",
        conversation_id="conv-lastk",
    )
    for i in range(20):
        adapter4.store(f"msg-{i}", metadata={"role": "user"})

    last10 = adapter4.retrieve(k=10)
    check(f"{label}: last_k returns 10", len(last10) == 10, f"got {len(last10)}")
    check(
        f"{label}: last_k chronological order",
        last10[0]["item"] == "msg-10" and last10[-1]["item"] == "msg-19",
        f"first={last10[0]['item']}, last={last10[-1]['item']}",
    )

    # ── Empty retrieve returns empty list ───────────────────────────
    db_path5 = os.path.join(tmpdir, f"{label}_empty.db")
    backend5 = make_backend(db_path5)
    backend5.initialize_schema()
    adapter5 = PersistentMemoryAdapter(
        backend=backend5, agent_id="empty-agent", agent_name="EA",
    )
    empty = adapter5.retrieve(k=10)
    check(f"{label}: empty retrieve", len(empty) == 0)

    # ── Multiple conversations scoped ───────────────────────────────
    db_path6 = os.path.join(tmpdir, f"{label}_multiconv.db")
    backend6 = make_backend(db_path6)
    backend6.initialize_schema()
    a_conv1 = PersistentMemoryAdapter(
        backend=backend6, agent_id="mc-agent", agent_name="MC",
        conversation_id="conv-A",
    )
    a_conv2 = PersistentMemoryAdapter(
        backend=backend6, agent_id="mc-agent", agent_name="MC",
        conversation_id="conv-B",
    )
    a_conv1.store("in conv A", metadata={"role": "user"})
    a_conv2.store("in conv B", metadata={"role": "user"})

    items_a = a_conv1.retrieve(k=10)
    items_b = a_conv2.retrieve(k=10)
    check(f"{label}: conversation scoping A", len(items_a) == 1 and items_a[0]["item"] == "in conv A")
    check(f"{label}: conversation scoping B", len(items_b) == 1 and items_b[0]["item"] == "in conv B")


def run_config_tests(tmpdir):
    """Test Gate 4 — Config tests. Covers GWT Section 13."""

    print(f"\n{'='*60}")
    print("  Config tests")
    print(f"{'='*60}")

    # ── from_config loads SQLite backend ────────────────────────────
    config = {
        "storage": {
            "backend": "sqlite",
            "path": os.path.join(tmpdir, "config_test.db"),
        },
        "compaction": {
            "soft_threshold_ratio": 0.5,
            "hard_threshold_ratio": 0.8,
            "model_context_window": 100000,
        },
        "retrieval": {
            "default_policy": "windowed",
            "default_k": 30,
        },
        "tokenizer": {
            "type": "word_estimate",
        },
    }
    config_path = os.path.join(tmpdir, "test_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)

    adapter = PersistentMemoryAdapter.from_config(
        config_path, agent_id="config-agent", agent_name="ConfigAgent"
    )
    check("config: from_config loads", adapter is not None)
    check(
        "config: compaction thresholds from file",
        adapter._compaction_config["soft_threshold_ratio"] == 0.5
        and adapter._compaction_config["hard_threshold_ratio"] == 0.8,
    )
    check(
        "config: retrieval policy from file",
        adapter._retrieval_config["default_policy"] == "windowed",
    )

    # Verify adapter works
    adapter.store("config test msg", metadata={"role": "user"})
    items = adapter.retrieve(k=5, policy="last_k")
    check("config: adapter functional after from_config", len(items) == 1)

    # ── from_env loads from GENESIS_MEMORY_CONFIG env var ───────────
    os.environ["GENESIS_MEMORY_CONFIG"] = config_path
    try:
        adapter_env = PersistentMemoryAdapter.from_env(
            agent_id="env-agent", agent_name="EnvAgent"
        )
        check("config: from_env loads", adapter_env is not None)
    finally:
        del os.environ["GENESIS_MEMORY_CONFIG"]

    # ── Direct constructor with db_path uses defaults ───────────────
    db_path = os.path.join(tmpdir, "direct_test.db")
    adapter_direct = PersistentMemoryAdapter(
        db_path=db_path, agent_id="direct-agent", agent_name="DirectAgent"
    )
    check(
        "config: direct constructor defaults",
        adapter_direct._compaction_config["soft_threshold_ratio"] == 0.6,
    )

    # ── Per-agent DB config overrides ───────────────────────────────
    adapter_direct._backend.set_config(
        "compaction.chunk_size", "10", agent_id="direct-agent"
    )
    agent_cfg = adapter_direct._backend.get_config(agent_id="direct-agent")
    check(
        "config: per-agent DB override",
        agent_cfg.get("compaction.chunk_size") == "10",
    )

    # ── Missing config file raises clear error ──────────────────────
    try:
        PersistentMemoryAdapter.from_config("/nonexistent/path.json")
        check("config: missing file raises", False, "no exception raised")
    except (FileNotFoundError, OSError):
        check("config: missing file raises", True)

    # ── Default values when optional fields omitted ─────────────────
    minimal_config = {"storage": {"backend": "sqlite", "path": os.path.join(tmpdir, "minimal.db")}}
    min_path = os.path.join(tmpdir, "minimal_config.json")
    with open(min_path, "w") as f:
        json.dump(minimal_config, f)

    adapter_min = PersistentMemoryAdapter.from_config(
        min_path, agent_id="min-agent", agent_name="MinAgent"
    )
    check(
        "config: defaults for omitted fields",
        adapter_min._compaction_config["soft_threshold_ratio"] == 0.6
        and adapter_min._retrieval_config["default_k"] == 50,
    )


# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  TEST GATE 3+4+5: PersistentMemoryAdapter + Config + Dual-Pathway")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Run adapter tests against SQLiteBackend
        run_adapter_tests(
            lambda path: SQLiteBackend(path),
            "sqlite",
            tmpdir,
        )

        # Run adapter tests against SQLAlchemyBackend
        try:
            from genesis_lib.memory.sqlalchemy_backend import SQLAlchemyBackend
            sa_dir = os.path.join(tmpdir, "sa")
            os.makedirs(sa_dir, exist_ok=True)
            run_adapter_tests(
                lambda path: SQLAlchemyBackend(f"sqlite:///{path}"),
                "sqlalchemy",
                sa_dir,
            )
        except ImportError:
            print("\n  SKIP: SQLAlchemy not installed, skipping sqlalchemy adapter tests")

        # Run config tests
        run_config_tests(tmpdir)

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
