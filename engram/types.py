from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SeedType(str, Enum):
    TRAUMA = "trauma"
    CURIOSITY = "curiosity"
    NEED_FOR_SUCCESS = "need_for_success"
    DELIBERATE_STUDY = "deliberate_study"
    BEST_IN_WORLD = "best_in_world"
    PROVISION = "provision"


class AccessMode(str, Enum):
    """How this agent accesses a surfacing trauma.

    ORIGIN: the agent lived it — verbatim render, immune to current-frame narrative rewriting.
    FULL: full-share inheritance — render re-synthesized through the inheritor's current frame.
    WARNING: warning-share inheritance — origin-tagged flag, not claimed as own experience.
    POOL: pool member accessing a pool trauma — 'our failure' framing with (future) slice attribution."""

    ORIGIN = "origin"
    FULL = "full"
    WARNING = "warning"
    POOL = "pool"


@dataclass
class ObsessionDefinition:
    """Identity of an obsession. Shared across agents that share the obsession;
    invariant to any single agent's activity. If owner_pool_id is set, this
    definition is pool-scoped — only pool members may activate against it."""

    id: str
    domain: str
    description: str
    identity_level: bool = False
    seed_metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    owner_pool_id: Optional[str] = None


@dataclass
class ObsessionActivation:
    """An agent's relationship to an obsession — always per-agent."""

    obsession_id: str
    agent_id: str
    seed_types: list[SeedType] = field(default_factory=list)
    earned_commitment: float = 0.0
    bootstrapped_commitment: float = 0.0
    last_activation: float = field(default_factory=time.time)
    decay_rate: float = 0.01

    @property
    def commitment(self) -> float:
        return self.earned_commitment + self.bootstrapped_commitment

    def touch(self) -> None:
        self.last_activation = time.time()


@dataclass
class Obsession:
    """Joined view: definition + this agent's activation against it."""

    definition: ObsessionDefinition
    activation: ObsessionActivation

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def domain(self) -> str:
        return self.definition.domain

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def identity_level(self) -> bool:
        return self.definition.identity_level

    @property
    def seed_metadata(self) -> dict:
        return self.definition.seed_metadata

    @property
    def embedding(self) -> Optional[list[float]]:
        return self.definition.embedding

    @property
    def owner_pool_id(self) -> Optional[str]:
        return self.definition.owner_pool_id

    @property
    def agent_id(self) -> str:
        return self.activation.agent_id

    @property
    def seed_types(self) -> list[SeedType]:
        return self.activation.seed_types

    @property
    def commitment(self) -> float:
        return self.activation.commitment

    @property
    def last_activation(self) -> float:
        return self.activation.last_activation

    @property
    def decay_rate(self) -> float:
        return self.activation.decay_rate

    def touch(self) -> None:
        self.activation.touch()

    def decay(self, now: Optional[float] = None) -> None:
        if self.definition.identity_level:
            return
        now = now or time.time()
        elapsed_days = (now - self.activation.last_activation) / 86400.0
        self.activation.earned_commitment = max(
            0.0,
            self.activation.earned_commitment - self.activation.decay_rate * elapsed_days,
        )


@dataclass
class Impression:
    """Always per-agent. Never shared."""

    id: str
    seed_text: str
    source_text: str
    obsession_ids: list[str]
    frame_at_encode: str
    agent_id: str
    created_at: float = field(default_factory=time.time)
    embedding: Optional[list[float]] = None


@dataclass
class Trauma:
    """Verbatim record of a failure. Record is immutable/append-only; render
    is produced at firing time by a SurfacedTrauma. If pool_id is set, this
    is a pooled trauma (team failure) — origin_agent_id is still the recorder,
    but access is via pool membership rather than per-agent share."""

    id: str
    context: str
    failure: str
    attempted_solutions: list[str]
    unsolvable_at_time: bool
    cost: str
    trigger_pattern: str
    linked_obsession_id: Optional[str]
    origin_agent_id: str
    resolution_tradeoffs: list[str] = field(default_factory=list)
    still_firing: bool = True
    created_at: float = field(default_factory=time.time)
    embedding: Optional[list[float]] = None
    pool_id: Optional[str] = None


@dataclass
class SurfacedTrauma:
    """A trauma as it surfaces for a particular agent in a particular context.
    Wraps the immutable record with the access mode (how this agent sees it)
    and the rendered text (the surface presentation for this agent + frame).
    Render rules:
      ORIGIN   → verbatim (trauma.failure)
      WARNING  → origin-tagged summary
      FULL     → re-synthesized through the inheritor's current frame
      POOL     → team-failure framing (slice attribution is a future refinement)"""

    trauma: Trauma
    access: AccessMode
    rendered_text: str


@dataclass
class IngestResult:
    action: str  # "stored" | "dropped" | "failure_recorded"
    impression: Optional[Impression] = None
    trauma_recorded: Optional[Trauma] = None
    trauma_warnings: list[SurfacedTrauma] = field(default_factory=list)
    scored_obsessions: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class QueryResult:
    answer: str
    impressions_used: list[Impression]
    trauma_surfaced: list[SurfacedTrauma]
    current_frame: str
