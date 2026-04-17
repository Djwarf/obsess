from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Optional


class SQLiteStorage:
    """SQLite-backed persistent storage. File-based, stdlib-only, file-locked
    for single-process safety. Two tables:

    - events: append-only log with indexed kind and agent_id columns for fast
      meta-layer queries (Creator failure-registry, Selection).
    - entities: generic (collection, id) → data JSON blob. All non-event state
      lands here. Filtering by payload fields is done Python-side after
      loading all() of a collection; adequate at prototype scale.

    Schema is created on construction if the tables don't exist. No migration
    layer in v1 — the schema is stable and forward-only."""

    def __init__(self, path: str):
        self._path = path
        self._conn = sqlite3.connect(path, isolation_level=None)  # autocommit
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        c = self._conn
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                agent_id TEXT,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_id)")
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                collection TEXT NOT NULL,
                id TEXT NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY (collection, id)
            )
            """
        )

    # --- Event log ---

    def append_event(
        self,
        kind: str,
        payload: dict,
        agent_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        ts = created_at if created_at is not None else time.time()
        self._conn.execute(
            "INSERT INTO events (id, kind, agent_id, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, kind, agent_id, json.dumps(payload), ts),
        )
        return event_id

    def query_events(
        self,
        kind: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[dict]:
        sql = "SELECT id, kind, agent_id, payload, created_at FROM events"
        clauses: list[str] = []
        params: list = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at ASC, rowid ASC"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def all_events(self) -> list[dict]:
        return self.query_events()

    @staticmethod
    def _row_to_event(row: tuple) -> dict:
        return {
            "id": row[0],
            "kind": row[1],
            "agent_id": row[2],
            "payload": json.loads(row[3]),
            "created_at": row[4],
        }

    # --- Entity collections ---

    def put(self, collection: str, id: str, data: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO entities (collection, id, data) VALUES (?, ?, ?)",
            (collection, id, json.dumps(data)),
        )

    def get(self, collection: str, id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT data FROM entities WHERE collection = ? AND id = ?",
            (collection, id),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def delete(self, collection: str, id: str) -> None:
        self._conn.execute(
            "DELETE FROM entities WHERE collection = ? AND id = ?",
            (collection, id),
        )

    def all(self, collection: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT data FROM entities WHERE collection = ? ORDER BY rowid ASC",
            (collection,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def close(self) -> None:
        self._conn.close()
