from __future__ import annotations

import unittest

from obsess.creator import (
    CreatorPolicy,
    CreatorResult,
    FailureRegistryMatch,
    ObsessionSpec,
)
from obsess.population import Population
from obsess.types import SeedType


class CreatorContract(unittest.TestCase):
    """Creator produces agents, queries the failure-registry view, applies
    policy, and emits agent_proposed/agent_created events."""

    def test_first_proposal_has_no_warnings_and_emits_events(self):
        pop = Population.new()

        spec = ObsessionSpec(
            domain="teaching",
            description="explain physics to child entropy thermodynamics",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.8,
        )
        result = pop.creator.propose("a", [spec])

        self.assertIsInstance(result, CreatorResult)
        self.assertEqual(result.agent.agent_id, "a")
        self.assertEqual(result.warnings, [])

        # Events
        proposed = pop.evolution.query(kind="agent_proposed", agent_id="a")
        created = pop.evolution.query(kind="agent_created", agent_id="a")
        self.assertEqual(len(proposed), 1)
        self.assertEqual(len(created), 1)
        self.assertEqual(proposed[0].payload["domains"], ["teaching"])
        self.assertEqual(created[0].payload["domains"], ["teaching"])
        self.assertEqual(created[0].payload["commitments"], {"teaching": 0.8})

        # Obsession was actually seeded on the agent
        self.assertEqual(len(result.agent.obsessions.all()), 1)
        self.assertEqual(result.agent.obsessions.all()[0].domain, "teaching")

    def test_failure_registry_warns_on_overlapping_config(self):
        pop = Population.new()
        a_spec = ObsessionSpec(
            domain="teaching",
            description="explain physics to kid",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.8,
        )
        a_result = pop.creator.propose("a", [a_spec])
        a_result.agent.record_failure(
            context="c", failure="f", attempted_solutions=[],
            cost="x", unsolvable_at_time=True,
            linked_obsession_id=a_result.agent.obsessions.all()[0].id,
        )

        # b's config overlaps on "teaching", should see a as a warning
        b_result = pop.creator.propose("b", [a_spec])
        self.assertEqual(len(b_result.warnings), 1)
        hit = b_result.warnings[0]
        self.assertEqual(hit.prior_agent_id, "a")
        self.assertEqual(hit.overlapping_domains, ["teaching"])
        self.assertEqual(hit.failure_count, 1)

    def test_no_warning_when_no_failures(self):
        pop = Population.new()
        spec = ObsessionSpec(
            domain="teaching",
            description="explain",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.7,
        )
        pop.creator.propose("a", [spec])  # no failures on a
        b_result = pop.creator.propose("b", [spec])
        self.assertEqual(b_result.warnings, [])

    def test_refuse_policy_raises_on_match(self):
        pop = Population.new(creator_policy=CreatorPolicy.REFUSE)
        spec = ObsessionSpec(
            domain="teaching", description="explain",
            seed_types=[SeedType.NEED_FOR_SUCCESS], commitment=0.7,
        )
        a_result = pop.creator.propose("a", [spec])
        a_result.agent.record_failure(
            context="c", failure="f", attempted_solutions=[],
            cost="x", unsolvable_at_time=True,
            linked_obsession_id=a_result.agent.obsessions.all()[0].id,
        )

        with self.assertRaises(FailureRegistryMatch):
            pop.creator.propose("b", [spec])

        # Refusal event recorded; b was never spawned
        refused = pop.evolution.query(kind="agent_refused", agent_id="b")
        self.assertEqual(len(refused), 1)
        self.assertIsNone(pop.get_agent("b"))

    def test_ignore_policy_skips_registry(self):
        pop = Population.new(creator_policy=CreatorPolicy.IGNORE)
        spec = ObsessionSpec(
            domain="teaching", description="explain",
            seed_types=[SeedType.NEED_FOR_SUCCESS], commitment=0.7,
        )
        a_result = pop.creator.propose("a", [spec])
        a_result.agent.record_failure(
            context="c", failure="f", attempted_solutions=[],
            cost="x", unsolvable_at_time=True,
            linked_obsession_id=a_result.agent.obsessions.all()[0].id,
        )
        b_result = pop.creator.propose("b", [spec])
        self.assertEqual(b_result.warnings, [])

    def test_shared_definition_activation(self):
        pop = Population.new()
        defn = pop.shared_obsessions.define(
            domain="physics",
            description="quantum field theory",
        )
        spec = ObsessionSpec(
            shared_definition_id=defn.id,
            seed_types=[SeedType.DELIBERATE_STUDY],
            commitment=0.6,
        )
        result = pop.creator.propose("a", [spec])
        # Agent has an activation against the shared def
        a_ob = result.agent.obsessions.get(defn.id)
        self.assertIsNotNone(a_ob)
        self.assertAlmostEqual(a_ob.commitment, 0.6)
        # Proposed/created events carry the domain derived from the shared def
        created = pop.evolution.query(kind="agent_created", agent_id="a")[0]
        self.assertEqual(created.payload["domains"], ["physics"])


if __name__ == "__main__":
    unittest.main()
