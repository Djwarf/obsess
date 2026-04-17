from __future__ import annotations

import unittest

from obsess.population import Population
from obsess.relationships import (
    KIND_META,
    RelationshipKind,
    SharingMode,
)


class RelationshipGraphContract(unittest.TestCase):
    """Covers the whole contract in one test: symmetric vs directional queries,
    kind metadata lookup, event emission to Evolution on formation, and
    Memory.my_relationships() read-through."""

    def test_graph_queries_and_memory_handle(self):
        pop = Population.new()
        a = pop.spawn("a")
        b = pop.spawn("b")
        c = pop.spawn("c")
        graph = pop.relationships

        peer_ab = graph.add(RelationshipKind.PEER, "a", "b")
        parent_ac = graph.add(RelationshipKind.PARENT_CHILD, "a", "c")

        # for_agent picks up both endpoints regardless of direction
        self.assertEqual(len(graph.for_agent("a")), 2)
        self.assertEqual(len(graph.for_agent("b")), 1)
        self.assertEqual(len(graph.for_agent("c")), 1)

        self.assertEqual(len(graph.for_agent("a", kind=RelationshipKind.PEER)), 1)

        # between() is order-independent at the storage level
        self.assertEqual(len(graph.between("a", "b")), 1)
        self.assertEqual(len(graph.between("b", "a")), 1)
        self.assertEqual(len(graph.between("a", "c")), 1)
        self.assertEqual(len(graph.between("c", "a")), 1)
        self.assertEqual(len(graph.between("b", "c")), 0)

        # KIND_META invariants match DESIGN-MULTI.md
        self.assertTrue(KIND_META[RelationshipKind.PEER].symmetric)
        self.assertTrue(KIND_META[RelationshipKind.PEER].decays)
        self.assertEqual(
            KIND_META[RelationshipKind.PEER].default_trauma_share_down, SharingMode.NONE
        )
        self.assertFalse(KIND_META[RelationshipKind.PARENT_CHILD].symmetric)
        self.assertFalse(KIND_META[RelationshipKind.PARENT_CHILD].decays)
        self.assertEqual(
            KIND_META[RelationshipKind.PARENT_CHILD].default_trauma_share_down,
            SharingMode.FULL,
        )
        self.assertEqual(
            KIND_META[RelationshipKind.PARENT_CHILD].default_trauma_share_up,
            SharingMode.WARNING,
        )

        # Memory's read-through handle sees the agent's own edges
        a_rels = a.my_relationships()
        self.assertEqual(len(a_rels), 2)
        self.assertEqual(len(a.my_relationships(kind=RelationshipKind.PARENT_CHILD)), 1)
        self.assertEqual(len(b.my_relationships()), 1)
        self.assertEqual(b.my_relationships()[0].id, peer_ab.id)

        # Formation events land in Evolution
        formed = pop.evolution.query(kind="relationship_formed")
        self.assertEqual(len(formed), 2)
        formed_ids = {e.payload["relationship_id"] for e in formed}
        self.assertEqual(formed_ids, {peer_ab.id, parent_ac.id})

        with self.assertRaises(ValueError):
            graph.add(RelationshipKind.PEER, "a", "a")


if __name__ == "__main__":
    unittest.main()
