from __future__ import annotations

import uuid
from typing import Optional

from engram.embed import Embedder
from engram.evolution import EvolutionStore
from engram.storage import Storage
from engram.storage.memory import InMemoryStorage
from engram.storage.serialize import (
    obsession_def_from_dict,
    obsession_def_to_dict,
)
from engram.types import ObsessionDefinition


_SHARED_DEFS_COLLECTION = "shared_obsession_definitions"


class SharedObsessions:
    """Population-level pool of shared obsession definitions. Storage-backed;
    hydrates on construction. Two flavors: free shared (owner_pool_id is None)
    and pool-scoped (owner_pool_id set, access gated by pool membership at
    the Memory layer)."""

    def __init__(
        self,
        embedder: Embedder,
        evolution: EvolutionStore,
        storage: Optional[Storage] = None,
    ):
        self._embedder = embedder
        self._evolution = evolution
        self._storage: Storage = storage or InMemoryStorage()
        self._cache: dict[str, ObsessionDefinition] = self._hydrate()

    def _hydrate(self) -> dict[str, ObsessionDefinition]:
        cache: dict[str, ObsessionDefinition] = {}
        for data in self._storage.all(_SHARED_DEFS_COLLECTION):
            d = obsession_def_from_dict(data)
            cache[d.id] = d
        return cache

    def define(
        self,
        domain: str,
        description: str,
        identity_level: bool = False,
        seed_metadata: Optional[dict] = None,
        owner_pool_id: Optional[str] = None,
    ) -> ObsessionDefinition:
        defn = ObsessionDefinition(
            id=str(uuid.uuid4()),
            domain=domain,
            description=description,
            identity_level=identity_level,
            seed_metadata=seed_metadata or {},
            embedding=self._embedder.embed(f"{domain}. {description}"),
            owner_pool_id=owner_pool_id,
        )
        self._cache[defn.id] = defn
        self._storage.put(_SHARED_DEFS_COLLECTION, defn.id, obsession_def_to_dict(defn))
        self._evolution.append(
            "shared_obsession_defined",
            {
                "definition_id": defn.id,
                "domain": defn.domain,
                "owner_pool_id": owner_pool_id,
            },
            agent_id=None,
        )
        return defn

    def get(self, definition_id: str) -> Optional[ObsessionDefinition]:
        return self._cache.get(definition_id)

    def has(self, definition_id: str) -> bool:
        return definition_id in self._cache

    def all(self) -> list[ObsessionDefinition]:
        return list(self._cache.values())
