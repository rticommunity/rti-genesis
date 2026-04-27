#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

"""
Compaction Engine — Three-level escalation for context management.

Level 1: LLM Summarization (or configurable summarizer)
Level 2: Summary-of-Summaries
Level 3: Deterministic Truncation (no LLM, guarantees convergence)
"""

import re
import time
from typing import Callable, List, Optional

from .storage_backend import StorageBackend
from .tokenizer import TokenizerBase


def _default_summarizer(messages: List[str]) -> str:
    """Default extractive summarizer for testing — takes first sentence of each message."""
    sentences = []
    for msg in messages:
        # Extract first sentence
        match = re.match(r'^[^.!?\n]+[.!?]?', msg.strip())
        if match:
            sentences.append(match.group(0).strip())
        elif msg.strip():
            # Take first 100 chars if no sentence boundary
            sentences.append(msg.strip()[:100])
    return " ".join(sentences)


def _deterministic_extract(summaries: List[str]) -> str:
    """Level 3 deterministic extraction. No LLM. Guarantees convergence.

    Extracts:
    - First sentence of each summary
    - File paths (regex)
    - Error messages
    """
    parts = []
    for s in summaries:
        # First sentence
        match = re.match(r'^[^.!?\n]+[.!?]?', s.strip())
        if match:
            parts.append(match.group(0).strip())

        # File paths
        paths = re.findall(r'[\w/\\]+\.(?:py|js|ts|json|yaml|yml|md|txt|sql|sh|cfg)', s)
        for p in paths:
            if p not in parts:
                parts.append(p)

        # Error patterns
        errors = re.findall(r'(?:Error|Exception|FAIL|error|failed)[^\n.]*', s)
        for e in errors:
            short = e.strip()[:100]
            if short not in parts:
                parts.append(short)

    return " | ".join(parts) if parts else "Session digest"


class CompactionEngine:
    """Three-level compaction engine for context management."""

    def __init__(
        self,
        backend: StorageBackend,
        tokenizer: TokenizerBase,
        config: dict = None,
        summarizer: Callable[[List[str]], str] = None,
        monitoring_callback: Callable = None,
    ):
        self._backend = backend
        self._tokenizer = tokenizer
        self._config = config or {}
        self._summarizer = summarizer or _default_summarizer
        self._monitoring_callback = monitoring_callback

        # Thresholds
        self._context_window = self._config.get("model_context_window", 200000)
        self._soft_ratio = self._config.get("soft_threshold_ratio", 0.6)
        self._hard_ratio = self._config.get("hard_threshold_ratio", 0.85)
        self._soft_threshold = int(self._context_window * self._soft_ratio)
        self._hard_threshold = int(self._context_window * self._hard_ratio)
        self._recent_window = self._config.get("recent_window_size", 20)
        self._chunk_size = self._config.get("chunk_size", 15)

    def needs_compaction(self, agent_id: str, conversation_id: str) -> bool:
        """Check if compaction is needed based on token budget."""
        total = self._get_active_token_count(agent_id, conversation_id)
        return total > self._hard_threshold

    def compact(self, agent_id: str, conversation_id: str) -> dict:
        """Run compaction with three-level escalation.

        Returns dict with compaction results.
        """
        start = time.time()
        tokens_before = self._get_active_token_count(agent_id, conversation_id)

        if tokens_before <= self._soft_threshold:
            return {"level": 0, "action": "none", "tokens_before": tokens_before, "tokens_after": tokens_before}

        # Level 1 — Summarize raw messages
        result = self._level1_summarize(agent_id, conversation_id)
        tokens_after = self._get_active_token_count(agent_id, conversation_id)

        if tokens_after <= self._hard_threshold:
            duration_ms = int((time.time() - start) * 1000)
            self._log_compaction(agent_id, conversation_id, 1, tokens_before, tokens_after, result["summaries_created"], "llm_summarize", duration_ms)
            return {"level": 1, "action": "summarize", "tokens_before": tokens_before, "tokens_after": tokens_after, "summaries_created": result["summaries_created"]}

        # Level 2 — Summary-of-summaries
        result2 = self._level2_summarize(agent_id, conversation_id)
        tokens_after = self._get_active_token_count(agent_id, conversation_id)

        if tokens_after <= self._hard_threshold:
            duration_ms = int((time.time() - start) * 1000)
            self._log_compaction(agent_id, conversation_id, 2, tokens_before, tokens_after, result2["summaries_created"], "llm_summarize", duration_ms)
            return {"level": 2, "action": "summary_of_summaries", "tokens_before": tokens_before, "tokens_after": tokens_after, "summaries_created": result2["summaries_created"]}

        # Level 3 — Deterministic truncation
        result3 = self._level3_truncate(agent_id, conversation_id)
        tokens_after = self._get_active_token_count(agent_id, conversation_id)
        duration_ms = int((time.time() - start) * 1000)
        self._log_compaction(agent_id, conversation_id, 3, tokens_before, tokens_after, result3["summaries_created"], "truncate", duration_ms)

        if self._monitoring_callback:
            self._monitoring_callback("memory_compact", {
                "agent_id": agent_id,
                "level": 3,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "duration_ms": duration_ms,
            })

        return {"level": 3, "action": "truncate", "tokens_before": tokens_before, "tokens_after": tokens_after, "summaries_created": result3["summaries_created"]}

    def _level1_summarize(self, agent_id: str, conversation_id: str) -> dict:
        """Level 1: Group consecutive messages and summarize each chunk."""
        msgs = self._backend.get_messages(agent_id, conversation_id)
        if not msgs:
            return {"summaries_created": 0}

        # Get existing L1 summaries to find what's already covered
        existing = self._backend.get_summaries(agent_id, conversation_id, level=1)
        covered_seqs = set()
        for s in existing:
            for seq in range(s["span_start_seq"], s["span_end_seq"] + 1):
                covered_seqs.add(seq)

        # Exclude recent window from summarization
        if len(msgs) > self._recent_window:
            eligible = msgs[:-self._recent_window]
        else:
            return {"summaries_created": 0}

        # Filter to uncovered messages
        uncovered = [m for m in eligible if m["sequence"] not in covered_seqs]
        if not uncovered:
            return {"summaries_created": 0}

        # Group into chunks
        summaries_created = 0
        for i in range(0, len(uncovered), self._chunk_size):
            chunk = uncovered[i:i + self._chunk_size]
            if not chunk:
                continue

            texts = [m["content"] for m in chunk]
            summary_text = self._summarizer(texts)
            token_count = self._tokenizer.count(summary_text)

            span_start = chunk[0]["sequence"]
            span_end = chunk[-1]["sequence"]

            self._backend.insert_summary(
                agent_id=agent_id,
                conversation_id=conversation_id,
                level=1,
                content=summary_text,
                token_count=token_count,
                span_start_seq=span_start,
                span_end_seq=span_end,
            )
            summaries_created += 1

        return {"summaries_created": summaries_created}

    def _level2_summarize(self, agent_id: str, conversation_id: str) -> dict:
        """Level 2: Summarize Level-1 summaries into larger spans."""
        l1_summaries = self._backend.get_summaries(agent_id, conversation_id, level=1, state="active")
        if len(l1_summaries) < 2:
            return {"summaries_created": 0}

        summaries_created = 0
        # Group L1 summaries into chunks
        for i in range(0, len(l1_summaries), self._chunk_size):
            chunk = l1_summaries[i:i + self._chunk_size]
            if len(chunk) < 2:
                continue

            texts = [s["content"] for s in chunk]
            summary_text = self._summarizer(texts)
            token_count = self._tokenizer.count(summary_text)

            span_start = chunk[0]["span_start_seq"]
            span_end = chunk[-1]["span_end_seq"]
            child_ids = [s["summary_id"] for s in chunk]

            self._backend.insert_summary(
                agent_id=agent_id,
                conversation_id=conversation_id,
                level=2,
                content=summary_text,
                token_count=token_count,
                span_start_seq=span_start,
                span_end_seq=span_end,
                child_ids=child_ids,
            )
            summaries_created += 1

            # Mark L1 children as superseded
            for s in chunk:
                self._backend.update_summary_state(s["summary_id"], "superseded")

        return {"summaries_created": summaries_created}

    def _level3_truncate(self, agent_id: str, conversation_id: str) -> dict:
        """Level 3: Deterministic extraction. No LLM. Guarantees convergence."""
        # Get all active summaries
        active = self._backend.get_summaries(agent_id, conversation_id, state="active")
        if not active:
            return {"summaries_created": 0}

        texts = [s["content"] for s in active]
        digest = _deterministic_extract(texts)
        token_count = self._tokenizer.count(digest)

        # Find total span
        span_start = min(s["span_start_seq"] for s in active)
        span_end = max(s["span_end_seq"] for s in active)
        child_ids = [s["summary_id"] for s in active]

        # Create L3 summary
        self._backend.insert_summary(
            agent_id=agent_id,
            conversation_id=conversation_id,
            level=3,
            content=digest,
            token_count=token_count,
            span_start_seq=span_start,
            span_end_seq=span_end,
            child_ids=child_ids,
        )

        # Mark all previous active summaries as superseded
        for s in active:
            self._backend.update_summary_state(s["summary_id"], "superseded")

        return {"summaries_created": 1}

    def _get_active_token_count(self, agent_id: str, conversation_id: str) -> int:
        """Calculate the active context token count (summaries + recent raw)."""
        msgs = self._backend.get_messages(agent_id, conversation_id)
        if not msgs:
            return 0

        # Get active summaries
        active_summaries = self._backend.get_summaries(agent_id, conversation_id, state="active")

        # Determine which message sequences are covered by summaries
        covered_seqs = set()
        summary_tokens = 0
        for s in active_summaries:
            for seq in range(s["span_start_seq"], s["span_end_seq"] + 1):
                covered_seqs.add(seq)
            summary_tokens += (s.get("token_count") or 0)

        # Recent window messages (always raw)
        recent = msgs[-self._recent_window:] if len(msgs) > self._recent_window else msgs
        recent_seqs = set(m["sequence"] for m in recent)

        # Raw messages: those not covered by summaries and not in recent window
        raw_tokens = 0
        for m in msgs:
            if m["sequence"] not in covered_seqs or m["sequence"] in recent_seqs:
                if m["sequence"] not in recent_seqs:
                    raw_tokens += (m.get("token_count") or 0)

        # Recent tokens
        recent_tokens = sum(m.get("token_count") or 0 for m in recent)

        return summary_tokens + raw_tokens + recent_tokens

    def _log_compaction(self, agent_id, conversation_id, level, tokens_before, tokens_after, summaries_created, strategy, duration_ms):
        """Log compaction to the audit table."""
        msgs = self._backend.get_messages(agent_id, conversation_id)
        self._backend.insert_compaction_log(
            agent_id, conversation_id,
            level=level,
            messages_before=len(msgs),
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            summaries_created=summaries_created,
            strategy=strategy,
            duration_ms=duration_ms,
        )

        if self._monitoring_callback:
            self._monitoring_callback("memory_compact", {
                "agent_id": agent_id,
                "level": level,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "duration_ms": duration_ms,
            })
