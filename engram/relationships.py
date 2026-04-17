from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from engram.evolution import EvolutionStore
from engram.storage import Storage
from engram.storage.memory import InMemoryStorage


class RelationshipKind(str, Enum):
    TEAM = "team"
    PEER = "peer"
    PARENT_CHILD = "parent_child"
    MASTER_PRODIGY = "master_prodigy"


class SharingMode(str, Enum):
    """Per DESIGN-MULTI.md: NONE = invisible to the other agent;
    WARNING = flagged, surfaces with origin tag, no commitment accrual;
    FULL = treated as the receiver's own, render re-synthesized through
    receiver's frame for trauma, commitment accrual for obsessions.
    Impressions are never shared — no SharingMode applies to them."""

    NONE = "none"
    WARNING = "warning"
    FULL = "full"


@dataclass(frozen=True)
class KindMeta:
    """Per-kind invariants: symmetry, decay behavior, and default sharing policy
    per memory type per direction.

    'Down' means information flowing from from_agent_id to to_agent_id.
    'Up' means information flowing from to_agent_id to from_agent_id.
    For symmetric kinds, down and up are the same (the labels are meaningless).
    For directional kinds, the distinction carries DESIGN-MULTI semantics:
    parent's trauma flows down FULL to child; child's trauma flows up WARNING
    to parent."""

    symmetric: bool
    decays: bool
    default_obsession_share_down: SharingMode
    default_obsession_share_up: SharingMode
    default_trauma_share_down: SharingMode
    default_trauma_share_up: SharingMode


KIND_META: dict[RelationshipKind, KindMeta] = {
    # Team: creates a pool. Non-pool sharing defaults to warning; pooled
    # activation/trauma are separate mechanisms (not yet implemented).
    # Decays: pool state decays on unused obsessions; membership persists.
    RelationshipKind.TEAM: KindMeta(
        symmetric=True,
        decays=True,
        default_obsession_share_down=SharingMode.WARNING,
        default_obsession_share_up=SharingMode.WARNING,
        default_trauma_share_down=SharingMode.WARNING,
        default_trauma_share_up=SharingMode.WARNING,
    ),
    # Peer/colleague: visibility-granting, no pool, no inheritance.
    # Defaults to no-share; any sharing is opt-in.
    RelationshipKind.PEER: KindMeta(
        symmetric=True,
        decays=True,
        default_obsession_share_down=SharingMode.NONE,
        default_obsession_share_up=SharingMode.NONE,
        default_trauma_share_down=SharingMode.NONE,
        default_trauma_share_up=SharingMode.NONE,
    ),
    # Parent/child: structural, non-decaying. Obsessions flow downward (full);
    # child's novel obsessions dissolve at teardown (no upward obsession flow).
    # Trauma flows down FULL, up WARNING — the child's scars teach the parent.
    RelationshipKind.PARENT_CHILD: KindMeta(
        symmetric=False,
        decays=False,
        default_obsession_share_down=SharingMode.FULL,
        default_obsession_share_up=SharingMode.NONE,
        default_trauma_share_down=SharingMode.FULL,
        default_trauma_share_up=SharingMode.WARNING,
    ),
    # Master/prodigy: directional, domain-scoped, decaying. Domain scope lives
    # in Relationship.metadata["domain"]. Obsessions flow down FULL (bootstrap);
    # trauma flows down FULL and up WARNING.
    RelationshipKind.MASTER_PRODIGY: KindMeta(
        symmetric=False,
        decays=True,
        default_obsession_share_down=SharingMode.FULL,
        default_obsession_share_up=SharingMode.NONE,
        default_trauma_share_down=SharingMode.FULL,
        default_trauma_share_up=SharingMode.WARNING,
    ),
}


@dataclass
class Relationship:
    id: str
    kind: RelationshipKind
    from_agent_id: str
    to_agent_id: str
    strength: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_activation: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    @property
    def meta(self) -> KindMeta:
        return KIND_META[self.kind]

    def involves(self, agent_id: str) -> bool:
        return agent_id == self.from_agent_id or agent_id == self.to_agent_id

    def other_endpoint(self, agent_id: str) -> str:
        """Return the endpoint that is not the given agent. Raises if the
        agent is not involved."""
        if agent_id == self.from_agent_id:
            return self.to_agent_id
        if agent_id == self.to_agent_id:
            return self.from_agent_id
        raise ValueError(f"agent {agent_id} is not an endpoint of relationship {self.id}")

    def trauma_share_mode_for_origin(self, origin_agent_id: str) -> SharingMode:
        """Given a trauma originated by origin_agent_id, what's the default
        share mode toward the other endpoint of this relationship? Resolves
        direction (down vs up) based on whether origin is from_agent_id."""
        meta = self.meta
        if meta.symmetric:
            return meta.default_trauma_share_down
        if origin_agent_id == self.from_agent_id:
            return meta.default_trauma_share_down
        return meta.default_trauma_share_up


_RELATIONSHIPS_COLLECTION = "relationships"


class RelationshipGraph:
    """Operational store for the relationship graph. Source of truth for
    who-is-related-to-whom. Evolution observes formation events on mutation.
    Queries are flat — per DESIGN-MULTI.md sharing is explicitly non-transitive,
    so no transitive closure is needed.

    Storage-backed. Hydrates on construction."""

    def __init__(self, evolution: EvolutionStore, storage: Optional[Storage] = None):
        self._evolution = evolution
        self._storage: Storage = storage or InMemoryStorage()
        self._rels: dict[str, Relationship] = self._hydrate()

    def _hydrate(self) -> dict[str, Relationship]:
        from engram.storage.serialize import relationship_from_dict  # lazy: avoids circular
        cache: dict[str, Relationship] = {}
        for data in self._storage.all(_RELATIONSHIPS_COLLECTION):
            r = relationship_from_dict(data)
            cache[r.id] = r
        return cache

    def add(
        self,
        kind: RelationshipKind,
        from_agent_id: str,
        to_agent_id: str,
        metadata: Optional[dict] = None,
    ) -> Relationship:
        from engram.storage.serialize import relationship_to_dict
        if from_agent_id == to_agent_id:
            raise ValueError("A relationship cannot have the same agent on both ends")
        rel = Relationship(
            id=str(uuid.uuid4()),
            kind=kind,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            metadata=dict(metadata or {}),
        )
        self._rels[rel.id] = rel
        self._storage.put(_RELATIONSHIPS_COLLECTION, rel.id, relationship_to_dict(rel))
        self._evolution.append(
            "relationship_formed",
            {
                "relationship_id": rel.id,
                "kind": rel.kind.value,
                "from_agent_id": rel.from_agent_id,
                "to_agent_id": rel.to_agent_id,
                "metadata": dict(rel.metadata),
            },
            agent_id=None,
        )
        return rel

    def get(self, relationship_id: str) -> Optional[Relationship]:
        return self._rels.get(relationship_id)

    def all(self) -> list[Relationship]:
        return list(self._rels.values())

    def for_agent(
        self,
        agent_id: str,
        kind: Optional[RelationshipKind] = None,
    ) -> list[Relationship]:
        results = [r for r in self._rels.values() if r.involves(agent_id)]
        if kind is not None:
            results = [r for r in results if r.kind == kind]
        return results

    def between(
        self,
        agent_a: str,
        agent_b: str,
        kind: Optional[RelationshipKind] = None,
    ) -> list[Relationship]:
        results = [
            r for r in self._rels.values()
            if (r.from_agent_id == agent_a and r.to_agent_id == agent_b)
            or (r.from_agent_id == agent_b and r.to_agent_id == agent_a)
        ]
        if kind is not None:
            results = [r for r in results if r.kind == kind]
        return results
