from __future__ import annotations

import copy
import time
import uuid
from typing import Optional


class InMemoryStorage:
    """Transient storage backend. Single-process, non-persistent — state
    lives only for the life of this object. Default backend for tests and
    single-session use. Data structures mirror obsess's pre-storage design,
    so switching to this backend is behaviorally identical to how obsess
    stores worked before the storage refactor."""

    def __init__(self):
        self._events: list[dict] = []
        self._collections: dict[str, dict[str, dict]] = {}

    # --- Event log ---

    def append_event(
        self,
        kind: str,
        payload: dict,
        agent_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        self._events.append({
            "id": event_id,
            "kind": kind,
            "payload": dict(payload),
            "agent_id": agent_id,
            "created_at": created_at if created_at is not None else time.time(),
        })
        return event_id

    def query_events(
        self,
        kind: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[dict]:
        results = self._events
        if kind is not None:
            results = [e for e in results if e["kind"] == kind]
        if agent_id is not None:
            results = [e for e in results if e["agent_id"] == agent_id]
        return [copy.deepcopy(e) for e in results]

    def all_events(self) -> list[dict]:
        return [copy.deepcopy(e) for e in self._events]

    # --- Entity collections ---

    def put(self, collection: str, id: str, data: dict) -> None:
        coll = self._collections.setdefault(collection, {})
        coll[id] = copy.deepcopy(data)

    def get(self, collection: str, id: str) -> Optional[dict]:
        coll = self._collections.get(collection)
        if coll is None:
            return None
        record = coll.get(id)
        return copy.deepcopy(record) if record is not None else None

    def delete(self, collection: str, id: str) -> None:
        coll = self._collections.get(collection)
        if coll is not None:
            coll.pop(id, None)

    def all(self, collection: str) -> list[dict]:
        coll = self._collections.get(collection)
        if coll is None:
            return []
        return [copy.deepcopy(v) for v in coll.values()]

    def close(self) -> None:
        pass
