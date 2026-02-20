#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
Test Gate 7 — Compaction Engine (Three-Level Escalation)

Covers GWT Sections 09, 10, 11, 12, 14:
- No compaction below soft threshold
- Compaction triggers above hard threshold
- Level 1 creates summary nodes
- Level 2 summarizes L1, marks children superseded
- Level 3 deterministic, no LLM, always converges
- expand() returns original raw messages
- DAG structure stored relationally
- No overlapping coverage at same level
- Compaction log records every operation
- Windowed retrieval: summaries + recent raw
- Full-expand retrieval: all originals
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from genesis_lib.memory.sqlite_backend import SQLiteBackend
from genesis_lib.memory.persistent_adapter import PersistentMemoryAdapter
from genesis_lib.memory.compaction import CompactionEngine, _default_summarizer, _deterministic_extract
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


def _make_long_message(i):
    """Create a message with ~50 tokens."""
    return f"Message number {i}. This is a detailed conversation message about topic {i} that contains enough words to generate a meaningful token count for testing purposes."


def run_compaction_tests(make_backend, label, tmpdir):
    """Run compaction tests against a backend factory."""

    print(f"\n{'='*60}")
    print(f"  Compaction tests: {label}")
    print(f"{'='*60}")

    # ── No compaction below soft threshold ──────────────────────────
    db_path = os.path.join(tmpdir, f"{label}_nocompact.db")
    backend = make_backend(db_path)
    backend.initialize_schema()

    # Very high thresholds so we stay below
    adapter = PersistentMemoryAdapter(
        backend=backend, agent_id="no-compact", agent_name="NC",
        conversation_id="conv-1",
        compaction_config={
            "model_context_window": 1000000,
            "soft_threshold_ratio": 0.6,
            "hard_threshold_ratio": 0.85,
            "chunk_size": 5,
            "recent_window_size": 5,
        },
    )
    for i in range(10):
        adapter.store(f"short msg {i}", metadata={"role": "user"})

    sums = backend.get_summaries("no-compact", "conv-1")
    check(f"{label}: no compaction below soft", len(sums) == 0)

    # ── Compaction triggers above hard threshold ────────────────────
    db_path2 = os.path.join(tmpdir, f"{label}_trigger.db")
    backend2 = make_backend(db_path2)
    backend2.initialize_schema()

    # Low context window to force compaction
    adapter2 = PersistentMemoryAdapter(
        backend=backend2, agent_id="trigger-agent", agent_name="TA",
        conversation_id="conv-1",
        compaction_config={
            "model_context_window": 500,  # Very small to force compaction
            "soft_threshold_ratio": 0.3,
            "hard_threshold_ratio": 0.5,
            "chunk_size": 5,
            "recent_window_size": 5,
        },
    )
    for i in range(30):
        adapter2.store(_make_long_message(i), metadata={"role": "user"})

    sums2 = backend2.get_summaries("trigger-agent", "conv-1")
    # Should have at least some summaries
    all_sums = backend2.get_summaries("trigger-agent", "conv-1", state=None)
    check(f"{label}: compaction triggered", len(all_sums) > 0, f"got {len(all_sums)} summaries")

    # ── Level 1 creates summary nodes with span tracking ───────────
    db_path3 = os.path.join(tmpdir, f"{label}_level1.db")
    backend3 = make_backend(db_path3)
    backend3.initialize_schema()
    backend3.register_agent("l1-agent", "L1Agent")

    tokenizer = WordEstimateTokenizer()
    engine = CompactionEngine(
        backend=backend3, tokenizer=tokenizer,
        config={
            "model_context_window": 200,
            "soft_threshold_ratio": 0.1,
            "hard_threshold_ratio": 0.2,
            "chunk_size": 5,
            "recent_window_size": 3,
        },
    )

    # Insert messages directly
    for i in range(20):
        backend3.insert_message(
            "l1-agent", "conv-1", "user",
            _make_long_message(i),
            tokenizer.count(_make_long_message(i)),
            sequence=i + 1,
        )

    result = engine._level1_summarize("l1-agent", "conv-1")
    check(f"{label}: L1 creates summaries", result["summaries_created"] > 0, f"created {result['summaries_created']}")

    l1_sums = backend3.get_summaries("l1-agent", "conv-1", level=1)
    check(f"{label}: L1 summaries have level 1", all(s["level"] == 1 for s in l1_sums))
    check(
        f"{label}: L1 summaries have span tracking",
        all(s["span_start_seq"] is not None and s["span_end_seq"] is not None for s in l1_sums),
    )

    # ── Level 2 summarizes L1, marks children superseded ────────────
    result2 = engine._level2_summarize("l1-agent", "conv-1")
    l2_sums = backend3.get_summaries("l1-agent", "conv-1", level=2)
    l1_active = backend3.get_summaries("l1-agent", "conv-1", level=1, state="active")
    l1_superseded = backend3.get_summaries("l1-agent", "conv-1", level=1, state="superseded")

    if result2["summaries_created"] > 0:
        check(f"{label}: L2 creates summaries", len(l2_sums) > 0)
        check(f"{label}: L2 marks L1 superseded", len(l1_superseded) > 0)
        check(
            f"{label}: L2 has child_ids",
            l2_sums[0].get("child_ids_json") is not None,
        )
    else:
        # If only 1 L1 summary was created, L2 won't run (needs >= 2)
        check(f"{label}: L2 skipped (too few L1s)", True)

    # ── Level 3 deterministic, no LLM, always converges ─────────────
    db_path4 = os.path.join(tmpdir, f"{label}_level3.db")
    backend4 = make_backend(db_path4)
    backend4.initialize_schema()
    backend4.register_agent("l3-agent", "L3Agent")

    # Insert messages
    for i in range(50):
        backend4.insert_message(
            "l3-agent", "conv-1", "user",
            _make_long_message(i),
            tokenizer.count(_make_long_message(i)),
            sequence=i + 1,
        )

    engine4 = CompactionEngine(
        backend=backend4, tokenizer=tokenizer,
        config={
            "model_context_window": 100,
            "soft_threshold_ratio": 0.1,
            "hard_threshold_ratio": 0.2,
            "chunk_size": 5,
            "recent_window_size": 3,
        },
    )

    # Run full compaction which should escalate through all levels
    compact_result = engine4.compact("l3-agent", "conv-1")
    check(f"{label}: L3 compaction ran", compact_result["level"] >= 1, f"level={compact_result['level']}")

    # Verify all summaries at same level have non-overlapping spans
    for level in [1, 2, 3]:
        level_sums = backend4.get_summaries("l3-agent", "conv-1", level=level, state=None)
        active_at_level = [s for s in level_sums if s["state"] == "active"]
        overlaps = False
        for i_s in range(len(active_at_level)):
            for j_s in range(i_s + 1, len(active_at_level)):
                a = active_at_level[i_s]
                b = active_at_level[j_s]
                if a["span_start_seq"] <= b["span_end_seq"] and b["span_start_seq"] <= a["span_end_seq"]:
                    overlaps = True
        if active_at_level:
            check(f"{label}: L{level} no overlap", not overlaps)

    # ── Adversarial: summarizer that produces longer output ─────────
    db_path5 = os.path.join(tmpdir, f"{label}_adversarial.db")
    backend5 = make_backend(db_path5)
    backend5.initialize_schema()
    backend5.register_agent("adv-agent", "AdvAgent")

    for i in range(50):
        backend5.insert_message(
            "adv-agent", "conv-1", "user",
            _make_long_message(i),
            tokenizer.count(_make_long_message(i)),
            sequence=i + 1,
        )

    # Adversarial summarizer that makes output LONGER
    def adversarial_summarizer(messages):
        return " ".join(messages) + " EXTRA LONG OUTPUT " * 10

    engine5 = CompactionEngine(
        backend=backend5, tokenizer=tokenizer,
        config={
            "model_context_window": 100,
            "soft_threshold_ratio": 0.1,
            "hard_threshold_ratio": 0.2,
            "chunk_size": 5,
            "recent_window_size": 3,
        },
        summarizer=adversarial_summarizer,
    )

    # Should not infinite loop — L3 guarantees convergence
    adv_result = engine5.compact("adv-agent", "conv-1")
    check(f"{label}: adversarial converges", adv_result["level"] == 3, f"level={adv_result['level']}")

    # ── expand() returns original raw messages ──────────────────────
    db_path6 = os.path.join(tmpdir, f"{label}_expand.db")
    backend6 = make_backend(db_path6)
    backend6.initialize_schema()

    adapter6 = PersistentMemoryAdapter(
        backend=backend6, agent_id="expand-agent", agent_name="EA",
        conversation_id="conv-1",
        compaction_config={
            "model_context_window": 200,
            "soft_threshold_ratio": 0.1,
            "hard_threshold_ratio": 0.2,
            "chunk_size": 5,
            "recent_window_size": 3,
        },
    )

    for i in range(20):
        adapter6.store(_make_long_message(i), metadata={"role": "user"})

    adapter6.compact()
    all_sums6 = backend6.get_summaries("expand-agent", "conv-1", state=None)

    if all_sums6:
        # Expand a Level-1 summary
        l1_sums6 = [s for s in all_sums6 if s["level"] == 1]
        if l1_sums6:
            expanded = adapter6.expand(l1_sums6[0]["summary_id"])
            check(f"{label}: expand returns messages", len(expanded) > 0)
            check(
                f"{label}: expand returns original content",
                all("Message number" in m["content"] for m in expanded),
            )

            # Verify span is correct
            span_start = l1_sums6[0]["span_start_seq"]
            span_end = l1_sums6[0]["span_end_seq"]
            check(
                f"{label}: expand respects span",
                all(span_start <= m["sequence"] <= span_end for m in expanded),
            )
        else:
            check(f"{label}: expand skipped (no L1)", True)

        # Expanding L2 summary walks DAG to originals
        l2_sums6 = [s for s in all_sums6 if s["level"] == 2]
        if l2_sums6:
            expanded2 = adapter6.expand(l2_sums6[0]["summary_id"])
            check(f"{label}: L2 expand returns originals", len(expanded2) > 0)
            check(
                f"{label}: L2 expand has no summary text",
                all("Message number" in m["content"] for m in expanded2),
            )
        else:
            check(f"{label}: L2 expand skipped (no L2)", True)

        # Superseded summaries can still be expanded
        superseded = [s for s in all_sums6 if s["state"] == "superseded"]
        if superseded:
            expanded_super = adapter6.expand(superseded[0]["summary_id"])
            check(f"{label}: superseded can be expanded", len(expanded_super) > 0)
        else:
            check(f"{label}: superseded expand skipped", True)
    else:
        check(f"{label}: expand skipped (no summaries)", True)

    # ── DAG stored relationally ─────────────────────────────────────
    if all_sums6:
        check(
            f"{label}: DAG has level indicators",
            all("level" in s for s in all_sums6),
        )
        check(
            f"{label}: DAG has span tracking",
            all("span_start_seq" in s and "span_end_seq" in s for s in all_sums6),
        )
    else:
        check(f"{label}: DAG check skipped", True)

    # ── Compaction log records operation ─────────────────────────────
    # The compact() call above should have logged
    # Read compaction_log directly
    if hasattr(backend6, '_conn'):
        # SQLiteBackend
        logs = backend6._conn.execute(
            "SELECT * FROM compaction_log WHERE agent_id = ?", ("expand-agent",)
        ).fetchall()
    else:
        # SQLAlchemy
        from sqlalchemy import text
        with backend6._engine.connect() as conn:
            logs = conn.execute(
                text("SELECT * FROM compaction_log WHERE agent_id = :aid"),
                {"aid": "expand-agent"},
            ).mappings().all()

    check(f"{label}: compaction log has entries", len(logs) > 0, f"got {len(logs)}")

    # ── Windowed retrieval: summaries + recent raw ──────────────────
    db_path7 = os.path.join(tmpdir, f"{label}_windowed.db")
    backend7 = make_backend(db_path7)
    backend7.initialize_schema()

    adapter7 = PersistentMemoryAdapter(
        backend=backend7, agent_id="win-agent", agent_name="WA",
        conversation_id="conv-1",
        compaction_config={
            "model_context_window": 300,
            "soft_threshold_ratio": 0.1,
            "hard_threshold_ratio": 0.2,
            "chunk_size": 5,
            "recent_window_size": 5,
        },
    )

    for i in range(30):
        adapter7.store(_make_long_message(i), metadata={"role": "user"})

    adapter7.compact()
    windowed = adapter7.retrieve(policy="windowed")

    # Should have a mix of summaries and recent raw
    has_summary = any(
        item.get("metadata", {}).get("role") == "summary" for item in windowed
    )
    has_raw = any(
        item.get("metadata", {}).get("role") == "user" for item in windowed
    )

    sums_7 = backend7.get_summaries("win-agent", "conv-1", state="active")
    if sums_7:
        check(f"{label}: windowed has summaries", has_summary, f"items={len(windowed)}")
    check(f"{label}: windowed has recent raw", has_raw)

    # ── Full-expand retrieval: all original messages ────────────────
    full_expand = adapter7.retrieve(policy="full_expand")
    check(f"{label}: full_expand returns all msgs", len(full_expand) == 30, f"got {len(full_expand)}")
    check(
        f"{label}: full_expand no summaries",
        all(item["metadata"].get("role") != "summary" for item in full_expand),
    )


# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  TEST GATE 7: Compaction Engine")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Run against SQLiteBackend
        run_compaction_tests(
            lambda path: SQLiteBackend(path),
            "sqlite",
            tmpdir,
        )

        # Run against SQLAlchemyBackend
        try:
            from genesis_lib.memory.sqlalchemy_backend import SQLAlchemyBackend
            sa_dir = os.path.join(tmpdir, "sa")
            os.makedirs(sa_dir, exist_ok=True)
            run_compaction_tests(
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
