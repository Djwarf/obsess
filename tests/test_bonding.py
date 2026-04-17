from __future__ import annotations

import random
import unittest

from obsess.creator import ObsessionSpec
from obsess.population import Population
from obsess.relationships import RelationshipKind
from obsess.types import SeedType


def _spec(domain: str, commitment: float = 0.7) -> ObsessionSpec:
    return ObsessionSpec(
        domain=domain,
        description=f"{domain} domain description",
        seed_types=[SeedType.NEED_FOR_SUCCESS],
        commitment=commitment,
    )


class BondingContract(unittest.TestCase):
    """Each strategy forms the right edges, respects retired agents, and
    emits events via the underlying Population.form_relationship path."""

    def test_genetic_creates_parent_child_edge_and_propagates_obsessions(self):
        pop = Population.new()
        parent = pop.creator.propose("parent", [_spec("teaching", 0.9)]).agent
        child = pop.spawn("child")

        rel = pop.bonding.genetic("parent", "child")
        self.assertEqual(rel.kind, RelationshipKind.PARENT_CHILD)
        self.assertEqual(rel.from_agent_id, "parent")
        self.assertEqual(rel.to_agent_id, "child")

        # parent's "teaching" is private, so it does NOT propagate via genetic.
        # (Only shared obsessions propagate through relationship edges.)
        self.assertIsNone(child.obsessions.get(parent.obsessions.all()[0].id))

    def test_genetic_propagates_shared_obsessions(self):
        pop = Population.new()
        defn = pop.shared_obsessions.define(
            domain="teaching", description="explain to kid",
        )
        parent = pop.creator.propose(
            "parent",
            [ObsessionSpec(
                shared_definition_id=defn.id,
                seed_types=[SeedType.NEED_FOR_SUCCESS],
                commitment=0.8,
            )],
        ).agent
        child = pop.spawn("child")

        pop.bonding.genetic("parent", "child")

        # Child inherits via PARENT_CHILD attenuation (default 0.5)
        child_ob = child.obsessions.get(defn.id)
        self.assertIsNotNone(child_ob)
        self.assertAlmostEqual(child_ob.activation.bootstrapped_commitment, 0.4)

    def test_teambuild_creates_pool_and_pairwise_team_edges(self):
        pop = Population.new()
        for aid in ["a", "b", "c"]:
            pop.spawn(aid)

        pool = pop.bonding.teambuild("team_1", ["a", "b", "c"])
        self.assertEqual(pool.name, "team_1")
        self.assertEqual(pool.member_ids, {"a", "b", "c"})

        # Three pairwise TEAM edges: a-b, a-c, b-c
        team_edges = [
            r for r in pop.relationships.all()
            if r.kind == RelationshipKind.TEAM
        ]
        self.assertEqual(len(team_edges), 3)
        endpoints = {tuple(sorted([r.from_agent_id, r.to_agent_id])) for r in team_edges}
        self.assertEqual(endpoints, {("a", "b"), ("a", "c"), ("b", "c")})

    def test_teambuild_then_activate_pool_obsession(self):
        pop = Population.new()
        for aid in ["a", "b"]:
            pop.spawn(aid)
        pool = pop.bonding.teambuild("team", ["a", "b"])
        # Pool-scoped obsessions are defined after teambuild; members activate
        # against them explicitly. Demonstrates that the separation works.
        defn = pop.shared_obsessions.define(
            domain="billing",
            description="prevent billing errors",
            owner_pool_id=pool.id,
        )
        for m in ["a", "b"]:
            pop.get_agent(m).activate_shared_obsession(
                defn.id, seed_types=[SeedType.NEED_FOR_SUCCESS], commitment=0.5,
            )
            self.assertIsNotNone(pop.get_agent(m).obsessions.get(defn.id))

    def test_teambuild_requires_spawned_members(self):
        pop = Population.new()
        pop.spawn("a")
        with self.assertRaises(ValueError):
            pop.bonding.teambuild("team", ["a", "ghost"])

    def test_teambuild_requires_at_least_two(self):
        pop = Population.new()
        pop.spawn("a")
        with self.assertRaises(ValueError):
            pop.bonding.teambuild("solo", ["a"])

    def test_hiring_finds_best_commitment_candidate(self):
        pop = Population.new()
        # Two candidates with different commitments on the needed domain
        pop.creator.propose("expert", [_spec("physics", 0.9)])
        pop.creator.propose("novice", [_spec("physics", 0.4)])
        pop.creator.propose("offtopic", [_spec("biology", 0.9)])
        pop.spawn("requester")

        rel = pop.bonding.hiring("requester", "physics", min_commitment=0.3)
        self.assertIsNotNone(rel)
        # Should pair with the expert (highest commitment)
        self.assertIn("expert", (rel.from_agent_id, rel.to_agent_id))
        self.assertEqual(rel.kind, RelationshipKind.PEER)

    def test_hiring_returns_none_if_no_candidate(self):
        pop = Population.new()
        pop.creator.propose("expert", [_spec("biology", 0.9)])
        pop.spawn("requester")
        self.assertIsNone(pop.bonding.hiring("requester", "physics"))

    def test_hiring_skips_retired_agents(self):
        pop = Population.new(retire_threshold=1)
        result = pop.creator.propose("expert", [_spec("physics", 0.9)])
        ob = result.agent.obsessions.all()[0]
        result.agent.record_failure(
            context="c", failure="f", attempted_solutions=[],
            cost="x", unsolvable_at_time=True, linked_obsession_id=ob.id,
        )
        pop.selection.run()  # retires "expert"
        pop.spawn("requester")
        self.assertIsNone(pop.bonding.hiring("requester", "physics"))

    def test_luck_is_deterministic_under_seed(self):
        pop = Population.new(bonding_rng=random.Random(42))
        for aid in ["a", "b", "c", "d"]:
            pop.spawn(aid)
        formed = pop.bonding.luck(["a", "b", "c", "d"], p=0.5)
        # With seed 42 and p=0.5 over 6 pairs, a deterministic subset is chosen.
        # Assert: some edges form, all are PEER, no duplicates.
        self.assertGreater(len(formed), 0)
        for rel in formed:
            self.assertEqual(rel.kind, RelationshipKind.PEER)
        # Re-run with same seed should yield the same count
        pop2 = Population.new(bonding_rng=random.Random(42))
        for aid in ["a", "b", "c", "d"]:
            pop2.spawn(aid)
        formed2 = pop2.bonding.luck(["a", "b", "c", "d"], p=0.5)
        self.assertEqual(len(formed), len(formed2))

    def test_luck_skips_retired(self):
        pop = Population.new(bonding_rng=random.Random(0), retire_threshold=1)
        for aid in ["a", "b", "c"]:
            pop.creator.propose(aid, [_spec("x", 0.8)])
        # Retire a
        a_ob = pop.get_agent("a").obsessions.all()[0]
        pop.get_agent("a").record_failure(
            context="c", failure="f", attempted_solutions=[],
            cost="x", unsolvable_at_time=True, linked_obsession_id=a_ob.id,
        )
        pop.selection.run()
        # Luck over all three, no edge involves a
        formed = pop.bonding.luck(["a", "b", "c"], p=1.0)
        for rel in formed:
            self.assertNotIn("a", (rel.from_agent_id, rel.to_agent_id))


if __name__ == "__main__":
    unittest.main()
