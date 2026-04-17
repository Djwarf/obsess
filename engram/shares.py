from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from engram.evolution import EvolutionStore
from engram.relationships import SharingMode
from engram.storage import Storage
from engram.storage.memory import InMemoryStorage


_SHARES_COLLECTION = "trauma_shares"


@dataclass
class TraumaShare:
    """A share relationship: trauma `trauma_id` (lived by `origin_agent_id`)
    is accessible to `recipient_agent_id` with the given `mode`. Created by
    trauma propagation along relationship edges."""

    id: str
    trauma_id: str
    recipient_agent_id: str
    origin_agent_id: str
    mode: SharingMode
    via_relationship_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class TraumaShares:
    """Population-level access-control table for trauma sharing. Append-only
    at v1: shares are created by propagation, not revoked."""

    def __init__(
        self,
        evolution: EvolutionStore,
        storage: Optional[Storage] = None,
    ):
        self._evolution = evolution
        self._storage: Storage = storage or InMemoryStorage()
        self._cache: dict[str, TraumaShare] = self._hydrate()

    def _hydrate(self) -> dict[str, TraumaShare]:
        from engram.storage.serialize import trauma_share_from_dict
        cache: dict[str, TraumaShare] = {}
        for data in self._storage.all(_SHARES_COLLECTION):
            s = trauma_share_from_dict(data)
            cache[s.id] = s
        return cache

    def add(
        self,
        trauma_id: str,
        recipient_agent_id: str,
        origin_agent_id: str,
        mode: SharingMode,
        via_relationship_id: Optional[str] = None,
    ) -> TraumaShare:
        share = TraumaShare(
            id=str(uuid.uuid4()),
            trauma_id=trauma_id,
            recipient_agent_id=recipient_agent_id,
            origin_agent_id=origin_agent_id,
            mode=mode,
            via_relationship_id=via_relationship_id,
        )
        from engram.storage.serialize import trauma_share_to_dict
        self._cache[share.id] = share
        self._storage.put(_SHARES_COLLECTION, share.id, trauma_share_to_dict(share))
        self._evolution.append(
            "trauma_shared",
            {
                "trauma_id": trauma_id,
                "recipient_agent_id": recipient_agent_id,
                "mode": mode.value,
                "via_relationship_id": via_relationship_id,
            },
            agent_id=origin_agent_id,
        )
        return share

    def for_recipient(self, agent_id: str) -> list[TraumaShare]:
        return [s for s in self._cache.values() if s.recipient_agent_id == agent_id]

    def for_trauma(self, trauma_id: str) -> list[TraumaShare]:
        return [s for s in self._cache.values() if s.trauma_id == trauma_id]

    def all(self) -> list[TraumaShare]:
        return list(self._cache.values())
