from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from obsess.bonding import Bonding
from obsess.creator import Creator, CreatorPolicy
from obsess.embed import Embedder, HashEmbedder
from obsess.evolution import EvolutionStore
from obsess.llm import LLM
from obsess.memory import Memory
from obsess.pools import PoolRegistry
from obsess.relationships import (
    KIND_META,
    Relationship,
    RelationshipGraph,
    RelationshipKind,
    SharingMode,
)
from obsess.selection import Selection
from obsess.shared import SharedObsessions
from obsess.shares import TraumaShares
from obsess.storage import Storage
from obsess.storage.memory import InMemoryStorage
from obsess.store import TraumaStore


_DEFAULT_ATTENUATION: dict[RelationshipKind, float] = {
    RelationshipKind.MASTER_PRODIGY: 1.0,
    RelationshipKind.PARENT_CHILD: 0.5,
}


@dataclass
class Population:
    """One obsess installation = one Population. Storage-backed: pass any
    Storage implementation (InMemoryStorage, SQLiteStorage, or your own) and
    every store in the population persists to it. When constructing on an
    existing SQLite file, shared stores automatically hydrate; per-agent
    state (ObsessionRegistry, ImpressionStore) hydrates when the agent is
    rehydrated via Population.rehydrate_agent."""

    embedder: Embedder
    evolution: EvolutionStore
    relationships: RelationshipGraph
    shared_obsessions: SharedObsessions
    traumas: TraumaStore
    trauma_shares: TraumaShares
    pools: PoolRegistry
    storage: Storage
    _agents: dict[str, Memory] = field(default_factory=dict)
    retired_ids: set[str] = field(default_factory=set)
    creator: Creator = field(init=False)
    bonding: Bonding = field(init=False)
    selection: Selection = field(init=False)

    @classmethod
    def new(
        cls,
        embedder: Optional[Embedder] = None,
        storage: Optional[Storage] = None,
        creator_policy: CreatorPolicy = CreatorPolicy.WARN,
        retire_threshold: int = 3,
        bonding_rng: Optional[random.Random] = None,
    ) -> "Population":
        embedder = embedder or HashEmbedder()
        storage = storage or InMemoryStorage()
        evolution = EvolutionStore(storage=storage)
        relationships = RelationshipGraph(evolution, storage=storage)
        shared_obsessions = SharedObsessions(embedder, evolution, storage=storage)
        traumas = TraumaStore(embedder, storage=storage)
        trauma_shares = TraumaShares(evolution, storage=storage)
        pools = PoolRegistry(evolution, storage=storage)
        pop = cls(
            embedder=embedder,
            evolution=evolution,
            relationships=relationships,
            shared_obsessions=shared_obsessions,
            traumas=traumas,
            trauma_shares=trauma_shares,
            pools=pools,
            storage=storage,
        )
        pop.creator = Creator(pop, policy=creator_policy)
        pop.bonding = Bonding(pop, rng=bonding_rng)
        pop.selection = Selection(pop, retire_threshold=retire_threshold)
        # Hydrate retired_ids from agent_retired events if this is a reloaded DB
        pop._hydrate_retired_ids()
        return pop

    def __post_init__(self) -> None:
        if self.__dict__.get("creator") is None:
            self.creator = Creator(self)
        if self.__dict__.get("bonding") is None:
            self.bonding = Bonding(self)
        if self.__dict__.get("selection") is None:
            self.selection = Selection(self)

    def _hydrate_retired_ids(self) -> None:
        for ev in self.evolution.query(kind="agent_retired"):
            if ev.agent_id:
                self.retired_ids.add(ev.agent_id)

    def spawn(self, agent_id: str, llm: Optional[LLM] = None) -> Memory:
        if agent_id in self._agents:
            raise ValueError(f"agent {agent_id} already spawned")
        mem = Memory(
            agent_id=agent_id,
            evolution=self.evolution,
            relationships=self.relationships,
            shared_obsessions=self.shared_obsessions,
            traumas=self.traumas,
            trauma_shares=self.trauma_shares,
            pools=self.pools,
            storage=self.storage,
            embedder=self.embedder,
            llm=llm,
        )
        self._agents[agent_id] = mem
        return mem

    def rehydrate_agent(self, agent_id: str, llm: Optional[LLM] = None) -> Memory:
        """Reconstruct a Memory for an agent whose state lives in storage
        (from a prior session). Does NOT emit a spawn event — rehydration
        is a runtime restoration, not a birth."""
        if agent_id in self._agents:
            return self._agents[agent_id]
        mem = Memory(
            agent_id=agent_id,
            evolution=self.evolution,
            relationships=self.relationships,
            shared_obsessions=self.shared_obsessions,
            traumas=self.traumas,
            trauma_shares=self.trauma_shares,
            pools=self.pools,
            storage=self.storage,
            embedder=self.embedder,
            llm=llm,
            _is_rehydrate=True,
        )
        self._agents[agent_id] = mem
        return mem

    def agent_ids_on_record(self) -> list[str]:
        """Agent IDs that have been spawned at some point (from spawn events).
        Useful after constructing a Population on an existing storage to
        discover which agents to rehydrate."""
        return list({
            ev.agent_id for ev in self.evolution.query(kind="spawn")
            if ev.agent_id
        })

    def get_agent(self, agent_id: str) -> Optional[Memory]:
        return self._agents.get(agent_id)

    def agent_ids(self) -> list[str]:
        return list(self._agents.keys())

    def close(self) -> None:
        self.storage.close()

    def form_relationship(
        self,
        kind: RelationshipKind,
        from_agent_id: str,
        to_agent_id: str,
        metadata: Optional[dict] = None,
    ) -> Relationship:
        if from_agent_id not in self._agents:
            raise ValueError(f"agent {from_agent_id} is not spawned")
        if to_agent_id not in self._agents:
            raise ValueError(f"agent {to_agent_id} is not spawned")

        rel = self.relationships.add(kind, from_agent_id, to_agent_id, metadata)
        self._propagate_obsessions_on_formation(rel)
        return rel

    def _propagate_obsessions_on_formation(self, rel: Relationship) -> None:
        meta = KIND_META[rel.kind]
        attenuation = self._attenuation_for(rel)

        if meta.default_obsession_share_down == SharingMode.FULL:
            self._propagate_obsessions_between(
                rel, rel.from_agent_id, rel.to_agent_id, attenuation
            )
        if meta.default_obsession_share_up == SharingMode.FULL:
            self._propagate_obsessions_between(
                rel, rel.to_agent_id, rel.from_agent_id, attenuation
            )

    def _propagate_obsessions_between(
        self,
        rel: Relationship,
        source_id: str,
        target_id: str,
        attenuation: float,
    ) -> None:
        source = self._agents[source_id]
        target = self._agents[target_id]

        for source_ob in source.obsessions.all():
            if source_ob.owner_pool_id is not None:
                continue
            if not self.shared_obsessions.has(source_ob.id):
                continue
            if target.obsessions.get(source_ob.id) is not None:
                continue

            bootstrapped = source_ob.commitment * attenuation
            target.obsessions.activate_shared(
                definition_id=source_ob.id,
                seed_types=[],
                commitment=0.0,
                bootstrapped_commitment=bootstrapped,
            )
            self.evolution.append(
                "obsession_propagated",
                {
                    "definition_id": source_ob.id,
                    "from_agent_id": source_id,
                    "to_agent_id": target_id,
                    "bootstrapped_commitment": bootstrapped,
                    "attenuation": attenuation,
                    "via_relationship_id": rel.id,
                },
                agent_id=target_id,
            )

    @staticmethod
    def _attenuation_for(rel: Relationship) -> float:
        if "attenuation" in rel.metadata:
            return float(rel.metadata["attenuation"])
        return _DEFAULT_ATTENUATION.get(rel.kind, 1.0)
