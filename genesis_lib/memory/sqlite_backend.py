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
SQLiteBackend — Zero-dependency SQLite implementation of StorageBackend.

Uses WAL mode, synchronous=NORMAL, foreign_keys=ON.
Thread-safe via check_same_thread=False + threading lock for writes.
"""

import json
import sqlite3
import threading
from typing import List, Optional

from .storage_backend import StorageBackend

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    agent_type      TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at    TEXT NOT NULL DEFAULT (datetime('now')),
    config_json     TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    message_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(agent_id),
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    sequence        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_agent_conv
    ON messages(agent_id, conversation_id, sequence);
CREATE INDEX IF NOT EXISTS idx_messages_agent_time
    ON messages(agent_id, created_at);

CREATE TABLE IF NOT EXISTS summaries (
    summary_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(agent_id),
    conversation_id TEXT NOT NULL,
    level           INTEGER NOT NULL DEFAULT 1,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    span_start_seq  INTEGER NOT NULL,
    span_end_seq    INTEGER NOT NULL,
    child_ids_json  TEXT,
    state           TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_summaries_agent_conv
    ON summaries(agent_id, conversation_id, level);

CREATE TABLE IF NOT EXISTS shared_memories (
    share_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source_agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    target_agent_id TEXT,
    namespace       TEXT NOT NULL DEFAULT 'default',
    content         TEXT NOT NULL,
    token_count     INTEGER,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_shared_source
    ON shared_memories(source_agent_id, namespace);
CREATE INDEX IF NOT EXISTS idx_shared_target
    ON shared_memories(target_agent_id, namespace);

CREATE TABLE IF NOT EXISTS compaction_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES agents(agent_id),
    conversation_id TEXT NOT NULL,
    level           INTEGER NOT NULL,
    messages_before INTEGER,
    tokens_before   INTEGER,
    tokens_after    INTEGER,
    summaries_created INTEGER,
    strategy        TEXT NOT NULL,
    duration_ms     INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memory_config (
    config_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT,
    key             TEXT NOT NULL,
    value           TEXT NOT NULL,
    UNIQUE(agent_id, key)
);
"""


class SQLiteBackend(StorageBackend):
    """SQLite implementation of StorageBackend with WAL mode."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._write_lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def initialize_schema(self) -> None:
        with self._write_lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()

    def register_agent(self, agent_id: str, agent_name: str, agent_type: str = "") -> None:
        with self._write_lock:
            self._conn.execute(
                """INSERT INTO agents (agent_id, agent_name, agent_type)
                   VALUES (?, ?, ?)
                   ON CONFLICT(agent_id) DO UPDATE SET
                       last_seen_at = datetime('now'),
                       agent_name = excluded.agent_name""",
                (agent_id, agent_name, agent_type),
            )
            self._conn.commit()

    def insert_message(
        self, agent_id: str, conversation_id: str, role: str,
        content: str, token_count: int, metadata: dict = None,
        sequence: int = None,
    ) -> int:
        meta_json = json.dumps(metadata) if metadata else None
        if sequence is None:
            sequence = self.get_next_sequence(agent_id, conversation_id)
        with self._write_lock:
            cursor = self._conn.execute(
                """INSERT INTO messages
                   (agent_id, conversation_id, role, content, token_count, metadata_json, sequence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, conversation_id, role, content, token_count, meta_json, sequence),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_messages(
        self, agent_id: str, conversation_id: str = None,
        since_sequence: int = None, limit: int = None,
    ) -> List[dict]:
        query = "SELECT * FROM messages WHERE agent_id = ?"
        params: list = [agent_id]
        if conversation_id is not None:
            query += " AND conversation_id = ?"
            params.append(conversation_id)
        if since_sequence is not None:
            query += " AND sequence >= ?"
            params.append(since_sequence)
        query += " ORDER BY sequence ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_message_by_id(self, message_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_token_count(self, agent_id: str, conversation_id: str) -> int:
        row = self._conn.execute(
            """SELECT COALESCE(SUM(token_count), 0) as total
               FROM messages WHERE agent_id = ? AND conversation_id = ?""",
            (agent_id, conversation_id),
        ).fetchone()
        return row["total"]

    def get_next_sequence(self, agent_id: str, conversation_id: str) -> int:
        row = self._conn.execute(
            """SELECT COALESCE(MAX(sequence), 0) as max_seq
               FROM messages WHERE agent_id = ? AND conversation_id = ?""",
            (agent_id, conversation_id),
        ).fetchone()
        return row["max_seq"] + 1

    def insert_summary(
        self, agent_id: str, conversation_id: str, level: int,
        content: str, token_count: int,
        span_start_seq: int, span_end_seq: int,
        child_ids: List[int] = None,
    ) -> int:
        child_json = json.dumps(child_ids) if child_ids else None
        with self._write_lock:
            cursor = self._conn.execute(
                """INSERT INTO summaries
                   (agent_id, conversation_id, level, content, token_count,
                    span_start_seq, span_end_seq, child_ids_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, conversation_id, level, content, token_count,
                 span_start_seq, span_end_seq, child_json),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_summaries(
        self, agent_id: str, conversation_id: str,
        level: int = None, state: str = "active",
    ) -> List[dict]:
        query = "SELECT * FROM summaries WHERE agent_id = ? AND conversation_id = ?"
        params: list = [agent_id, conversation_id]
        if level is not None:
            query += " AND level = ?"
            params.append(level)
        if state is not None:
            query += " AND state = ?"
            params.append(state)
        query += " ORDER BY span_start_seq ASC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_summary_state(self, summary_id: int, state: str) -> None:
        with self._write_lock:
            self._conn.execute(
                "UPDATE summaries SET state = ? WHERE summary_id = ?",
                (state, summary_id),
            )
            self._conn.commit()

    def insert_shared_memory(
        self, source_agent_id: str, content: str,
        target_agent_id: str = None, namespace: str = "default",
        token_count: int = 0, metadata: dict = None,
        expires_at: str = None,
    ) -> int:
        meta_json = json.dumps(metadata) if metadata else None
        with self._write_lock:
            cursor = self._conn.execute(
                """INSERT INTO shared_memories
                   (source_agent_id, target_agent_id, namespace, content,
                    token_count, metadata_json, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (source_agent_id, target_agent_id, namespace, content,
                 token_count, meta_json, expires_at),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_shared_memories(
        self, agent_id: str, namespace: str = "default",
        include_broadcasts: bool = True, limit: int = 50,
    ) -> List[dict]:
        if include_broadcasts:
            query = """SELECT * FROM shared_memories
                       WHERE namespace = ?
                         AND (target_agent_id = ? OR target_agent_id IS NULL)
                       ORDER BY created_at DESC LIMIT ?"""
            params = [namespace, agent_id, limit]
        else:
            query = """SELECT * FROM shared_memories
                       WHERE namespace = ? AND target_agent_id = ?
                       ORDER BY created_at DESC LIMIT ?"""
            params = [namespace, agent_id, limit]
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def insert_compaction_log(self, agent_id: str, conversation_id: str, **kwargs) -> None:
        with self._write_lock:
            self._conn.execute(
                """INSERT INTO compaction_log
                   (agent_id, conversation_id, level, messages_before,
                    tokens_before, tokens_after, summaries_created,
                    strategy, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent_id, conversation_id,
                    kwargs.get("level", 0),
                    kwargs.get("messages_before", 0),
                    kwargs.get("tokens_before", 0),
                    kwargs.get("tokens_after", 0),
                    kwargs.get("summaries_created", 0),
                    kwargs.get("strategy", "unknown"),
                    kwargs.get("duration_ms", 0),
                ),
            )
            self._conn.commit()

    def get_config(self, agent_id: str = None) -> dict:
        # Get global defaults first
        rows = self._conn.execute(
            "SELECT key, value FROM memory_config WHERE agent_id IS NULL"
        ).fetchall()
        config = {r["key"]: r["value"] for r in rows}
        # Override with agent-specific
        if agent_id:
            rows = self._conn.execute(
                "SELECT key, value FROM memory_config WHERE agent_id = ?",
                (agent_id,),
            ).fetchall()
            config.update({r["key"]: r["value"] for r in rows})
        return config

    def set_config(self, key: str, value: str, agent_id: str = None) -> None:
        with self._write_lock:
            self._conn.execute(
                """INSERT INTO memory_config (agent_id, key, value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(agent_id, key) DO UPDATE SET value = excluded.value""",
                (agent_id, key, value),
            )
            self._conn.commit()

    def close(self):
        """Close the database connection."""
        self._conn.close()

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert sqlite3.Row to dict, parsing JSON fields."""
        d = dict(row)
        for json_field in ("metadata_json", "child_ids_json", "config_json"):
            if json_field in d and d[json_field] is not None:
                try:
                    d[json_field] = json.loads(d[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
