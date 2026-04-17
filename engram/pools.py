from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from engram.evolution import EvolutionStore
from engram.storage import Storage
from engram.storage.memory import InMemoryStorage


_POOLS_COLLECTION = "pools"


@dataclass
class Pool:
    """A named collective with a mutable member set. Pools are how 'pooled'
    ownership (DESIGN-MULTI.md) is realized: pool obsessions and pool traumas
    are scoped by pool membership rather than by per-agent sharing edges."""

    id: str
    name: str
    member_ids: set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)


class PoolRegistry:
    """Operational store for pools. Membership changes emit events to Evolution.
    Storage-backed; hydrates on construction."""

    def __init__(
        self,
        evolution: EvolutionStore,
        storage: Optional[Storage] = None,
    ):
        self._evolution = evolution
        self._storage: Storage = storage or InMemoryStorage()
        self._pools: dict[str, Pool] = self._hydrate()

    def _hydrate(self) -> dict[str, Pool]:
        from engram.storage.serialize import pool_from_dict
        cache: dict[str, Pool] = {}
        for data in self._storage.all(_POOLS_COLLECTION):
            p = pool_from_dict(data)
            cache[p.id] = p
        return cache

    def _persist(self, pool: Pool) -> None:
        from engram.storage.serialize import pool_to_dict
        self._storage.put(_POOLS_COLLECTION, pool.id, pool_to_dict(pool))

    def add(self, name: str, member_ids: list[str]) -> Pool:
        pool = Pool(
            id=str(uuid.uuid4()),
            name=name,
            member_ids=set(member_ids),
        )
        self._pools[pool.id] = pool
        self._persist(pool)
        self._evolution.append(
            "pool_formed",
            {
                "pool_id": pool.id,
                "name": pool.name,
                "member_ids": sorted(pool.member_ids),
            },
            agent_id=None,
        )
        return pool

    def get(self, pool_id: str) -> Optional[Pool]:
        return self._pools.get(pool_id)

    def all(self) -> list[Pool]:
        return list(self._pools.values())

    def for_member(self, agent_id: str) -> list[Pool]:
        return [p for p in self._pools.values() if agent_id in p.member_ids]

    def is_member(self, pool_id: str, agent_id: str) -> bool:
        pool = self._pools.get(pool_id)
        if pool is None:
            return False
        return agent_id in pool.member_ids

    def add_member(self, pool_id: str, agent_id: str) -> None:
        pool = self._pools.get(pool_id)
        if pool is None:
            raise KeyError(pool_id)
        if agent_id in pool.member_ids:
            return
        pool.member_ids.add(agent_id)
        self._persist(pool)
        self._evolution.append(
            "pool_member_added",
            {"pool_id": pool_id, "agent_id": agent_id},
            agent_id=agent_id,
        )

    def remove_member(self, pool_id: str, agent_id: str) -> None:
        pool = self._pools.get(pool_id)
        if pool is None:
            raise KeyError(pool_id)
        if agent_id not in pool.member_ids:
            return
        pool.member_ids.discard(agent_id)
        self._persist(pool)
        self._evolution.append(
            "pool_member_removed",
            {"pool_id": pool_id, "agent_id": agent_id},
            agent_id=agent_id,
        )
