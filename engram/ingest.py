from __future__ import annotations

from typing import Optional

from engram.embed import Embedder
from engram.llm import LLM
from engram.obsessions import ObsessionRegistry
from engram.pools import PoolRegistry
from engram.scoring import score_obsessions, surface_traumas
from engram.shares import TraumaShares
from engram.store import ImpressionStore, TraumaStore
from engram.types import IngestResult, SeedType


ALIGNMENT_THRESHOLD = 0.05


class Ingestor:
    """Utility-gated ingest. Content that doesn't clear the obsession-alignment
    gate is dropped. Trauma warnings that surface during ingest are rendered
    per the agent's access mode (origin/full/warning/pool)."""

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

    def ingest(self, text: str) -> IngestResult:
        scored = score_obsessions(text, self.obsessions, self.llm)
        best = scored[0] if scored else None

        relevant_ob_ids = [o.id for o, s in scored if s >= ALIGNMENT_THRESHOLD][:3]
        frame = self.obsessions.current_frame()
        warnings = surface_traumas(
            text,
            relevant_ob_ids,
            self.agent_id,
            frame,
            self.traumas,
            self.shares,
            self.pools,
            self.llm,
        )

        if best is None or best[1] < ALIGNMENT_THRESHOLD:
            return IngestResult(
                action="dropped",
                trauma_warnings=warnings,
                scored_obsessions=[(o.domain, s) for o, s in scored],
            )

        best_ob, _ = best
        best_ob.touch()
        self.obsessions.persist_activation(best_ob.id)

        if self.llm.detect_failure(text):
            trigger_ctx = f"{best_ob.description} {text}"
            trigger = self.llm.extract_trigger_pattern(trigger_ctx, text)
            trauma = self.traumas.record(
                origin_agent_id=self.agent_id,
                context=text,
                failure=text,
                attempted_solutions=[],
                unsolvable_at_time=True,
                cost="(unspecified — flag later)",
                trigger_pattern=trigger,
                linked_obsession_id=best_ob.id,
            )
            if SeedType.TRAUMA not in best_ob.seed_types:
                best_ob.seed_types.append(SeedType.TRAUMA)
                self.obsessions.persist_activation(best_ob.id)
            return IngestResult(
                action="failure_recorded",
                trauma_recorded=trauma,
                trauma_warnings=warnings,
                scored_obsessions=[(o.domain, s) for o, s in scored],
            )

        impression_text = self.llm.form_impression(text, frame)
        imp = self.impressions.add(
            seed_text=impression_text,
            source_text=text,
            obsession_ids=[best_ob.id],
            frame_at_encode=frame,
        )
        return IngestResult(
            action="stored",
            impression=imp,
            trauma_warnings=warnings,
            scored_obsessions=[(o.domain, s) for o, s in scored],
        )

    def record_failure(
        self,
        context: str,
        failure: str,
        attempted_solutions: list[str],
        cost: str,
        unsolvable_at_time: bool,
        linked_obsession_id: Optional[str] = None,
        pool_id: Optional[str] = None,
    ):
        """Explicit failure recording. If pool_id is set, this is a pool trauma
        (team failure) — caller must verify pool membership before calling."""
        linked = self.obsessions.get(linked_obsession_id) if linked_obsession_id else None
        trigger_ctx = f"{linked.description} {context}" if linked else context
        trigger = self.llm.extract_trigger_pattern(trigger_ctx, failure)
        trauma = self.traumas.record(
            origin_agent_id=self.agent_id,
            context=context,
            failure=failure,
            attempted_solutions=attempted_solutions,
            unsolvable_at_time=unsolvable_at_time,
            cost=cost,
            trigger_pattern=trigger,
            linked_obsession_id=linked_obsession_id,
            pool_id=pool_id,
        )
        return trauma
