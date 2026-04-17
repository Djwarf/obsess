from __future__ import annotations

import time
import unittest

from obsess.population import Population
from obsess.types import SeedType


class SharedObsessionContract(unittest.TestCase):
    """Two agents activate against the same shared definition with different
    commitments. Definition identity is shared; activations are isolated.
    Private obsessions still work alongside. Guard errors fire for
    missing/duplicate activations."""

    def test_shared_definition_with_isolated_activations(self):
        pop = Population.new()
        a = pop.spawn("a")
        b = pop.spawn("b")

        physics_def = pop.shared_obsessions.define(
            domain="physics",
            description="quantum field theory renormalization",
        )

        a_ob = a.activate_shared_obsession(
            physics_def.id,
            seed_types=[SeedType.CURIOSITY],
            commitment=0.8,
        )
        b_ob = b.activate_shared_obsession(
            physics_def.id,
            seed_types=[SeedType.DELIBERATE_STUDY],
            commitment=0.3,
        )

        # Same definition — identity is shared
        self.assertIs(a_ob.definition, b_ob.definition)
        self.assertEqual(a_ob.id, b_ob.id)
        self.assertEqual(a_ob.domain, "physics")
        self.assertEqual(b_ob.domain, "physics")

        # Activations are isolated
        self.assertAlmostEqual(a_ob.commitment, 0.8)
        self.assertAlmostEqual(b_ob.commitment, 0.3)
        self.assertEqual(a_ob.seed_types, [SeedType.CURIOSITY])
        self.assertEqual(b_ob.seed_types, [SeedType.DELIBERATE_STUDY])
        self.assertEqual(a_ob.agent_id, "a")
        self.assertEqual(b_ob.agent_id, "b")

        # Touching A does not move B's activation state
        b_last_before = b_ob.last_activation
        time.sleep(0.01)
        a_ob.touch()
        self.assertEqual(b_ob.last_activation, b_last_before)
        self.assertGreater(a_ob.last_activation, b_last_before)

        # Private obsessions still work alongside shared ones
        a.seed_obsession(
            domain="teaching",
            description="explain physics to my kid",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.5,
        )
        self.assertEqual(len(a.obsessions.all()), 2)
        domains = {o.domain for o in a.obsessions.all()}
        self.assertEqual(domains, {"physics", "teaching"})

        # Guards
        with self.assertRaises(KeyError):
            a.activate_shared_obsession(
                "not-a-real-id", [SeedType.CURIOSITY], commitment=0.1
            )
        with self.assertRaises(ValueError):
            a.activate_shared_obsession(
                physics_def.id, [SeedType.CURIOSITY], commitment=0.5
            )

        defined = pop.evolution.query(kind="shared_obsession_defined")
        self.assertEqual(len(defined), 1)
        self.assertEqual(defined[0].payload["definition_id"], physics_def.id)

        activated = pop.evolution.query(kind="shared_obsession_activated")
        self.assertEqual(len(activated), 2)
        self.assertEqual({e.agent_id for e in activated}, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
