from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from engram.pools import Pool
from engram.relationships import Relationship, RelationshipKind

if TYPE_CHECKING:
    from engram.population import Population


class Bonding:
    """System component that produces relationships between agents. Core +
    pluggable strategies (DESIGN-META.md). Every strategy ultimately routes
    through Population.form_relationship or PoolRegistry.add so that
    propagation, events, and graph consistency come for free.

    v1 strategies: genetic, teambuild, hiring, luck. Others (apprenticeship,
    rival, mentor-of-mentor, ...) are extensions via subclass or additional
    methods without changing the core."""

    def __init__(
        self,
        population: "Population",
        rng: Optional[random.Random] = None,
    ):
        self._pop = population
        self._rng = rng or random.Random()

    def genetic(
        self,
        parent_id: str,
        child_id: str,
        metadata: Optional[dict] = None,
    ) -> Relationship:
        """Record a PARENT_CHILD edge. Typically called at spawn time, once
        Creator has produced the child agent."""
        return self._pop.form_relationship(
            RelationshipKind.PARENT_CHILD, parent_id, child_id, metadata
        )

    def teambuild(self, name: str, members: list[str]) -> Pool:
        """Create a named pool and form pairwise TEAM edges between all members.
        Pool-scoped obsessions are defined separately (via
        pop.shared_obsessions.define(owner_pool_id=pool.id)) after the pool
        exists; members activate against them with activate_shared_obsession."""
        for m in members:
            if m not in self._pop._agents:
                raise ValueError(f"teambuild member {m} is not spawned")
        if len(members) < 2:
            raise ValueError("teambuild requires at least 2 members")

        pool = self._pop.pools.add(name=name, member_ids=members)
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                self._pop.form_relationship(RelationshipKind.TEAM, a, b)
        return pool

    def hiring(
        self,
        requester_id: str,
        domain_need: str,
        min_commitment: float = 0.3,
    ) -> Optional[Relationship]:
        """Find an agent whose obsessions include `domain_need` with commitment
        at or above `min_commitment`, and form a PEER relationship with the
        requester. Skips retired agents and self. Returns None if no candidate
        qualifies; returns the existing PEER edge if one already exists."""
        candidates: list[tuple[str, float]] = []
        for agent_id, mem in self._pop._agents.items():
            if agent_id == requester_id or agent_id in self._pop.retired_ids:
                continue
            for ob in mem.obsessions.all():
                if ob.domain == domain_need and ob.commitment >= min_commitment:
                    candidates.append((agent_id, ob.commitment))
                    break

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[1])
        best = candidates[0][0]

        existing = self._pop.relationships.between(
            requester_id, best, kind=RelationshipKind.PEER
        )
        if existing:
            return existing[0]

        return self._pop.form_relationship(
            RelationshipKind.PEER, requester_id, best
        )

    def luck(
        self,
        candidates: list[str],
        kind: RelationshipKind = RelationshipKind.PEER,
        p: float = 0.1,
    ) -> list[Relationship]:
        """For each unordered pair in `candidates`, with probability `p`, form
        a relationship of the given kind. Deterministic under a seeded RNG.
        Skips self-pairs, retired agents, and duplicates."""
        formed: list[Relationship] = []
        valid = [
            c for c in candidates
            if c in self._pop._agents and c not in self._pop.retired_ids
        ]
        for i, a in enumerate(valid):
            for b in valid[i + 1:]:
                if self._rng.random() >= p:
                    continue
                if self._pop.relationships.between(a, b, kind=kind):
                    continue
                formed.append(self._pop.form_relationship(kind, a, b))
        return formed
