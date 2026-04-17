from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from obsess.population import Population


@dataclass
class SelectionReport:
    """Result of one selection pass. Inspection-friendly — tests and callers
    can read what happened without parsing events."""

    retired: list[str] = field(default_factory=list)
    promoted_configs: list[tuple[str, ...]] = field(default_factory=list)
    failure_counts: dict[str, int] = field(default_factory=dict)
    total_agents: int = 0


class Selection:
    """Evolution's selection pass. Caller-driven cadence — call run() daily,
    on-demand, or whenever population-level reasoning is warranted.

    Observation is handled continuously by EvolutionStore. Selection is the
    periodic synthesis: reads events, identifies agents exceeding a failure
    threshold (retirement), identifies configs with clean outcomes
    (promotion), emits agent_retired and config_promoted events, and returns
    a report. Does not modify running agents' internal state — retirement is
    advisory (Population.retired_ids gets updated; callers may honor it)."""

    def __init__(self, population: "Population", retire_threshold: int = 3):
        self._pop = population
        self._retire_threshold = retire_threshold
        self._promoted: set[tuple[str, ...]] = set()

    def run(self) -> SelectionReport:
        failure_counts: dict[str, int] = {}
        for ev in self._pop.evolution.query(kind="failure_recorded"):
            if ev.agent_id:
                failure_counts[ev.agent_id] = failure_counts.get(ev.agent_id, 0) + 1

        retired_now: list[str] = []
        for agent_id, count in failure_counts.items():
            if count < self._retire_threshold:
                continue
            if agent_id in self._pop.retired_ids:
                continue
            self._pop.retired_ids.add(agent_id)
            retired_now.append(agent_id)
            self._pop.evolution.append(
                "agent_retired",
                {"failure_count": count, "threshold": self._retire_threshold},
                agent_id=agent_id,
            )

        promotions_now: list[tuple[str, ...]] = []
        for ev in self._pop.evolution.query(kind="agent_created"):
            prior_agent = ev.agent_id
            if not prior_agent:
                continue
            if failure_counts.get(prior_agent, 0) > 0:
                continue
            if prior_agent in self._pop.retired_ids:
                continue
            domains = ev.payload.get("domains", [])
            if not domains:
                continue
            config_sig = tuple(sorted(domains))
            if config_sig in self._promoted:
                continue
            self._promoted.add(config_sig)
            promotions_now.append(config_sig)
            self._pop.evolution.append(
                "config_promoted",
                {"domains": list(config_sig), "example_agent_id": prior_agent},
                agent_id=None,
            )

        return SelectionReport(
            retired=retired_now,
            promoted_configs=promotions_now,
            failure_counts=dict(failure_counts),
            total_agents=len(self._pop._agents),
        )
