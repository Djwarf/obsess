from __future__ import annotations

from engram.llm import LLM
from engram.obsessions import ObsessionRegistry
from engram.pools import PoolRegistry
from engram.relationships import SharingMode
from engram.shares import TraumaShares
from engram.store import TraumaStore
from engram.types import AccessMode, Obsession, SeedType, SurfacedTrauma, Trauma


TRAUMA_TRIGGER_THRESHOLD = 0.15


def score_obsessions(
    text: str, registry: ObsessionRegistry, llm: LLM
) -> list[tuple[Obsession, float]]:
    """Obsession alignment is a semantic judgment — ask the LLM, not the embedder.
    Batched into a single call. Provision-obsessions amplify; they do not create
    alignment from nothing."""
    active = registry.active()
    if not active:
        return []

    alignments = llm.score_relevance_batch(text, [ob.description for ob in active])

    raw: list[tuple[Obsession, float]] = []
    provision_boost = 0.0
    for ob, alignment in zip(active, alignments):
        score = alignment * ob.commitment
        if ob.identity_level and SeedType.PROVISION in ob.seed_types:
            provision_boost = max(provision_boost, 0.1 * ob.commitment)
        raw.append((ob, score))

    boosted: list[tuple[Obsession, float]] = []
    for ob, s in raw:
        if ob.identity_level and SeedType.PROVISION in ob.seed_types:
            boosted.append((ob, s))
        elif s > 0:
            boosted.append((ob, s + provision_boost))
        else:
            boosted.append((ob, s))
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted


def _fires(
    trauma: Trauma,
    text: str,
    relevant_obsession_ids: list[str],
    llm: LLM,
) -> bool:
    """Firing paths:
    1. Linked to an obsession that is currently active for the agent.
    2. Trigger pattern resembles the current context (LLM-scored)."""
    if trauma.linked_obsession_id and trauma.linked_obsession_id in relevant_obsession_ids:
        return True
    return llm.score_relevance(text, trauma.trigger_pattern) >= TRAUMA_TRIGGER_THRESHOLD


def _render(trauma: Trauma, frame: str, access: AccessMode) -> str:
    """Surface presentation for this agent + frame. Real LLM-driven render for
    FULL (re-synthesis through the inheritor's frame) lands with LlamaCppLLM;
    for now the render is templated — the seam is correct, the content isn't yet."""
    if access == AccessMode.ORIGIN:
        return trauma.failure
    if access == AccessMode.WARNING:
        return f"[warning from agent {trauma.origin_agent_id}] {trauma.failure}"
    if access == AccessMode.FULL:
        return f"[through frame '{frame}', inherited from {trauma.origin_agent_id}] {trauma.failure}"
    if access == AccessMode.POOL:
        return f"[team failure, pool {trauma.pool_id}] {trauma.failure}"
    return trauma.failure


def surface_traumas(
    text: str,
    relevant_obsession_ids: list[str],
    agent_id: str,
    current_frame: str,
    traumas: TraumaStore,
    shares: TraumaShares,
    pools: PoolRegistry,
    llm: LLM,
) -> list[SurfacedTrauma]:
    """Traumas that fire for this agent in the current context. View is the
    union of: (a) origin traumas, (b) pool traumas for pools the agent is in,
    (c) traumas shared to the agent via TraumaShares. Each fired trauma is
    wrapped with its access mode and rendered text."""
    fired: list[SurfacedTrauma] = []
    seen: set[str] = set()

    def consider(t: Trauma, access: AccessMode) -> None:
        if t.id in seen or not t.still_firing:
            return
        if not _fires(t, text, relevant_obsession_ids, llm):
            return
        fired.append(
            SurfacedTrauma(
                trauma=t,
                access=access,
                rendered_text=_render(t, current_frame, access),
            )
        )
        seen.add(t.id)

    # Origin traumas (per-agent, non-pool)
    for t in traumas.for_agent(agent_id):
        consider(t, AccessMode.ORIGIN)

    # Pool traumas for pools this agent is a member of
    for pool in pools.for_member(agent_id):
        for t in traumas.for_pool(pool.id):
            consider(t, AccessMode.POOL)

    # Shared-in traumas (per-agent, non-pool)
    for share in shares.for_recipient(agent_id):
        t = traumas.get(share.trauma_id)
        if t is None or t.pool_id is not None:
            continue
        access = AccessMode.FULL if share.mode == SharingMode.FULL else AccessMode.WARNING
        consider(t, access)

    return fired
