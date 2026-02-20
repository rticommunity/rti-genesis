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
PersistentMemoryAdapter — Database-backed MemoryAdapter implementation.

Drop-in replacement for SimpleMemoryAdapter. Provides:
- Restart-persistent storage via StorageBackend
- Multi-agent shared memory
- Compaction engine (wired in Step 7)
- Configurable retrieval policies
"""

import os
import uuid

from .base import MemoryAdapter
from .storage_backend import StorageBackend
from .sqlite_backend import SQLiteBackend
from .tokenizer import create_tokenizer


class PersistentMemoryAdapter(MemoryAdapter):
    """Database-backed memory adapter implementing the MemoryAdapter interface."""

    def __init__(
        self,
        backend: StorageBackend = None,
        agent_id: str = None,
        agent_name: str = None,
        agent_type: str = "",
        conversation_id: str = None,
        db_path: str = None,
        tokenizer_config: dict = None,
        compaction_config: dict = None,
        retrieval_config: dict = None,
        monitoring_callback=None,
    ):
        """Initialize the persistent memory adapter.

        Args:
            backend: StorageBackend instance. If None, creates SQLiteBackend from db_path.
            agent_id: Unique agent identifier. Auto-generated if None.
            agent_name: Human-readable agent name.
            agent_type: Agent type (e.g., "coding", "planning").
            conversation_id: Current conversation ID. Auto-generated if None.
            db_path: Path to SQLite database (used if backend is None).
            tokenizer_config: Config dict for tokenizer factory.
            compaction_config: Config dict for compaction engine.
            retrieval_config: Config dict for retrieval policies.
            monitoring_callback: Optional callable(event_type, metadata) for monitoring.
        """
        if backend is None:
            if db_path is None:
                db_path = os.path.join(os.getcwd(), "genesis_memory.db")
            backend = SQLiteBackend(db_path)
            backend.initialize_schema()

        self._backend = backend
        self._agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self._agent_name = agent_name or self._agent_id
        self._agent_type = agent_type
        self._conversation_id = conversation_id or f"conv-{uuid.uuid4().hex[:8]}"
        self._tokenizer = create_tokenizer(tokenizer_config)
        self._monitoring_callback = monitoring_callback

        # Compaction config (defaults)
        self._compaction_config = {
            "soft_threshold_ratio": 0.6,
            "hard_threshold_ratio": 0.85,
            "model_context_window": 200000,
            "recent_window_size": 20,
            "chunk_size": 15,
        }
        if compaction_config:
            self._compaction_config.update(compaction_config)

        # Retrieval config (defaults)
        self._retrieval_config = {
            "default_policy": "last_k",
            "default_k": 50,
        }
        if retrieval_config:
            self._retrieval_config.update(retrieval_config)

        # Compaction engine
        from .compaction import CompactionEngine
        self._compaction_engine = CompactionEngine(
            backend=self._backend,
            tokenizer=self._tokenizer,
            config=self._compaction_config,
            monitoring_callback=self._monitoring_callback,
        )

        # Register agent
        self._backend.register_agent(self._agent_id, self._agent_name, self._agent_type)

    def store(self, item, metadata=None):
        """Store an item to persistent memory.

        Args:
            item: The content to store (string).
            metadata: Optional dict with 'role' and other metadata.
        """
        role = "user"
        if metadata and isinstance(metadata, dict):
            role = metadata.get("role", "user")

        token_count = self._tokenizer.count(str(item))
        sequence = self._backend.get_next_sequence(self._agent_id, self._conversation_id)

        self._backend.insert_message(
            agent_id=self._agent_id,
            conversation_id=self._conversation_id,
            role=role,
            content=str(item),
            token_count=token_count,
            metadata=metadata,
            sequence=sequence,
        )

        # Check if compaction is needed (wired in Step 7)
        if self._compaction_engine:
            total_tokens = self._backend.get_token_count(
                self._agent_id, self._conversation_id
            )
            hard = (
                self._compaction_config["hard_threshold_ratio"]
                * self._compaction_config["model_context_window"]
            )
            if total_tokens > hard:
                self._compaction_engine.compact(
                    self._agent_id, self._conversation_id
                )

    def retrieve(self, query=None, k=100, policy=None):
        """Retrieve items from persistent memory.

        Args:
            query: Unused (for interface compatibility).
            k: Number of items to retrieve.
            policy: Retrieval policy ('last_k', 'windowed', 'full_expand', 'cross_agent').

        Returns:
            List of dicts with 'item' and 'metadata' keys (matching SimpleMemoryAdapter format).
        """
        if policy is None:
            policy = self._retrieval_config.get("default_policy", "last_k")

        if policy == "last_k":
            return self._retrieve_last_k(k)
        elif policy == "windowed":
            return self._retrieve_windowed(k)
        elif policy == "full_expand":
            return self._retrieve_full_expand()
        elif policy == "cross_agent":
            return self._retrieve_cross_agent(k)
        else:
            return self._retrieve_last_k(k)

    def _retrieve_last_k(self, k):
        """Retrieve last k raw messages."""
        msgs = self._backend.get_messages(
            self._agent_id, self._conversation_id
        )
        # Take last k messages
        recent = msgs[-k:] if k and len(msgs) > k else msgs
        return [self._msg_to_adapter_format(m) for m in recent]

    def _retrieve_windowed(self, k):
        """Retrieve summaries + recent raw messages.

        Returns summaries for older content + last N raw messages.
        """
        recent_window = self._compaction_config.get("recent_window_size", 20)
        msgs = self._backend.get_messages(self._agent_id, self._conversation_id)

        if not msgs:
            return []

        # Get recent raw messages
        recent_msgs = msgs[-recent_window:] if len(msgs) > recent_window else msgs
        recent_start_seq = recent_msgs[0]["sequence"] if recent_msgs else 0

        # Get active summaries for older messages
        summaries = self._backend.get_summaries(
            self._agent_id, self._conversation_id, state="active"
        )

        # Filter summaries to those covering messages before the recent window
        older_summaries = [
            s for s in summaries if s["span_end_seq"] < recent_start_seq
        ]

        result = []
        # Add summaries first (chronological by span)
        for s in older_summaries:
            result.append({
                "item": s["content"],
                "metadata": {
                    "role": "summary",
                    "summary_id": s["summary_id"],
                    "level": s["level"],
                    "span_start_seq": s["span_start_seq"],
                    "span_end_seq": s["span_end_seq"],
                },
            })

        # If no summaries cover older messages, include raw messages up to k
        if not older_summaries and len(msgs) > recent_window:
            older_msgs = msgs[:-recent_window]
            # If total would exceed k, take last k worth
            max_older = max(0, k - recent_window) if k else len(older_msgs)
            for m in older_msgs[-max_older:]:
                result.append(self._msg_to_adapter_format(m))

        # Add recent raw messages
        for m in recent_msgs:
            result.append(self._msg_to_adapter_format(m))

        return result

    def _retrieve_full_expand(self):
        """Retrieve all original messages (no summaries)."""
        msgs = self._backend.get_messages(self._agent_id, self._conversation_id)
        return [self._msg_to_adapter_format(m) for m in msgs]

    def _retrieve_cross_agent(self, k):
        """Retrieve own messages + shared memories from other agents."""
        result = []

        # Get shared memories first
        shared_ns = self._retrieval_config.get("shared_namespaces", ["default"])
        for ns in shared_ns:
            shared = self._backend.get_shared_memories(
                self._agent_id, namespace=ns
            )
            for s in shared:
                result.append({
                    "item": s["content"],
                    "metadata": {
                        "role": "shared",
                        "source_agent_id": s["source_agent_id"],
                        "namespace": s["namespace"],
                    },
                })

        # Then own messages
        own = self._retrieve_last_k(k)
        result.extend(own)
        return result

    def expand(self, summary_id):
        """Expand a summary back to its original raw messages.

        Args:
            summary_id: The summary to expand.

        Returns:
            List of original message dicts.
        """
        # Get the summary to find its span
        summaries = self._backend.get_summaries(
            self._agent_id, self._conversation_id, state=None
        )
        summary = None
        for s in summaries:
            if s["summary_id"] == summary_id:
                summary = s
                break

        if summary is None:
            return []

        # Retrieve the original messages in the span
        msgs = self._backend.get_messages(
            agent_id=self._agent_id,
            conversation_id=self._conversation_id,
            since_sequence=summary["span_start_seq"],
        )
        # Filter to only those within the span
        return [
            m for m in msgs
            if m["sequence"] <= summary["span_end_seq"]
        ]

    def compact(self):
        """Manually trigger compaction."""
        if self._compaction_engine:
            self._compaction_engine.compact(self._agent_id, self._conversation_id)

    def share(self, content, namespace="default", target_agent_id=None):
        """Publish a shared memory for other agents.

        Args:
            content: The content to share.
            namespace: Topic namespace for the shared memory.
            target_agent_id: Specific target agent, or None for broadcast.
        """
        token_count = self._tokenizer.count(str(content))
        self._backend.insert_shared_memory(
            source_agent_id=self._agent_id,
            content=str(content),
            target_agent_id=target_agent_id,
            namespace=namespace,
            token_count=token_count,
        )
        if self._monitoring_callback:
            self._monitoring_callback("memory_share", {
                "source_agent_id": self._agent_id,
                "target_agent_id": target_agent_id,
                "namespace": namespace,
            })

    def retrieve_shared(self, namespace="default", limit=50):
        """Retrieve shared memories from other agents.

        Args:
            namespace: Topic namespace to query.
            limit: Maximum number of shared memories.

        Returns:
            List of shared memory dicts.
        """
        return self._backend.get_shared_memories(
            self._agent_id, namespace=namespace, limit=limit
        )

    def summarize(self, window=None):
        """Trigger summarization on a window (stub for MemoryAdapter compat)."""
        if self._compaction_engine:
            self._compaction_engine.compact(self._agent_id, self._conversation_id)

    def promote(self, item_id):
        """Promote a memory item (stub for MemoryAdapter compat)."""
        pass

    def prune(self, criteria=None):
        """Prune memory (stub for MemoryAdapter compat)."""
        pass

    @classmethod
    def from_config(cls, config_path, agent_id=None, agent_name=None):
        """Create a PersistentMemoryAdapter from a JSON config file.

        Args:
            config_path: Path to the JSON config file.
            agent_id: Optional agent ID override.
            agent_name: Optional agent name override.

        Returns:
            PersistentMemoryAdapter instance.
        """
        from .config import load_config
        config = load_config(config_path)
        return cls._from_config_dict(config, agent_id, agent_name)

    @classmethod
    def from_env(cls, agent_id=None, agent_name=None):
        """Create a PersistentMemoryAdapter from GENESIS_MEMORY_CONFIG env var.

        Args:
            agent_id: Optional agent ID override.
            agent_name: Optional agent name override.

        Returns:
            PersistentMemoryAdapter instance.
        """
        from .config import load_config_from_env
        config = load_config_from_env()
        return cls._from_config_dict(config, agent_id, agent_name)

    @classmethod
    def _from_config_dict(cls, config, agent_id=None, agent_name=None):
        """Create adapter from a parsed config dict."""
        storage_cfg = config.get("storage", {})
        backend_type = storage_cfg.get("backend", "sqlite")

        if backend_type == "sqlite":
            db_path = storage_cfg.get("path", "genesis_memory.db")
            backend = SQLiteBackend(db_path)
        elif backend_type == "sqlalchemy":
            from .sqlalchemy_backend import SQLAlchemyBackend
            url = storage_cfg.get("url", f"sqlite:///{storage_cfg.get('path', 'genesis_memory.db')}")
            pool_size = storage_cfg.get("pool_size", 5)
            backend = SQLAlchemyBackend(url, pool_size=pool_size)
        else:
            raise ValueError(f"Unknown storage backend: {backend_type}")

        backend.initialize_schema()

        return cls(
            backend=backend,
            agent_id=agent_id,
            agent_name=agent_name,
            tokenizer_config=config.get("tokenizer"),
            compaction_config=config.get("compaction"),
            retrieval_config=config.get("retrieval"),
        )

    @staticmethod
    def _msg_to_adapter_format(msg):
        """Convert a database message row to SimpleMemoryAdapter format."""
        metadata = {"role": msg.get("role", "user")}
        if msg.get("metadata_json"):
            if isinstance(msg["metadata_json"], dict):
                metadata.update(msg["metadata_json"])
            elif isinstance(msg["metadata_json"], str):
                import json
                try:
                    metadata.update(json.loads(msg["metadata_json"]))
                except (json.JSONDecodeError, TypeError):
                    pass
        return {"item": msg["content"], "metadata": metadata}
