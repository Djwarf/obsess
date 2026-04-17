from __future__ import annotations

import unittest

from obsess.creator import ObsessionSpec
from obsess.population import Population
from obsess.relationships import RelationshipKind
from obsess.types import SeedType


class MetaLayerIntegration(unittest.TestCase):
    """End-to-end: Creator proposes A; A accumulates failures; Selection
    retires A; next Creator proposal with A's config sees the failure-registry
    warning; Bonding teambuilds new agents. The three meta-operators compose
    through Population without any direct coupling between them."""

    def test_full_flow(self):
        pop = Population.new(retire_threshold=2)

        teaching_spec = ObsessionSpec(
            domain="teaching",
            description="explain physics to child entropy thermodynamics",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.8,
        )

        # 1. Creator proposes 'a', no prior failures, no warnings
        a_result = pop.creator.propose("a", [teaching_spec])
        self.assertEqual(a_result.warnings, [])

        # 2. 'a' records failures past the retirement threshold
        a_ob = a_result.agent.obsessions.all()[0]
        for _ in range(2):
            a_result.agent.record_failure(
                context="tried dice analogy",
                failure="kid did not understand",
                attempted_solutions=["dice"],
                cost="disengagement",
                unsolvable_at_time=True,
                linked_obsession_id=a_ob.id,
            )

        # 3. Selection retires 'a'
        report = pop.selection.run()
        self.assertIn("a", report.retired)
        self.assertIn("a", pop.retired_ids)

        # 4. Creator proposes 'b' with the same config, warnings include 'a'
        b_result = pop.creator.propose("b", [teaching_spec])
        self.assertEqual(len(b_result.warnings), 1)
        self.assertEqual(b_result.warnings[0].prior_agent_id, "a")
        self.assertEqual(b_result.warnings[0].failure_count, 2)

        # 5. Creator proposes 'c' and 'd' with different configs, no warnings
        pop.creator.propose(
            "c",
            [ObsessionSpec(
                domain="research", description="research",
                seed_types=[SeedType.CURIOSITY], commitment=0.7,
            )],
        )
        pop.creator.propose(
            "d",
            [ObsessionSpec(
                domain="review", description="code review",
                seed_types=[SeedType.DELIBERATE_STUDY], commitment=0.7,
            )],
        )

        # 6. Bonding teambuilds b+c+d into a pool with pairwise TEAM edges
        pool = pop.bonding.teambuild("team_1", ["b", "c", "d"])
        self.assertEqual(pool.member_ids, {"b", "c", "d"})
        team_edges = [
            r for r in pop.relationships.all()
            if r.kind == RelationshipKind.TEAM
        ]
        self.assertEqual(len(team_edges), 3)

        # 7. Event spot-checks across the meta layer
        proposed = pop.evolution.query(kind="agent_proposed")
        self.assertEqual(len(proposed), 4)  # a, b, c, d
        created = pop.evolution.query(kind="agent_created")
        self.assertEqual(len(created), 4)
        retired = pop.evolution.query(kind="agent_retired")
        self.assertEqual(len(retired), 1)
        self.assertEqual(retired[0].agent_id, "a")
        formed = pop.evolution.query(kind="relationship_formed")
        self.assertEqual(len(formed), 3)
        pool_formed = pop.evolution.query(kind="pool_formed")
        self.assertEqual(len(pool_formed), 1)


if __name__ == "__main__":
    unittest.main()
