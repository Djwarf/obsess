from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from engram.llm import LLM
from engram.memory import Memory
from engram.types import Obsession, SeedType

if TYPE_CHECKING:
    from engram.population import Population


class CreatorPolicy(str, Enum):
    """How Creator responds when a proposed agent's config matches a prior
    failure pattern in Evolution's store.

    WARN:   proceed with the spawn; warnings appear in CreatorResult.
    REFUSE: raise FailureRegistryMatch before spawning.
    IGNORE: skip the failure-registry query entirely."""

    WARN = "warn"
    REFUSE = "refuse"
    IGNORE = "ignore"


class FailureRegistryMatch(Exception):
    """Raised by Creator when policy is REFUSE and the proposed config matches
    one or more prior failures."""


@dataclass
class ObsessionSpec:
    """A proposed obsession for a new agent. Either a private seed (domain +
    description, stored in the agent's ObsessionRegistry) or an activation
    against an existing shared definition (shared_definition_id set; domain
    and description can be left empty — they're read from the definition)."""

    domain: str = ""
    description: str = ""
    seed_types: list[SeedType] = field(default_factory=list)
    commitment: float = 0.7
    identity_level: bool = False
    seed_metadata: Optional[dict] = None
    shared_definition_id: Optional[str] = None


@dataclass
class FailureRegistryHit:
    """A prior agent whose config (obsession domains) overlaps with a newly
    proposed config AND who recorded at least one failure. The 'warning' Creator
    surfaces before (or instead of) spawning."""

    prior_agent_id: str
    overlapping_domains: list[str]
    failure_count: int


@dataclass
class CreatorResult:
    agent: Memory
    warnings: list[FailureRegistryHit]


class Creator:
    """System component that produces new agents. All-knowing (no bounded
    attention) and has no memory of its own — every decision queries
    Evolution's store.

    Before each spawn, Creator checks the failure-registry view: past agents
    whose obsession domains overlap with the proposed config AND who accumulated
    failure_recorded events. The response to a hit is governed by CreatorPolicy.

    Creator itself is exogenous — configured by the system builder at
    Population construction. No Creator-on-Creator lineage in v1."""

    def __init__(
        self,
        population: "Population",
        policy: CreatorPolicy = CreatorPolicy.WARN,
    ):
        self._pop = population
        self.policy = policy

    def propose(
        self,
        agent_id: str,
        obsessions: list[ObsessionSpec],
        llm: Optional[LLM] = None,
    ) -> CreatorResult:
        proposed_domains = [self._resolve_domain(spec) for spec in obsessions]

        self._pop.evolution.append(
            "agent_proposed",
            {"domains": proposed_domains},
            agent_id=agent_id,
        )

        warnings = self._check_failure_registry(proposed_domains)

        if warnings and self.policy == CreatorPolicy.REFUSE:
            self._pop.evolution.append(
                "agent_refused",
                {
                    "reason": "failure_registry_match",
                    "prior_agents": [w.prior_agent_id for w in warnings],
                },
                agent_id=agent_id,
            )
            raise FailureRegistryMatch(
                f"Creator policy REFUSE: {len(warnings)} prior-failure match(es) "
                f"for proposed config {proposed_domains}"
            )

        agent = self._pop.spawn(agent_id, llm=llm)
        for spec in obsessions:
            self._apply_obsession(agent, spec)

        self._pop.evolution.append(
            "agent_created",
            {
                "domains": proposed_domains,
                "commitments": {
                    d: spec.commitment
                    for d, spec in zip(proposed_domains, obsessions)
                },
            },
            agent_id=agent_id,
        )

        return CreatorResult(agent=agent, warnings=warnings)

    def _resolve_domain(self, spec: ObsessionSpec) -> str:
        if spec.shared_definition_id is None:
            return spec.domain
        defn = self._pop.shared_obsessions.get(spec.shared_definition_id)
        if defn is None:
            raise KeyError(
                f"ObsessionSpec references unknown shared definition {spec.shared_definition_id}"
            )
        return defn.domain

    def _apply_obsession(self, agent: Memory, spec: ObsessionSpec) -> Obsession:
        if spec.shared_definition_id is not None:
            return agent.activate_shared_obsession(
                spec.shared_definition_id,
                seed_types=list(spec.seed_types),
                commitment=spec.commitment,
            )
        return agent.seed_obsession(
            domain=spec.domain,
            description=spec.description,
            seed_types=list(spec.seed_types),
            commitment=spec.commitment,
            identity_level=spec.identity_level,
            seed_metadata=spec.seed_metadata,
        )

    def _check_failure_registry(
        self, proposed_domains: list[str]
    ) -> list[FailureRegistryHit]:
        if self.policy == CreatorPolicy.IGNORE:
            return []

        failure_counts: dict[str, int] = {}
        for ev in self._pop.evolution.query(kind="failure_recorded"):
            if ev.agent_id:
                failure_counts[ev.agent_id] = failure_counts.get(ev.agent_id, 0) + 1

        proposed_set = set(proposed_domains)
        hits: list[FailureRegistryHit] = []
        for ev in self._pop.evolution.query(kind="agent_created"):
            prior_agent = ev.agent_id
            if not prior_agent:
                continue
            prior_domains = ev.payload.get("domains", [])
            overlap = proposed_set & set(prior_domains)
            if not overlap:
                continue
            fcount = failure_counts.get(prior_agent, 0)
            if fcount == 0:
                continue
            hits.append(
                FailureRegistryHit(
                    prior_agent_id=prior_agent,
                    overlapping_domains=sorted(overlap),
                    failure_count=fcount,
                )
            )
        return hits
