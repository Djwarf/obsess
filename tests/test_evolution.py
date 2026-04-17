from __future__ import annotations

import unittest

from obsess.evolution import EvolutionStore
from obsess.population import Population
from obsess.types import SeedType


class EvolutionStoreSmoke(unittest.TestCase):
    """Append-only, filterable by kind and agent_id. That is the whole contract."""

    def test_append_and_query(self):
        store = EvolutionStore()
        store.append("spawn", {"config": "a"}, agent_id="agent_1")
        store.append("failure", {"reason": "X"}, agent_id="agent_1")
        store.append("spawn", {"config": "b"}, agent_id="agent_2")

        self.assertEqual(len(store.all()), 3)
        self.assertEqual(len(store.query(kind="spawn")), 2)
        self.assertEqual(len(store.query(agent_id="agent_1")), 2)
        self.assertEqual(len(store.query(kind="failure", agent_id="agent_1")), 1)
        self.assertEqual(len(store.query(kind="spawn", agent_id="agent_2")), 1)


class MemoryEmitsEvents(unittest.TestCase):
    """Two agents share one Population. Every observation event is correctly
    attributed. Event set is tight: spawn, failure_recorded, trauma_resolved,
    trauma_fired. No content leakage, IDs and structured metadata only."""

    def test_two_agents_emit_attributed_events(self):
        pop = Population.new()
        a = pop.spawn("a")
        b = pop.spawn("b")

        self.assertEqual(len(pop.evolution.query(kind="spawn")), 2)
        self.assertEqual(len(pop.evolution.query(kind="spawn", agent_id="a")), 1)
        self.assertEqual(len(pop.evolution.query(kind="spawn", agent_id="b")), 1)

        teaching = a.seed_obsession(
            domain="teaching_kid",
            description="explain physics to child entropy thermodynamics",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.8,
        )

        trauma = a.record_failure(
            context="Tried to explain entropy with dice",
            failure="Kid did not ground entropy in anything familiar",
            attempted_solutions=["dice"],
            cost="Disengagement",
            unsolvable_at_time=True,
            linked_obsession_id=teaching.id,
        )
        failures = pop.evolution.query(kind="failure_recorded", agent_id="a")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].payload["trauma_id"], trauma.id)
        self.assertEqual(failures[0].payload["linked_obsession_id"], teaching.id)
        self.assertTrue(failures[0].payload["unsolvable_at_time"])

        a.ingest("Planning to teach thermodynamics tomorrow.")
        fired = pop.evolution.query(kind="trauma_fired", agent_id="a")
        self.assertGreater(len(fired), 0)
        self.assertEqual(fired[0].payload["surfaced_in"], "ingest")
        self.assertEqual(fired[0].payload["trauma_id"], trauma.id)

        a.resolve_with_tradeoff(trauma.id, "Lego-block analogy worked partially")
        resolved = pop.evolution.query(kind="trauma_resolved", agent_id="a")
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].payload, {"trauma_id": trauma.id})

        # Agent b has no edges to a, no shared obsession, no cross-agent events
        b_events = pop.evolution.query(agent_id="b")
        self.assertEqual(len(b_events), 1)
        self.assertEqual(b_events[0].kind, "spawn")


if __name__ == "__main__":
    unittest.main()
