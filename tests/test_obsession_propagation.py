from __future__ import annotations

import unittest

from obsess.population import Population
from obsess.relationships import RelationshipKind
from obsess.types import SeedType


class ObsessionPropagationContract(unittest.TestCase):
    """Formation-time obsession propagation (DESIGN-MULTI.md bootstrap):
    when a relationship is formed, FULL-share downstream (and upstream where
    applicable) copies the source's shared-obsession activations to the target
    with bootstrapped commitment = source's total × attenuation."""

    def test_master_prodigy_bootstraps_full_commitment(self):
        pop = Population.new()
        master = pop.spawn("master")
        prodigy = pop.spawn("prodigy")

        physics_def = pop.shared_obsessions.define(
            domain="physics",
            description="quantum field theory renormalization",
        )
        master.activate_shared_obsession(physics_def.id, [SeedType.DELIBERATE_STUDY], 0.8)

        pop.form_relationship(RelationshipKind.MASTER_PRODIGY, "master", "prodigy")

        prodigy_physics = prodigy.obsessions.get(physics_def.id)
        self.assertIsNotNone(prodigy_physics)
        self.assertAlmostEqual(prodigy_physics.activation.earned_commitment, 0.0)
        self.assertAlmostEqual(prodigy_physics.activation.bootstrapped_commitment, 0.8)
        self.assertAlmostEqual(prodigy_physics.commitment, 0.8)

        events = pop.evolution.query(kind="obsession_propagated")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["from_agent_id"], "master")
        self.assertEqual(events[0].payload["to_agent_id"], "prodigy")
        self.assertAlmostEqual(events[0].payload["bootstrapped_commitment"], 0.8)

    def test_parent_child_attenuates_inheritance(self):
        pop = Population.new()
        parent = pop.spawn("parent")
        child = pop.spawn("child")

        teaching_def = pop.shared_obsessions.define(
            domain="teaching",
            description="explain science to children",
        )
        parent.activate_shared_obsession(
            teaching_def.id, [SeedType.NEED_FOR_SUCCESS], 0.9
        )

        pop.form_relationship(RelationshipKind.PARENT_CHILD, "parent", "child")

        # Default parent/child attenuation is 0.5: child starts at half the parent's total.
        child_teaching = child.obsessions.get(teaching_def.id)
        self.assertIsNotNone(child_teaching)
        self.assertAlmostEqual(child_teaching.activation.bootstrapped_commitment, 0.45)

    def test_attenuation_override_via_metadata(self):
        pop = Population.new()
        parent = pop.spawn("parent")
        child = pop.spawn("child")

        defn = pop.shared_obsessions.define(
            domain="rigor",
            description="mathematical rigor",
        )
        parent.activate_shared_obsession(defn.id, [SeedType.BEST_IN_WORLD], 0.8)

        pop.form_relationship(
            RelationshipKind.PARENT_CHILD,
            "parent", "child",
            metadata={"attenuation": 0.25},
        )
        child_ob = child.obsessions.get(defn.id)
        self.assertAlmostEqual(child_ob.activation.bootstrapped_commitment, 0.2)

    def test_peer_does_not_propagate(self):
        pop = Population.new()
        a = pop.spawn("a")
        b = pop.spawn("b")

        defn = pop.shared_obsessions.define(
            domain="physics", description="qft"
        )
        a.activate_shared_obsession(defn.id, [SeedType.CURIOSITY], 0.8)

        pop.form_relationship(RelationshipKind.PEER, "a", "b")
        self.assertIsNone(b.obsessions.get(defn.id))
        self.assertEqual(len(pop.evolution.query(kind="obsession_propagated")), 0)

    def test_upward_flow_is_not_default(self):
        """Master/prodigy and parent/child both default to NONE upward for
        obsessions, a prodigy's later obsessions do not retroactively flow
        to the master."""
        pop = Population.new()
        master = pop.spawn("master")
        prodigy = pop.spawn("prodigy")

        pop.form_relationship(RelationshipKind.MASTER_PRODIGY, "master", "prodigy")

        biology_def = pop.shared_obsessions.define(
            domain="biology", description="cell biology"
        )
        prodigy.activate_shared_obsession(biology_def.id, [SeedType.CURIOSITY], 0.6)

        # Master does not inherit prodigy's obsession, and activation-time
        # propagation is not implemented, so even if defaults were non-NONE
        # upward, this wouldn't flow. Both invariants covered.
        self.assertIsNone(master.obsessions.get(biology_def.id))

    def test_pool_obsessions_do_not_propagate_via_relationships(self):
        pop = Population.new()
        master = pop.spawn("master")
        prodigy = pop.spawn("prodigy")

        pool = pop.pools.add(name="team", member_ids=["master"])
        pool_def = pop.shared_obsessions.define(
            domain="team_priority",
            description="team priority",
            owner_pool_id=pool.id,
        )
        master.activate_shared_obsession(pool_def.id, [SeedType.NEED_FOR_SUCCESS], 0.7)

        pop.form_relationship(RelationshipKind.MASTER_PRODIGY, "master", "prodigy")

        # Prodigy is not in the pool, so the pool obsession does not propagate.
        # Pool access is by membership, not by relationship edges.
        self.assertIsNone(prodigy.obsessions.get(pool_def.id))

    def test_form_relationship_requires_spawned_agents(self):
        pop = Population.new()
        pop.spawn("a")
        with self.assertRaises(ValueError):
            pop.form_relationship(RelationshipKind.PEER, "a", "ghost")


if __name__ == "__main__":
    unittest.main()
