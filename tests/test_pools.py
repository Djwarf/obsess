from __future__ import annotations

import unittest

from obsess.population import Population
from obsess.types import AccessMode, SeedType


class PoolContract(unittest.TestCase):
    """Pool primitive, pool obsessions (membership-gated), pool traumas
    (visible to all members, no TraumaShares needed). Render layer surfaces
    pool traumas with AccessMode.POOL."""

    def test_pool_obsession_and_pool_trauma(self):
        pop = Population.new()
        a = pop.spawn("a")
        b = pop.spawn("b")
        c = pop.spawn("c")  # non-member

        pool = pop.pools.add(name="billing_team", member_ids=["a", "b"])
        self.assertTrue(pop.pools.is_member(pool.id, "a"))
        self.assertTrue(pop.pools.is_member(pool.id, "b"))
        self.assertFalse(pop.pools.is_member(pool.id, "c"))

        # Pool-scoped obsession: members can activate, non-members cannot
        billing_def = pop.shared_obsessions.define(
            domain="billing_correctness",
            description="prevent overcharge underbill billing invoice errors",
            owner_pool_id=pool.id,
        )
        a.activate_shared_obsession(billing_def.id, [SeedType.NEED_FOR_SUCCESS], 0.8)
        b.activate_shared_obsession(billing_def.id, [SeedType.NEED_FOR_SUCCESS], 0.6)
        with self.assertRaises(PermissionError):
            c.activate_shared_obsession(billing_def.id, [SeedType.CURIOSITY], 0.1)

        # A records a pool trauma (team failure)
        trauma = a.record_failure(
            context="Billing pipeline sent duplicate invoice to customer",
            failure="Could not correlate invoice retry with the first send; team-level state",
            attempted_solutions=["idempotency check"],
            cost="Customer complaint, refund issued",
            unsolvable_at_time=True,
            linked_obsession_id=billing_def.id,
            pool_id=pool.id,
        )
        self.assertEqual(trauma.pool_id, pool.id)

        # Pool traumas do NOT propagate via TraumaShares
        self.assertEqual(len(pop.trauma_shares.all()), 0)

        # Pool trauma fires for B (member) with AccessMode.POOL
        r_b = b.ingest("Investigating a duplicate invoice issue this morning.")
        pool_warnings = [st for st in r_b.trauma_warnings if st.access == AccessMode.POOL]
        self.assertEqual(len(pool_warnings), 1)
        self.assertEqual(pool_warnings[0].trauma.id, trauma.id)
        self.assertIn("team failure", pool_warnings[0].rendered_text)

        # And for A (also a member), also as POOL, origin doesn't get ORIGIN
        # semantics for pool traumas, since the failure is collective
        r_a = a.ingest("Investigating a duplicate invoice issue this morning.")
        pool_warnings_a = [st for st in r_a.trauma_warnings if st.access == AccessMode.POOL]
        self.assertEqual(len(pool_warnings_a), 1)

        # Non-member does not see it
        r_c = c.ingest("Investigating a duplicate invoice issue this morning.")
        self.assertEqual(len(r_c.trauma_warnings), 0)

        # Non-member cannot record a pool trauma
        with self.assertRaises(PermissionError):
            c.record_failure(
                context="impersonation attempt",
                failure="should fail",
                attempted_solutions=[],
                cost="x",
                unsolvable_at_time=True,
                pool_id=pool.id,
            )

        # Pool member can resolve a pool trauma even if they weren't the recorder
        b.resolve_with_tradeoff(trauma.id, "Added idempotency key to retry path")
        self.assertIn("idempotency key", " ".join(trauma.resolution_tradeoffs))

        # Non-member cannot resolve
        with self.assertRaises(PermissionError):
            c.resolve_with_tradeoff(trauma.id, "not mine")

        # Membership change: adding C grants access. C onboards by activating
        # the pool obsession, and then pool memory surfaces for them.
        pop.pools.add_member(pool.id, "c")
        self.assertTrue(pop.pools.is_member(pool.id, "c"))
        c.activate_shared_obsession(billing_def.id, [SeedType.CURIOSITY], 0.7)
        r_c2 = c.ingest("Investigating a duplicate invoice issue this morning.")
        pool_warnings_c = [st for st in r_c2.trauma_warnings if st.access == AccessMode.POOL]
        self.assertEqual(len(pool_warnings_c), 1)

        # Events landed
        self.assertEqual(len(pop.evolution.query(kind="pool_formed")), 1)
        self.assertEqual(len(pop.evolution.query(kind="pool_member_added")), 1)


if __name__ == "__main__":
    unittest.main()
