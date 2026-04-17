from __future__ import annotations

from obsess.embed import Embedder
from obsess.llm import LLM
from obsess.obsessions import ObsessionRegistry
from obsess.pools import PoolRegistry
from obsess.scoring import score_obsessions, surface_traumas
from obsess.shares import TraumaShares
from obsess.store import ImpressionStore, TraumaStore
from obsess.types import QueryResult


ALIGNMENT_THRESHOLD = 0.05


class Retriever:
    """Retrieval is regeneration, not playback. Impressions are seeds; the answer
    is re-synthesized through the *current* obsession frame."""

    def __init__(
        self,
        obsessions: ObsessionRegistry,
        impressions: ImpressionStore,
        traumas: TraumaStore,
        shares: TraumaShares,
        pools: PoolRegistry,
        llm: LLM,
        embedder: Embedder,
    ):
        self.obsessions = obsessions
        self.impressions = impressions
        self.traumas = traumas
        self.shares = shares
        self.pools = pools
        self.llm = llm
        self.embedder = embedder

    @property
    def agent_id(self) -> str:
        return self.obsessions.agent_id

    def query(self, q: str, k: int = 5) -> QueryResult:
        scored = score_obsessions(q, self.obsessions, self.llm)
        relevant_ob_ids = [o.id for o, s in scored if s >= ALIGNMENT_THRESHOLD][:3]

        frame = self.obsessions.current_frame()
        surfaced = surface_traumas(
            q,
            relevant_ob_ids,
            self.agent_id,
            frame,
            self.traumas,
            self.shares,
            self.pools,
            self.llm,
        )

        q_emb = self.embedder.embed(q, role="query")
        hits = self.impressions.search(q_emb, obsession_ids=relevant_ob_ids or None, k=k)
        impressions = [imp for imp, _ in hits]

        answer = self.llm.regenerate(
            impressions=[imp.seed_text for imp in impressions],
            query=q,
            frame=frame,
        )

        return QueryResult(
            answer=answer,
            impressions_used=impressions,
            trauma_surfaced=surfaced,
            current_frame=frame,
        )
