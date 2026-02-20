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
SQLAlchemyBackend — Enterprise storage backend using SQLAlchemy Core.

Supports PostgreSQL, MySQL, or any RDBMS via SQLAlchemy dialects.
Also works with SQLite via 'sqlite:///' URLs for testing parity.

Dialect-aware: automatically uses correct SQL syntax for each database.
"""

import json
from typing import List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from .storage_backend import StorageBackend

# ── Schema templates per dialect ─────────────────────────────────────

_SQLITE_SCHEMA = """
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
    agent_id        TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    sequence        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_agent_conv ON messages(agent_id, conversation_id, sequence);
CREATE INDEX IF NOT EXISTS idx_messages_agent_time ON messages(agent_id, created_at);
CREATE TABLE IF NOT EXISTS summaries (
    summary_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_summaries_agent_conv ON summaries(agent_id, conversation_id, level);
CREATE TABLE IF NOT EXISTS shared_memories (
    share_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source_agent_id TEXT NOT NULL,
    target_agent_id TEXT,
    namespace       TEXT NOT NULL DEFAULT 'default',
    content         TEXT NOT NULL,
    token_count     INTEGER,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_shared_source ON shared_memories(source_agent_id, namespace);
CREATE INDEX IF NOT EXISTS idx_shared_target ON shared_memories(target_agent_id, namespace);
CREATE TABLE IF NOT EXISTS compaction_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL,
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

# PostgreSQL schema: uses SERIAL, CURRENT_TIMESTAMP, and DO NOTHING for idx conflicts
_PG_SCHEMA_TABLES = [
    """CREATE TABLE IF NOT EXISTS agents (
        agent_id        TEXT PRIMARY KEY,
        agent_name      TEXT NOT NULL,
        agent_type      TEXT DEFAULT '',
        created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        config_json     TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS messages (
        message_id      SERIAL PRIMARY KEY,
        agent_id        TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        token_count     INTEGER,
        metadata_json   TEXT,
        created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        sequence        INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS summaries (
        summary_id      SERIAL PRIMARY KEY,
        agent_id        TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        level           INTEGER NOT NULL DEFAULT 1,
        content         TEXT NOT NULL,
        token_count     INTEGER,
        span_start_seq  INTEGER NOT NULL,
        span_end_seq    INTEGER NOT NULL,
        child_ids_json  TEXT,
        state           TEXT NOT NULL DEFAULT 'active',
        created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS shared_memories (
        share_id        SERIAL PRIMARY KEY,
        source_agent_id TEXT NOT NULL,
        target_agent_id TEXT,
        namespace       TEXT NOT NULL DEFAULT 'default',
        content         TEXT NOT NULL,
        token_count     INTEGER,
        metadata_json   TEXT,
        created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at      TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS compaction_log (
        log_id          SERIAL PRIMARY KEY,
        agent_id        TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        level           INTEGER NOT NULL,
        messages_before INTEGER,
        tokens_before   INTEGER,
        tokens_after    INTEGER,
        summaries_created INTEGER,
        strategy        TEXT NOT NULL,
        duration_ms     INTEGER,
        created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS memory_config (
        config_id       SERIAL PRIMARY KEY,
        agent_id        TEXT,
        key             TEXT NOT NULL,
        value           TEXT NOT NULL,
        UNIQUE(agent_id, key)
    )""",
]

_PG_SCHEMA_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_messages_agent_conv ON messages(agent_id, conversation_id, sequence)",
    "CREATE INDEX IF NOT EXISTS idx_messages_agent_time ON messages(agent_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_summaries_agent_conv ON summaries(agent_id, conversation_id, level)",
    "CREATE INDEX IF NOT EXISTS idx_shared_source ON shared_memories(source_agent_id, namespace)",
    "CREATE INDEX IF NOT EXISTS idx_shared_target ON shared_memories(target_agent_id, namespace)",
]


class SQLAlchemyBackend(StorageBackend):
    """SQLAlchemy Core implementation of StorageBackend.

    Dialect-aware: detects SQLite vs PostgreSQL and uses appropriate SQL syntax.
    """

    def __init__(self, url: str, pool_size: int = 5, **engine_kwargs):
        self.url = url
        self._is_sqlite = url.startswith("sqlite")
        self._is_pg = url.startswith("postgresql")

        engine_args = {}
        if not self._is_sqlite:
            engine_args["pool_size"] = pool_size
            engine_args["poolclass"] = QueuePool
        engine_args.update(engine_kwargs)

        self._engine = create_engine(url, **engine_args)

    @property
    def _now_func(self) -> str:
        """Return the correct 'now' function for the current dialect."""
        return "datetime('now')" if self._is_sqlite else "CURRENT_TIMESTAMP"

    def initialize_schema(self) -> None:
        if self._is_sqlite:
            with self._engine.begin() as conn:
                # SQLite supports executescript-like behavior via multiple execute calls
                for stmt in _SQLITE_SCHEMA.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        conn.execute(text(stmt))
        else:
            with self._engine.begin() as conn:
                for ddl in _PG_SCHEMA_TABLES:
                    conn.execute(text(ddl))
                for ddl in _PG_SCHEMA_INDEXES:
                    conn.execute(text(ddl))

    def register_agent(self, agent_id: str, agent_name: str, agent_type: str = "") -> None:
        now = self._now_func
        with self._engine.begin() as conn:
            conn.execute(text(
                f"""INSERT INTO agents (agent_id, agent_name, agent_type)
                   VALUES (:aid, :aname, :atype)
                   ON CONFLICT(agent_id) DO UPDATE SET
                       last_seen_at = {now},
                       agent_name = EXCLUDED.agent_name"""
            ), {"aid": agent_id, "aname": agent_name, "atype": agent_type})

    def insert_message(
        self, agent_id: str, conversation_id: str, role: str,
        content: str, token_count: int, metadata: dict = None,
        sequence: int = None,
    ) -> int:
        meta_json = json.dumps(metadata) if metadata else None
        if sequence is None:
            sequence = self.get_next_sequence(agent_id, conversation_id)
        with self._engine.begin() as conn:
            if self._is_pg:
                row = conn.execute(text(
                    """INSERT INTO messages
                       (agent_id, conversation_id, role, content, token_count, metadata_json, sequence)
                       VALUES (:aid, :cid, :role, :content, :tc, :meta, :seq)
                       RETURNING message_id"""
                ), {
                    "aid": agent_id, "cid": conversation_id, "role": role,
                    "content": content, "tc": token_count, "meta": meta_json,
                    "seq": sequence,
                }).fetchone()
                return row[0]
            else:
                result = conn.execute(text(
                    """INSERT INTO messages
                       (agent_id, conversation_id, role, content, token_count, metadata_json, sequence)
                       VALUES (:aid, :cid, :role, :content, :tc, :meta, :seq)"""
                ), {
                    "aid": agent_id, "cid": conversation_id, "role": role,
                    "content": content, "tc": token_count, "meta": meta_json,
                    "seq": sequence,
                })
                return result.lastrowid

    def get_messages(
        self, agent_id: str, conversation_id: str = None,
        since_sequence: int = None, limit: int = None,
    ) -> List[dict]:
        query = "SELECT * FROM messages WHERE agent_id = :aid"
        params = {"aid": agent_id}
        if conversation_id is not None:
            query += " AND conversation_id = :cid"
            params["cid"] = conversation_id
        if since_sequence is not None:
            query += " AND sequence >= :seq"
            params["seq"] = since_sequence
        query += " ORDER BY sequence ASC"
        if limit is not None:
            query += " LIMIT :lim"
            params["lim"] = limit
        with self._engine.connect() as conn:
            rows = conn.execute(text(query), params).mappings().all()
            return [self._row_to_dict(dict(r)) for r in rows]

    def get_message_by_id(self, message_id: int) -> Optional[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM messages WHERE message_id = :mid"),
                {"mid": message_id},
            ).mappings().all()
            if rows:
                return self._row_to_dict(dict(rows[0]))
            return None

    def get_token_count(self, agent_id: str, conversation_id: str) -> int:
        with self._engine.connect() as conn:
            row = conn.execute(text(
                """SELECT COALESCE(SUM(token_count), 0) as total
                   FROM messages WHERE agent_id = :aid AND conversation_id = :cid"""
            ), {"aid": agent_id, "cid": conversation_id}).mappings().first()
            return row["total"]

    def get_next_sequence(self, agent_id: str, conversation_id: str) -> int:
        with self._engine.connect() as conn:
            row = conn.execute(text(
                """SELECT COALESCE(MAX(sequence), 0) as max_seq
                   FROM messages WHERE agent_id = :aid AND conversation_id = :cid"""
            ), {"aid": agent_id, "cid": conversation_id}).mappings().first()
            return row["max_seq"] + 1

    def insert_summary(
        self, agent_id: str, conversation_id: str, level: int,
        content: str, token_count: int,
        span_start_seq: int, span_end_seq: int,
        child_ids: List[int] = None,
    ) -> int:
        child_json = json.dumps(child_ids) if child_ids else None
        with self._engine.begin() as conn:
            if self._is_pg:
                row = conn.execute(text(
                    """INSERT INTO summaries
                       (agent_id, conversation_id, level, content, token_count,
                        span_start_seq, span_end_seq, child_ids_json)
                       VALUES (:aid, :cid, :level, :content, :tc, :sstart, :send, :cids)
                       RETURNING summary_id"""
                ), {
                    "aid": agent_id, "cid": conversation_id, "level": level,
                    "content": content, "tc": token_count,
                    "sstart": span_start_seq, "send": span_end_seq,
                    "cids": child_json,
                }).fetchone()
                return row[0]
            else:
                result = conn.execute(text(
                    """INSERT INTO summaries
                       (agent_id, conversation_id, level, content, token_count,
                        span_start_seq, span_end_seq, child_ids_json)
                       VALUES (:aid, :cid, :level, :content, :tc, :sstart, :send, :cids)"""
                ), {
                    "aid": agent_id, "cid": conversation_id, "level": level,
                    "content": content, "tc": token_count,
                    "sstart": span_start_seq, "send": span_end_seq,
                    "cids": child_json,
                })
                return result.lastrowid

    def get_summaries(
        self, agent_id: str, conversation_id: str,
        level: int = None, state: str = "active",
    ) -> List[dict]:
        query = "SELECT * FROM summaries WHERE agent_id = :aid AND conversation_id = :cid"
        params = {"aid": agent_id, "cid": conversation_id}
        if level is not None:
            query += " AND level = :level"
            params["level"] = level
        if state is not None:
            query += " AND state = :state"
            params["state"] = state
        query += " ORDER BY span_start_seq ASC"
        with self._engine.connect() as conn:
            rows = conn.execute(text(query), params).mappings().all()
            return [self._row_to_dict(dict(r)) for r in rows]

    def update_summary_state(self, summary_id: int, state: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(
                "UPDATE summaries SET state = :state WHERE summary_id = :sid"
            ), {"state": state, "sid": summary_id})

    def insert_shared_memory(
        self, source_agent_id: str, content: str,
        target_agent_id: str = None, namespace: str = "default",
        token_count: int = 0, metadata: dict = None,
        expires_at: str = None,
    ) -> int:
        meta_json = json.dumps(metadata) if metadata else None
        with self._engine.begin() as conn:
            if self._is_pg:
                row = conn.execute(text(
                    """INSERT INTO shared_memories
                       (source_agent_id, target_agent_id, namespace, content,
                        token_count, metadata_json, expires_at)
                       VALUES (:said, :taid, :ns, :content, :tc, :meta, :exp)
                       RETURNING share_id"""
                ), {
                    "said": source_agent_id, "taid": target_agent_id,
                    "ns": namespace, "content": content, "tc": token_count,
                    "meta": meta_json, "exp": expires_at,
                }).fetchone()
                return row[0]
            else:
                result = conn.execute(text(
                    """INSERT INTO shared_memories
                       (source_agent_id, target_agent_id, namespace, content,
                        token_count, metadata_json, expires_at)
                       VALUES (:said, :taid, :ns, :content, :tc, :meta, :exp)"""
                ), {
                    "said": source_agent_id, "taid": target_agent_id,
                    "ns": namespace, "content": content, "tc": token_count,
                    "meta": meta_json, "exp": expires_at,
                })
                return result.lastrowid

    def get_shared_memories(
        self, agent_id: str, namespace: str = "default",
        include_broadcasts: bool = True, limit: int = 50,
    ) -> List[dict]:
        if include_broadcasts:
            query = """SELECT * FROM shared_memories
                       WHERE namespace = :ns
                         AND (target_agent_id = :aid OR target_agent_id IS NULL)
                       ORDER BY created_at DESC LIMIT :lim"""
        else:
            query = """SELECT * FROM shared_memories
                       WHERE namespace = :ns AND target_agent_id = :aid
                       ORDER BY created_at DESC LIMIT :lim"""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(query), {"ns": namespace, "aid": agent_id, "lim": limit}
            ).mappings().all()
            return [self._row_to_dict(dict(r)) for r in rows]

    def insert_compaction_log(self, agent_id: str, conversation_id: str, **kwargs) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(
                """INSERT INTO compaction_log
                   (agent_id, conversation_id, level, messages_before,
                    tokens_before, tokens_after, summaries_created,
                    strategy, duration_ms)
                   VALUES (:aid, :cid, :level, :mb, :tb, :ta, :sc, :strat, :dur)"""
            ), {
                "aid": agent_id, "cid": conversation_id,
                "level": kwargs.get("level", 0),
                "mb": kwargs.get("messages_before", 0),
                "tb": kwargs.get("tokens_before", 0),
                "ta": kwargs.get("tokens_after", 0),
                "sc": kwargs.get("summaries_created", 0),
                "strat": kwargs.get("strategy", "unknown"),
                "dur": kwargs.get("duration_ms", 0),
            })

    def get_config(self, agent_id: str = None) -> dict:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT key, value FROM memory_config WHERE agent_id IS NULL")
            ).mappings().all()
            config = {r["key"]: r["value"] for r in rows}
            if agent_id:
                rows = conn.execute(
                    text("SELECT key, value FROM memory_config WHERE agent_id = :aid"),
                    {"aid": agent_id},
                ).mappings().all()
                config.update({r["key"]: r["value"] for r in rows})
            return config

    def set_config(self, key: str, value: str, agent_id: str = None) -> None:
        now = self._now_func
        with self._engine.begin() as conn:
            if self._is_pg:
                conn.execute(text(
                    """INSERT INTO memory_config (agent_id, key, value)
                       VALUES (:aid, :key, :val)
                       ON CONFLICT (agent_id, key) DO UPDATE SET value = EXCLUDED.value"""
                ), {"aid": agent_id, "key": key, "val": value})
            else:
                conn.execute(text(
                    """INSERT INTO memory_config (agent_id, key, value)
                       VALUES (:aid, :key, :val)
                       ON CONFLICT(agent_id, key) DO UPDATE SET value = :val"""
                ), {"aid": agent_id, "key": key, "val": value})

    def close(self):
        """Dispose of the engine and its connection pool."""
        self._engine.dispose()

    @staticmethod
    def _row_to_dict(d: dict) -> dict:
        """Parse JSON fields in a row dict."""
        for json_field in ("metadata_json", "child_ids_json", "config_json"):
            if json_field in d and d[json_field] is not None:
                try:
                    d[json_field] = json.loads(d[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
