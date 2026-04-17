from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from obsess.storage import Storage
from obsess.storage.memory import InMemoryStorage


@dataclass
class Event:
    """An append-only record of something that happened at the meta layer —
    an agent spawned, an agent failed, a relationship formed, Evolution's own
    selection applied pressure. Event is deliberately generic: the payload
    dict carries kind-specific fields."""

    id: str
    kind: str
    payload: dict
    agent_id: Optional[str]
    created_at: float = field(default_factory=time.time)


class EvolutionStore:
    """Owned by Evolution. Single source of truth for population-level history.
    Append-only: records are never rewritten; corrections are new events that
    reference the original.

    Storage-backed: delegates to a Storage instance. Default InMemoryStorage
    preserves the pre-persistence behavior; pass a SQLiteStorage to persist.
    Event construction (dataclass) happens here; the storage layer just holds
    JSON-serializable dicts."""

    def __init__(self, storage: Optional[Storage] = None):
        self._storage: Storage = storage or InMemoryStorage()

    def append(
        self,
        kind: str,
        payload: dict,
        agent_id: Optional[str] = None,
    ) -> Event:
        event_id = self._storage.append_event(
            kind=kind, payload=payload, agent_id=agent_id
        )
        # Rebuild the Event from what the storage actually holds so callers
        # see the same timestamps/ids as the persistent record.
        for ev in self._storage.query_events(kind=kind):
            if ev["id"] == event_id:
                return _event_from_dict(ev)
        # Shouldn't happen — defensive fallback.
        return Event(
            id=event_id, kind=kind, payload=dict(payload), agent_id=agent_id
        )

    def query(
        self,
        kind: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[Event]:
        return [
            _event_from_dict(ev)
            for ev in self._storage.query_events(kind=kind, agent_id=agent_id)
        ]

    def all(self) -> list[Event]:
        return [_event_from_dict(ev) for ev in self._storage.all_events()]


def _event_from_dict(data: dict) -> Event:
    return Event(
        id=data["id"],
        kind=data["kind"],
        payload=dict(data["payload"]),
        agent_id=data.get("agent_id"),
        created_at=data["created_at"],
    )
