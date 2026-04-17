from __future__ import annotations

import unittest

from obsess.creator import ObsessionSpec
from obsess.population import Population
from obsess.types import SeedType


def _spec(domain: str) -> ObsessionSpec:
    return ObsessionSpec(
        domain=domain,
        description=f"{domain} details entropy thermodynamics",
        seed_types=[SeedType.NEED_FOR_SUCCESS],
        commitment=0.8,
    )


class SelectionContract(unittest.TestCase):
    """Selection retires agents exceeding the failure threshold, promotes
    zero-failure configs, emits events, and doesn't touch agents' internal
    state."""

    def test_retirement_at_threshold(self):
        pop = Population.new(retire_threshold=2)
        result = pop.creator.propose("a", [_spec("teaching")])
        ob = result.agent.obsessions.all()[0]
        for _ in range(2):
            result.agent.record_failure(
                context="c", failure="f", attempted_solutions=[],
                cost="x", unsolvable_at_time=True, linked_obsession_id=ob.id,
            )

        report = pop.selection.run()
        self.assertEqual(report.retired, ["a"])
        self.assertIn("a", pop.retired_ids)

        retired_events = pop.evolution.query(kind="agent_retired", agent_id="a")
        self.assertEqual(len(retired_events), 1)
        self.assertEqual(retired_events[0].payload["failure_count"], 2)
        self.assertEqual(retired_events[0].payload["threshold"], 2)

        # Agent's internal state is unchanged — retirement is advisory
        self.assertIsNotNone(pop.get_agent("a"))
        self.assertEqual(len(result.agent.obsessions.all()), 1)

    def test_below_threshold_not_retired(self):
        pop = Population.new(retire_threshold=3)
        result = pop.creator.propose("a", [_spec("teaching")])
        ob = result.agent.obsessions.all()[0]
        result.agent.record_failure(
            context="c", failure="f", attempted_solutions=[],
            cost="x", unsolvable_at_time=True, linked_obsession_id=ob.id,
        )
        report = pop.selection.run()
        self.assertEqual(report.retired, [])
        self.assertNotIn("a", pop.retired_ids)

    def test_promotion_of_zero_failure_config(self):
        pop = Population.new()
        pop.creator.propose("a", [_spec("teaching")])
        pop.creator.propose("b", [_spec("research")])
        report = pop.selection.run()

        # Both configs promoted
        promoted = {sig for sig in report.promoted_configs}
        self.assertEqual(promoted, {("teaching",), ("research",)})

        events = pop.evolution.query(kind="config_promoted")
        self.assertEqual(len(events), 2)

    def test_promoted_once_is_not_repromoted(self):
        pop = Population.new()
        pop.creator.propose("a", [_spec("teaching")])
        first = pop.selection.run()
        self.assertEqual(len(first.promoted_configs), 1)

        # Second run with no new agents: nothing new to promote
        second = pop.selection.run()
        self.assertEqual(second.promoted_configs, [])
        self.assertEqual(len(pop.evolution.query(kind="config_promoted")), 1)

    def test_failed_agent_not_promoted(self):
        pop = Population.new(retire_threshold=5)  # high threshold — not retired
        result = pop.creator.propose("a", [_spec("teaching")])
        ob = result.agent.obsessions.all()[0]
        result.agent.record_failure(
            context="c", failure="f", attempted_solutions=[],
            cost="x", unsolvable_at_time=True, linked_obsession_id=ob.id,
        )
        report = pop.selection.run()
        self.assertEqual(report.promoted_configs, [])
        self.assertEqual(report.retired, [])


if __name__ == "__main__":
    unittest.main()
