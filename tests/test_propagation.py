from __future__ import annotations

import unittest

from engram.population import Population
from engram.relationships import RelationshipKind, SharingMode
from engram.types import AccessMode, SeedType


class TraumaPropagationContract(unittest.TestCase):
    """The piece that makes the multi-agent thesis do real work.

    Setup: A and B in parent/child (A parent, B child). Both activate against
    a shared 'teaching' obsession. A records a failure linked to teaching.

    Verify: (1) a TraumaShare lands for B with mode=FULL (parent→child default);
    (2) trauma_shared event hits Evolution; (3) B ingests similar content and
    sees A's trauma in B's trauma_warnings, with origin_agent_id pointing to A."""

    def test_parent_failure_propagates_and_fires_for_child(self):
        pop = Population.new()
        a = pop.spawn("a")
        b = pop.spawn("b")

        pop.relationships.add(RelationshipKind.PARENT_CHILD, "a", "b")

        # Both agents activate against the same shared obsession
        teaching_def = pop.shared_obsessions.define(
            domain="teaching_kid",
            description="explain physics to child entropy thermodynamics",
        )
        a.activate_shared_obsession(
            teaching_def.id, seed_types=[SeedType.NEED_FOR_SUCCESS], commitment=0.9
        )
        b.activate_shared_obsession(
            teaching_def.id, seed_types=[SeedType.NEED_FOR_SUCCESS], commitment=0.7
        )

        # Parent records a failure linked to the shared obsession
        trauma = a.record_failure(
            context="Tried to explain entropy to my 7-year-old with dice",
            failure="Could not ground entropy in anything they understood",
            attempted_solutions=["dice", "verbal"],
            cost="Kid disengaged",
            unsolvable_at_time=True,
            linked_obsession_id=teaching_def.id,
        )

        # (1) Share record lands for B with FULL mode
        b_shares = pop.trauma_shares.for_recipient("b")
        self.assertEqual(len(b_shares), 1)
        self.assertEqual(b_shares[0].trauma_id, trauma.id)
        self.assertEqual(b_shares[0].origin_agent_id, "a")
        self.assertEqual(b_shares[0].mode, SharingMode.FULL)

        # (2) trauma_shared event emitted
        shared_events = pop.evolution.query(kind="trauma_shared")
        self.assertEqual(len(shared_events), 1)
        self.assertEqual(shared_events[0].agent_id, "a")  # origin
        self.assertEqual(shared_events[0].payload["recipient_agent_id"], "b")
        self.assertEqual(shared_events[0].payload["mode"], "full")

        # (3) Child ingests similar content; A's trauma fires for B as FULL inheritance
        r = b.ingest("Planning to teach thermodynamics to my kid tomorrow.")
        self.assertGreater(len(r.trauma_warnings), 0)
        inherited = [st for st in r.trauma_warnings if st.trauma.origin_agent_id == "a"]
        self.assertEqual(len(inherited), 1)
        self.assertEqual(inherited[0].trauma.id, trauma.id)
        self.assertEqual(inherited[0].access, AccessMode.FULL)

        # Render reflects the access mode
        self.assertIn("inherited from a", inherited[0].rendered_text)

        # Symmetric check: A's own trauma fires for A as ORIGIN (verbatim)
        r_a = a.ingest("Planning to teach thermodynamics to my kid tomorrow.")
        self.assertGreater(len(r_a.trauma_warnings), 0)
        own = [st for st in r_a.trauma_warnings if st.trauma.origin_agent_id == "a"]
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0].access, AccessMode.ORIGIN)
        self.assertEqual(own[0].rendered_text, own[0].trauma.failure)

    def test_peer_relationship_does_not_propagate(self):
        """Peer defaults to NONE for both directions; recording a failure
        should produce no share records. This pins the KIND_META contract."""
        pop = Population.new()
        a = pop.spawn("a")
        pop.spawn("b")

        pop.relationships.add(RelationshipKind.PEER, "a", "b")

        teaching = a.seed_obsession(
            domain="teaching",
            description="explain physics",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.8,
        )
        a.record_failure(
            context="failed",
            failure="failed to explain",
            attempted_solutions=[],
            cost="x",
            unsolvable_at_time=True,
            linked_obsession_id=teaching.id,
        )

        self.assertEqual(len(pop.trauma_shares.for_recipient("b")), 0)
        self.assertEqual(len(pop.evolution.query(kind="trauma_shared")), 0)

    def test_non_origin_cannot_resolve(self):
        """Only the origin agent may append resolution tradeoffs to a trauma.
        Inheritors see it fire but do not hold the lived experience."""
        pop = Population.new()
        a = pop.spawn("a")
        b = pop.spawn("b")
        pop.relationships.add(RelationshipKind.PARENT_CHILD, "a", "b")

        teaching = a.seed_obsession(
            domain="teaching",
            description="explain",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.8,
        )
        trauma = a.record_failure(
            context="c", failure="f", attempted_solutions=[], cost="x",
            unsolvable_at_time=True, linked_obsession_id=teaching.id,
        )

        with self.assertRaises(PermissionError):
            b.resolve_with_tradeoff(trauma.id, "not mine to resolve")

        # Origin can resolve
        a.resolve_with_tradeoff(trauma.id, "worked this out eventually")
        self.assertIn("worked this out", " ".join(trauma.resolution_tradeoffs))


if __name__ == "__main__":
    unittest.main()
