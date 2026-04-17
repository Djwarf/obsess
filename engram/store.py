from __future__ import annotations

import uuid
from typing import Optional

from engram.embed import Embedder, cosine
from engram.storage import Storage
from engram.storage.memory import InMemoryStorage
from engram.storage.serialize import (
    impression_from_dict,
    impression_to_dict,
    trauma_from_dict,
    trauma_to_dict,
)
from engram.types import Impression, Trauma


_IMPRESSIONS_COLLECTION = "impressions"
_TRAUMAS_COLLECTION = "traumas"


class ImpressionStore:
    """Always per-agent. Uses a shared Storage instance but filters by
    agent_id on read (impressions carry their agent_id as part of the record).
    Structural isolation is still the enforced invariant — the store's
    `agent_id` attribute gates both writes (stamp) and reads (filter)."""

    def __init__(self, embedder: Embedder, agent_id: str, storage: Optional[Storage] = None):
        self._embedder = embedder
        self._agent_id = agent_id
        self._storage: Storage = storage or InMemoryStorage()
        self._cache: dict[str, Impression] = self._hydrate()

    def _hydrate(self) -> dict[str, Impression]:
        cache: dict[str, Impression] = {}
        for data in self._storage.all(_IMPRESSIONS_COLLECTION):
            if data.get("agent_id") != self._agent_id:
                continue
            imp = impression_from_dict(data)
            cache[imp.id] = imp
        return cache

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def add(
        self,
        seed_text: str,
        source_text: str,
        obsession_ids: list[str],
        frame_at_encode: str,
    ) -> Impression:
        imp = Impression(
            id=str(uuid.uuid4()),
            seed_text=seed_text,
            source_text=source_text,
            obsession_ids=list(obsession_ids),
            frame_at_encode=frame_at_encode,
            agent_id=self._agent_id,
            embedding=self._embedder.embed(seed_text),
        )
        self._cache[imp.id] = imp
        self._storage.put(_IMPRESSIONS_COLLECTION, imp.id, impression_to_dict(imp))
        return imp

    def all(self) -> list[Impression]:
        return list(self._cache.values())

    def search(
        self,
        query_embedding: list[float],
        obsession_ids: Optional[list[str]] = None,
        k: int = 5,
    ) -> list[tuple[Impression, float]]:
        scored: list[tuple[Impression, float]] = []
        for imp in self._cache.values():
            if obsession_ids and not set(imp.obsession_ids) & set(obsession_ids):
                continue
            if imp.embedding is None:
                continue
            sim = cosine(query_embedding, imp.embedding)
            scored.append((imp, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


class TraumaStore:
    """Population-level catalog. Per-agent and pooled traumas live side by
    side, distinguished by origin_agent_id and pool_id fields. Storage-backed
    via a shared Storage instance; hydrates its cache on construction."""

    def __init__(self, embedder: Embedder, storage: Optional[Storage] = None):
        self._embedder = embedder
        self._storage: Storage = storage or InMemoryStorage()
        self._cache: dict[str, Trauma] = self._hydrate()

    def _hydrate(self) -> dict[str, Trauma]:
        cache: dict[str, Trauma] = {}
        for data in self._storage.all(_TRAUMAS_COLLECTION):
            t = trauma_from_dict(data)
            cache[t.id] = t
        return cache

    def record(
        self,
        origin_agent_id: str,
        context: str,
        failure: str,
        attempted_solutions: list[str],
        unsolvable_at_time: bool,
        cost: str,
        trigger_pattern: str,
        linked_obsession_id: Optional[str],
        pool_id: Optional[str] = None,
    ) -> Trauma:
        t = Trauma(
            id=str(uuid.uuid4()),
            context=context,
            failure=failure,
            attempted_solutions=list(attempted_solutions),
            unsolvable_at_time=unsolvable_at_time,
            cost=cost,
            trigger_pattern=trigger_pattern,
            linked_obsession_id=linked_obsession_id,
            origin_agent_id=origin_agent_id,
            pool_id=pool_id,
            embedding=self._embedder.embed(f"{context} {failure} {trigger_pattern}"),
        )
        self._cache[t.id] = t
        self._storage.put(_TRAUMAS_COLLECTION, t.id, trauma_to_dict(t))
        return t

    def append_resolution(self, trauma_id: str, tradeoff: str) -> None:
        t = self._cache.get(trauma_id)
        if t is None:
            raise KeyError(trauma_id)
        t.resolution_tradeoffs.append(tradeoff)
        self._storage.put(_TRAUMAS_COLLECTION, t.id, trauma_to_dict(t))

    def get(self, trauma_id: str) -> Optional[Trauma]:
        return self._cache.get(trauma_id)

    def all(self) -> list[Trauma]:
        return list(self._cache.values())

    def for_agent(self, agent_id: str) -> list[Trauma]:
        return [
            t for t in self._cache.values()
            if t.origin_agent_id == agent_id and t.pool_id is None
        ]

    def for_pool(self, pool_id: str) -> list[Trauma]:
        return [t for t in self._cache.values() if t.pool_id == pool_id]
