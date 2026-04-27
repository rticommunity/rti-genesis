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
StorageBackend ABC — Abstract interface for persistent memory storage.

Implementations must support transactional writes and indexed reads.
SQLite is the zero-dependency default. PostgreSQL/MySQL via SQLAlchemy
for remote or shared deployments.
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class StorageBackend(ABC):
    """Abstract interface for persistent memory storage."""

    @abstractmethod
    def initialize_schema(self) -> None:
        """Create tables if they don't exist. Idempotent."""

    # --- Agent registry ---
    @abstractmethod
    def register_agent(self, agent_id: str, agent_name: str, agent_type: str = "") -> None:
        """Register or update an agent's presence. Upserts last_seen_at."""

    # --- Messages (immutable store) ---
    @abstractmethod
    def insert_message(
        self, agent_id: str, conversation_id: str, role: str,
        content: str, token_count: int, metadata: dict = None,
        sequence: int = None,
    ) -> int:
        """Append a message. Returns message_id. Never modifies existing rows."""

    @abstractmethod
    def get_messages(
        self, agent_id: str, conversation_id: str = None,
        since_sequence: int = None, limit: int = None,
    ) -> List[dict]:
        """Retrieve messages for an agent, optionally filtered by conversation and sequence."""

    @abstractmethod
    def get_message_by_id(self, message_id: int) -> Optional[dict]:
        """Retrieve a single message by primary key."""

    @abstractmethod
    def get_token_count(self, agent_id: str, conversation_id: str) -> int:
        """Sum of token_count for all messages in a conversation."""

    @abstractmethod
    def get_next_sequence(self, agent_id: str, conversation_id: str) -> int:
        """Return the next sequence number for a conversation."""

    # --- Summaries (DAG cache) ---
    @abstractmethod
    def insert_summary(
        self, agent_id: str, conversation_id: str, level: int,
        content: str, token_count: int,
        span_start_seq: int, span_end_seq: int,
        child_ids: List[int] = None,
    ) -> int:
        """Insert a summary node. Returns summary_id."""

    @abstractmethod
    def get_summaries(
        self, agent_id: str, conversation_id: str,
        level: int = None, state: str = "active",
    ) -> List[dict]:
        """Retrieve summaries, optionally filtered by level and state."""

    @abstractmethod
    def update_summary_state(self, summary_id: int, state: str) -> None:
        """Transition a summary (e.g., 'active' -> 'superseded')."""

    # --- Shared memory (cross-agent) ---
    @abstractmethod
    def insert_shared_memory(
        self, source_agent_id: str, content: str,
        target_agent_id: str = None, namespace: str = "default",
        token_count: int = 0, metadata: dict = None,
        expires_at: str = None,
    ) -> int:
        """Publish a memory item for other agents."""

    @abstractmethod
    def get_shared_memories(
        self, agent_id: str, namespace: str = "default",
        include_broadcasts: bool = True, limit: int = 50,
    ) -> List[dict]:
        """Retrieve shared memories targeted at (or broadcast to) an agent."""

    # --- Compaction log ---
    @abstractmethod
    def insert_compaction_log(self, agent_id: str, conversation_id: str, **kwargs) -> None:
        """Record a compaction event for audit."""

    # --- Configuration ---
    @abstractmethod
    def get_config(self, agent_id: str = None) -> dict:
        """Retrieve memory config. Agent-specific overrides global defaults."""

    @abstractmethod
    def set_config(self, key: str, value: str, agent_id: str = None) -> None:
        """Set a config value. agent_id=None sets global default."""
