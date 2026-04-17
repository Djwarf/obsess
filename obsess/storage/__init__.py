from __future__ import annotations

from typing import Optional, Protocol


class Storage(Protocol):
    """Plug-and-play storage primitive. Mirrors the LLM provider architecture:
    obsess's stores (EvolutionStore, TraumaStore, ImpressionStore, etc.)
    consume this thin protocol; swapping backends (in-memory, SQLite, Postgres,
    Redis, ...) is a drop-in change that does not affect obsess's semantics.

    Two concern groups:

    - **Event log**: append-only, time-ordered, filtered by kind and/or agent_id.
      This is the hot query path for the meta-layer (Creator failure-registry,
      Selection). Backends should index kind and agent_id.

    - **Entity collections**: id-keyed CRUD. Used by every other store. Queries
      that need field-level filtering are done Python-side on `all(collection)`
      for v1 — good enough at prototype scale; moving to backend-side filters
      is a future optimization behind this same protocol."""

    # --- Event log ---

    def append_event(
        self,
        kind: str,
        payload: dict,
        agent_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ) -> str: ...

    def query_events(
        self,
        kind: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[dict]: ...

    def all_events(self) -> list[dict]: ...

    # --- Entity collections ---

    def put(self, collection: str, id: str, data: dict) -> None: ...
    def get(self, collection: str, id: str) -> Optional[dict]: ...
    def delete(self, collection: str, id: str) -> None: ...
    def all(self, collection: str) -> list[dict]: ...

    # --- Lifecycle ---

    def close(self) -> None: ...


# Re-export concrete backends.

try:
    from obsess.storage.memory import InMemoryStorage  # noqa: F401
except ImportError:
    pass

try:
    from obsess.storage.sqlite import SQLiteStorage  # noqa: F401
except ImportError:
    pass
