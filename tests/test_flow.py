from __future__ import annotations

import unittest

from engram.population import Population
from engram.types import SeedType


class EngramFlow(unittest.TestCase):
    def setUp(self):
        self.pop = Population.new()
        self.mem = self.pop.spawn(agent_id="test_agent")
        self.physics = self.mem.seed_obsession(
            domain="physics",
            description="quantum field theory renormalization gauge symmetry",
            seed_types=[SeedType.CURIOSITY, SeedType.DELIBERATE_STUDY],
            commitment=0.9,
        )
        self.teaching = self.mem.seed_obsession(
            domain="teaching_kid",
            description="explain physics to child entropy thermodynamics",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.6,
        )
        self.mem.seed_obsession(
            domain="provision",
            description="support family dependents",
            seed_types=[SeedType.PROVISION],
            commitment=1.0,
            identity_level=True,
        )

    def test_high_alignment_stored(self):
        r = self.mem.ingest(
            "Renormalization handles UV divergences in quantum field theory."
        )
        self.assertEqual(r.action, "stored")
        self.assertIsNotNone(r.impression)

    def test_low_alignment_dropped(self):
        r = self.mem.ingest("Pop star releases album, fans thrilled.")
        self.assertEqual(r.action, "dropped")
        self.assertIsNone(r.impression)

    def test_trauma_self_surfaces(self):
        self.mem.record_failure(
            context="Tried to explain entropy to my 7-year-old with dice",
            failure="Could not ground entropy in anything they understood",
            attempted_solutions=["dice", "verbal"],
            cost="Kid disengaged",
            unsolvable_at_time=True,
            linked_obsession_id=self.teaching.id,
        )
        r = self.mem.ingest("Planning to teach my kid thermodynamics tomorrow.")
        self.assertGreater(len(r.trauma_warnings), 0)

    def test_trauma_keeps_firing_after_resolution(self):
        trauma = self.mem.record_failure(
            context="Explained entropy to kid failed",
            failure="Kid did not understand entropy from dice analogy",
            attempted_solutions=["dice"],
            cost="Disengagement",
            unsolvable_at_time=True,
            linked_obsession_id=self.teaching.id,
        )
        self.mem.resolve_with_tradeoff(
            trauma.id,
            "Lego-block analogy works but oversimplifies microstate counting",
        )
        r = self.mem.ingest("Going to teach kid about heat death today.")
        self.assertGreater(len(r.trauma_warnings), 0, "trauma must still fire after resolution")
        surfaced = r.trauma_warnings[0]
        self.assertIn("Lego", " ".join(surfaced.trauma.resolution_tradeoffs))

    def test_retrieval_regenerates_through_current_frame(self):
        self.mem.ingest("QFT uses path integrals to compute amplitudes.")
        q = self.mem.query("what do I know about QFT?")
        self.assertEqual(q.current_frame, "physics")
        self.assertIn("physics", q.answer.lower())

    def test_provision_is_not_the_frame(self):
        q = self.mem.query("anything")
        self.assertNotEqual(q.current_frame, "provision")


if __name__ == "__main__":
    unittest.main()
