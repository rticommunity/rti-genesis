#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 12 — Local Pathway End-to-End Test

Tests:
- Agent registers in DB via local config
- Messages persist across restart
- Compaction triggers on large conversations
- Expand recovers originals
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

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


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST GATE 12: Local Pathway E2E")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "e2e_local.db")
        config = {
            "storage": {"backend": "sqlite", "path": db_path},
            "compaction": {
                "model_context_window": 500,
                "soft_threshold_ratio": 0.3,
                "hard_threshold_ratio": 0.5,
                "chunk_size": 5,
                "recent_window_size": 5,
            },
            "retrieval": {"default_policy": "windowed", "default_k": 50},
            "tokenizer": {"type": "word_estimate"},
        }
        config_path = os.path.join(tmpdir, "local_config.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        # ── Start agent with local config ───────────────────────────
        adapter = PersistentMemoryAdapter.from_config(
            config_path, agent_id="e2e-agent", agent_name="E2EAgent"
        )
        check("agent registers via config", adapter._agent_id == "e2e-agent")

        # ── Send request → verify message persisted ─────────────────
        adapter.store("Hello from E2E test", metadata={"role": "user"})
        adapter.store("Response from agent", metadata={"role": "assistant"})
        items = adapter.retrieve(k=10, policy="last_k")
        check("messages persisted", len(items) == 2)

        # ── Kill and restart → verify prior conversation ────────────
        conv_id = adapter._conversation_id
        del adapter

        adapter2 = PersistentMemoryAdapter.from_config(
            config_path, agent_id="e2e-agent", agent_name="E2EAgent"
        )
        # Set the same conversation ID
        adapter2._conversation_id = conv_id
        items2 = adapter2.retrieve(k=10, policy="last_k")
        check("restart preserves history", len(items2) == 2)
        check("restart content correct", items2[0]["item"] == "Hello from E2E test")

        # ── Send many messages → verify compaction triggers ─────────
        for i in range(30):
            adapter2.store(
                f"Long message {i}. This is a detailed message with enough content to accumulate tokens.",
                metadata={"role": "user"},
            )

        adapter2.compact()
        all_sums = adapter2._backend.get_summaries(
            "e2e-agent", conv_id, state=None
        )
        check("compaction creates summaries", len(all_sums) > 0, f"got {len(all_sums)}")

        # ── Verify expand recovers originals ────────────────────────
        if all_sums:
            expanded = adapter2.expand(all_sums[0]["summary_id"])
            check("expand recovers originals", len(expanded) > 0)
        else:
            check("expand skipped (no summaries)", True)

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
