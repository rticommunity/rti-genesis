#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 9 — Monitoring Integration

Covers GWT Section 15:
- Compact emits monitoring event with token counts and duration
- Share emits monitoring event
- Event format matches existing monitoring patterns
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


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST GATE 9: Monitoring Integration")
    print("=" * 60)

    events = []

    def capture_event(event_type, metadata):
        events.append({"type": event_type, "metadata": metadata})

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "monitor_test.db")
        backend = SQLiteBackend(db_path)
        backend.initialize_schema()

        adapter = PersistentMemoryAdapter(
            backend=backend,
            agent_id="monitor-agent",
            agent_name="MonitorAgent",
            conversation_id="conv-1",
            monitoring_callback=capture_event,
            compaction_config={
                "model_context_window": 300,
                "soft_threshold_ratio": 0.1,
                "hard_threshold_ratio": 0.2,
                "chunk_size": 5,
                "recent_window_size": 3,
            },
        )

        # ── Share emits monitoring event ────────────────────────────
        events.clear()
        adapter.share("shared finding", namespace="project-x")
        share_events = [e for e in events if e["type"] == "memory_share"]
        check("share emits monitoring event", len(share_events) == 1)
        if share_events:
            check(
                "share event has source_agent_id",
                share_events[0]["metadata"].get("source_agent_id") == "monitor-agent",
            )
            check(
                "share event has namespace",
                share_events[0]["metadata"].get("namespace") == "project-x",
            )

        # ── Compact emits monitoring event ──────────────────────────
        events.clear()
        # Store enough to trigger compaction
        for i in range(30):
            adapter.store(
                f"Message {i}. Detailed content about topic {i} with enough words to generate tokens.",
                metadata={"role": "user"},
            )

        adapter.compact()
        compact_events = [e for e in events if e["type"] == "memory_compact"]
        check("compact emits monitoring event", len(compact_events) > 0, f"got {len(compact_events)}")
        if compact_events:
            meta = compact_events[0]["metadata"]
            check("compact event has tokens_before", "tokens_before" in meta)
            check("compact event has tokens_after", "tokens_after" in meta)
            check("compact event has duration_ms", "duration_ms" in meta)
            check("compact event has level", "level" in meta)

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
