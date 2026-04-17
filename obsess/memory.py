from __future__ import annotations

from typing import Optional

from obsess.embed import Embedder, HashEmbedder
from obsess.evolution import EvolutionStore
from obsess.ingest import Ingestor
from obsess.llm import LLM, MockLLM
from obsess.obsessions import ObsessionRegistry
from obsess.pools import Pool, PoolRegistry
from obsess.relationships import Relationship, RelationshipGraph, RelationshipKind, SharingMode
from obsess.retrieve import Retriever
from obsess.shared import SharedObsessions
from obsess.shares import TraumaShares
from obsess.storage import Storage
from obsess.storage.memory import InMemoryStorage
from obsess.store import ImpressionStore, TraumaStore
from obsess.types import IngestResult, Obsession, QueryResult, SeedType, Trauma


class Memory:
    """Per-agent facade. The boundary where per-agent observability meets
    population-level state: impressions are strictly private; obsessions and
    traumas may be private, shared, or pooled. On failure, propagation writes
    share records along relationship edges (non-pool traumas) or stamps
    pool_id (pool traumas)."""

    def __init__(
        self,
        agent_id: str,
        evolution: EvolutionStore,
        relationships: RelationshipGraph,
        shared_obsessions: SharedObsessions,
        traumas: TraumaStore,
        trauma_shares: TraumaShares,
        pools: PoolRegistry,
        storage: Optional[Storage] = None,
        llm: Optional[LLM] = None,
        embedder: Optional[Embedder] = None,
        _is_rehydrate: bool = False,
    ):
        self.agent_id = agent_id
        self.evolution = evolution
        self.relationships = relationships
        self.shared_obsessions = shared_obsessions
        self.traumas = traumas
        self.trauma_shares = trauma_shares
        self.pools = pools
        self.storage = storage or InMemoryStorage()
        self.embedder = embedder or HashEmbedder()
        self.llm = llm or MockLLM()
        self.obsessions = ObsessionRegistry(
            self.embedder, self.agent_id, self.shared_obsessions, storage=self.storage
        )
        self.impressions = ImpressionStore(
            self.embedder, self.agent_id, storage=self.storage
        )
        self._ingestor = Ingestor(
            self.obsessions,
            self.impressions,
            self.traumas,
            self.trauma_shares,
            self.pools,
            self.llm,
            self.embedder,
        )
        self._retriever = Retriever(
            self.obsessions,
            self.impressions,
            self.traumas,
            self.trauma_shares,
            self.pools,
            self.llm,
            self.embedder,
        )

        if not _is_rehydrate:
            self.evolution.append("spawn", {}, agent_id=self.agent_id)

    # --- read-through convenience handles ---

    def my_relationships(
        self, kind: Optional[RelationshipKind] = None
    ) -> list[Relationship]:
        return self.relationships.for_agent(self.agent_id, kind=kind)

    def my_traumas(self) -> list[Trauma]:
        return self.traumas.for_agent(self.agent_id)

    def my_pools(self) -> list[Pool]:
        return self.pools.for_member(self.agent_id)

    # --- obsession creation ---

    def seed_obsession(
        self,
        domain: str,
        description: str,
        seed_types: list[SeedType],
        commitment: float = 0.7,
        identity_level: bool = False,
        seed_metadata: Optional[dict] = None,
    ) -> Obsession:
        return self.obsessions.seed(
            domain=domain,
            description=description,
            seed_types=seed_types,
            commitment=commitment,
            identity_level=identity_level,
            seed_metadata=seed_metadata,
        )

    def activate_shared_obsession(
        self,
        definition_id: str,
        seed_types: list[SeedType],
        commitment: float = 0.7,
    ) -> Obsession:
        """Commit to a shared obsession. If the definition is pool-scoped, the
        agent must be a member of the owning pool."""
        defn = self.shared_obsessions.get(definition_id)
        if defn is None:
            raise KeyError(definition_id)
        if defn.owner_pool_id is not None:
            if not self.pools.is_member(defn.owner_pool_id, self.agent_id):
                raise PermissionError(
                    f"agent {self.agent_id} is not a member of pool {defn.owner_pool_id}"
                )
        ob = self.obsessions.activate_shared(definition_id, seed_types, commitment)
        self.evolution.append(
            "shared_obsession_activated",
            {"definition_id": definition_id, "owner_pool_id": defn.owner_pool_id},
            agent_id=self.agent_id,
        )
        return ob

    # --- ingest / retrieve ---

    def ingest(self, text: str) -> IngestResult:
        result = self._ingestor.ingest(text)
        for st in result.trauma_warnings:
            self.evolution.append(
                "trauma_fired",
                {
                    "trauma_id": st.trauma.id,
                    "surfaced_in": "ingest",
                    "access": st.access.value,
                },
                agent_id=self.agent_id,
            )
        if result.trauma_recorded is not None:
            self._emit_and_propagate_failure(result.trauma_recorded)
        return result

    def record_failure(
        self,
        context: str,
        failure: str,
        attempted_solutions: list[str],
        cost: str,
        unsolvable_at_time: bool = True,
        linked_obsession_id: Optional[str] = None,
        pool_id: Optional[str] = None,
    ) -> Trauma:
        """Record a failure. If pool_id is set, produces a pool trauma —
        recorder must be a pool member; access is granted to all pool members
        (not via TraumaShares)."""
        if pool_id is not None and not self.pools.is_member(pool_id, self.agent_id):
            raise PermissionError(
                f"agent {self.agent_id} is not a member of pool {pool_id}"
            )
        trauma = self._ingestor.record_failure(
            context=context,
            failure=failure,
            attempted_solutions=attempted_solutions,
            cost=cost,
            unsolvable_at_time=unsolvable_at_time,
            linked_obsession_id=linked_obsession_id,
            pool_id=pool_id,
        )
        self._emit_and_propagate_failure(trauma)
        return trauma

    def resolve_with_tradeoff(self, trauma_id: str, tradeoff: str) -> None:
        """Append a resolution tradeoff. For per-agent traumas, only the origin
        may resolve. For pool traumas, any member of the owning pool may
        resolve — the resolution belongs to the collective."""
        t = self.traumas.get(trauma_id)
        if t is None:
            raise KeyError(trauma_id)
        if t.pool_id is not None:
            if not self.pools.is_member(t.pool_id, self.agent_id):
                raise PermissionError(
                    f"agent {self.agent_id} is not a member of pool {t.pool_id}"
                )
        else:
            if t.origin_agent_id != self.agent_id:
                raise PermissionError(
                    f"agent {self.agent_id} cannot resolve trauma originated by {t.origin_agent_id}"
                )
        self.traumas.append_resolution(trauma_id, tradeoff)
        self.evolution.append(
            "trauma_resolved",
            {"trauma_id": trauma_id},
            agent_id=self.agent_id,
        )

    def query(self, q: str, k: int = 5) -> QueryResult:
        result = self._retriever.query(q, k=k)
        for st in result.trauma_surfaced:
            self.evolution.append(
                "trauma_fired",
                {
                    "trauma_id": st.trauma.id,
                    "surfaced_in": "query",
                    "access": st.access.value,
                },
                agent_id=self.agent_id,
            )
        return result

    # --- internals ---

    def _emit_and_propagate_failure(self, trauma: Trauma) -> None:
        self.evolution.append(
            "failure_recorded",
            {
                "trauma_id": trauma.id,
                "linked_obsession_id": trauma.linked_obsession_id,
                "unsolvable_at_time": trauma.unsolvable_at_time,
                "pool_id": trauma.pool_id,
            },
            agent_id=self.agent_id,
        )
        # Pool traumas don't propagate via TraumaShares — access is via pool membership
        if trauma.pool_id is not None:
            return
        self._propagate_trauma(trauma)

    def _propagate_trauma(self, trauma: Trauma) -> None:
        """Walk this agent's relationships; for each edge whose trauma-share
        default (in the direction this origin points) is non-NONE, write a
        share record."""
        for rel in self.relationships.for_agent(self.agent_id):
            mode = rel.trauma_share_mode_for_origin(self.agent_id)
            if mode == SharingMode.NONE:
                continue
            recipient = rel.other_endpoint(self.agent_id)
            self.trauma_shares.add(
                trauma_id=trauma.id,
                recipient_agent_id=recipient,
                origin_agent_id=self.agent_id,
                mode=mode,
                via_relationship_id=rel.id,
            )

    # --- snapshot for the demo/cli ---

    def snapshot(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "pools": [{"id": p.id, "name": p.name} for p in self.my_pools()],
            "obsessions": [
                {
                    "domain": o.domain,
                    "commitment": round(o.commitment, 3),
                    "earned": round(o.activation.earned_commitment, 3),
                    "bootstrapped": round(o.activation.bootstrapped_commitment, 3),
                    "seeds": [s.value for s in o.seed_types],
                    "identity_level": o.identity_level,
                    "pool_id": o.owner_pool_id,
                }
                for o in self.obsessions.all()
            ],
            "impressions": [
                {"obsessions": imp.obsession_ids, "frame": imp.frame_at_encode, "seed": imp.seed_text}
                for imp in self.impressions.all()
            ],
            "traumas": [
                {
                    "failure": t.failure[:80],
                    "trigger": t.trigger_pattern,
                    "still_firing": t.still_firing,
                    "tradeoffs": t.resolution_tradeoffs,
                    "pool_id": t.pool_id,
                }
                for t in self.my_traumas()
            ],
            "current_frame": self.obsessions.current_frame(),
        }
