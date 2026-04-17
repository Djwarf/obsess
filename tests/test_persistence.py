from __future__ import annotations

import os
import tempfile
import unittest

from obsess.creator import ObsessionSpec
from obsess.population import Population
from obsess.relationships import RelationshipKind
from obsess.storage.memory import InMemoryStorage
from obsess.storage.sqlite import SQLiteStorage
from obsess.types import SeedType


class StorageBackendContract(unittest.TestCase):
    """Both backends (InMemory, SQLite) implement the same Storage protocol.
    Verify the contract: events append + query; entities put/get/all/delete."""

    def _verify(self, storage):
        # Events
        e1 = storage.append_event("spawn", {"x": 1}, agent_id="a")
        e2 = storage.append_event("failure_recorded", {"trauma_id": "t1"}, agent_id="a")
        e3 = storage.append_event("spawn", {"x": 2}, agent_id="b")
        self.assertEqual(len(storage.all_events()), 3)
        self.assertEqual(len(storage.query_events(kind="spawn")), 2)
        self.assertEqual(len(storage.query_events(agent_id="a")), 2)
        self.assertEqual(
            len(storage.query_events(kind="failure_recorded", agent_id="a")), 1
        )

        # Entities
        storage.put("things", "x1", {"value": 1})
        storage.put("things", "x2", {"value": 2})
        self.assertEqual(storage.get("things", "x1"), {"value": 1})
        self.assertEqual(len(storage.all("things")), 2)
        self.assertIsNone(storage.get("things", "ghost"))
        storage.delete("things", "x1")
        self.assertIsNone(storage.get("things", "x1"))
        self.assertEqual(len(storage.all("things")), 1)

        # Overwrite via put
        storage.put("things", "x2", {"value": 99})
        self.assertEqual(storage.get("things", "x2"), {"value": 99})

    def test_in_memory(self):
        self._verify(InMemoryStorage())

    def test_sqlite(self):
        with tempfile.TemporaryDirectory() as td:
            storage = SQLiteStorage(os.path.join(td, "test.db"))
            try:
                self._verify(storage)
            finally:
                storage.close()


class SqlitePersistenceAcrossSessions(unittest.TestCase):
    """The real proof: a Population built on SQLite storage, populated with
    agents/obsessions/traumas/relationships/pools, closed, reopened, and
    rehydrated — state survives. Agent behavior continues where it left off."""

    def test_end_to_end_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "obsess.db")

            # --- Session 1: build state ---
            pop = Population.new(storage=SQLiteStorage(path))

            # Shared obsession both agents activate against
            teaching_def = pop.shared_obsessions.define(
                domain="teaching_kid",
                description="explain physics to child entropy thermodynamics",
            )

            a = pop.creator.propose("a", [ObsessionSpec(
                shared_definition_id=teaching_def.id,
                seed_types=[SeedType.NEED_FOR_SUCCESS],
                commitment=0.8,
            )]).agent
            b = pop.creator.propose("b", [ObsessionSpec(
                shared_definition_id=teaching_def.id,
                seed_types=[SeedType.NEED_FOR_SUCCESS],
                commitment=0.7,
            )]).agent

            # Parent/child relationship (propagates obsessions)
            pop.form_relationship(RelationshipKind.PARENT_CHILD, "a", "b")

            # A records a failure → propagates to b as FULL share
            trauma = a.record_failure(
                context="Tried to explain entropy with dice",
                failure="Kid did not understand",
                attempted_solutions=["dice"],
                cost="disengagement",
                unsolvable_at_time=True,
                linked_obsession_id=teaching_def.id,
            )

            # Pool (separate concern)
            for aid in ["c", "d"]:
                pop.spawn(aid)
            pool = pop.bonding.teambuild("team_x", ["c", "d"])

            # Capture key identifiers for later assertion
            trauma_id = trauma.id
            teaching_id = teaching_def.id
            pool_id = pool.id

            pop.close()

            # --- Session 2: reopen and verify ---
            pop2 = Population.new(storage=SQLiteStorage(path))

            # Shared obsession survived
            defn2 = pop2.shared_obsessions.get(teaching_id)
            self.assertIsNotNone(defn2)
            self.assertEqual(defn2.domain, "teaching_kid")

            # Relationships survived: parent/child (a,b) + team (c,d)
            rels = pop2.relationships.all()
            self.assertEqual(len(rels), 2)
            pc = [r for r in rels if r.kind == RelationshipKind.PARENT_CHILD]
            self.assertEqual(len(pc), 1)
            self.assertEqual(pc[0].from_agent_id, "a")
            self.assertEqual(pc[0].to_agent_id, "b")
            team = [r for r in rels if r.kind == RelationshipKind.TEAM]
            self.assertEqual(len(team), 1)

            # Trauma survived
            t2 = pop2.traumas.get(trauma_id)
            self.assertIsNotNone(t2)
            self.assertEqual(t2.origin_agent_id, "a")
            self.assertEqual(t2.linked_obsession_id, teaching_id)

            # Trauma share survived
            shares_for_b = pop2.trauma_shares.for_recipient("b")
            self.assertEqual(len(shares_for_b), 1)
            self.assertEqual(shares_for_b[0].trauma_id, trauma_id)

            # Pool survived
            pool2 = pop2.pools.get(pool_id)
            self.assertIsNotNone(pool2)
            self.assertEqual(pool2.member_ids, {"c", "d"})

            # Events survived (several event kinds accumulated)
            self.assertGreater(len(pop2.evolution.query(kind="spawn")), 0)
            self.assertEqual(
                len(pop2.evolution.query(kind="failure_recorded", agent_id="a")), 1
            )
            self.assertEqual(
                len(pop2.evolution.query(kind="trauma_shared")), 1
            )

            # Agent IDs are discoverable from spawn events
            recorded = set(pop2.agent_ids_on_record())
            self.assertEqual(recorded, {"a", "b", "c", "d"})

            # Rehydrate agents — no new spawn events fire
            spawns_before = len(pop2.evolution.query(kind="spawn"))
            a_rehydrated = pop2.rehydrate_agent("a")
            b_rehydrated = pop2.rehydrate_agent("b")
            spawns_after = len(pop2.evolution.query(kind="spawn"))
            self.assertEqual(spawns_before, spawns_after)

            # Rehydrated agents have their obsessions
            a_obs = a_rehydrated.obsessions.all()
            self.assertEqual(len(a_obs), 1)
            self.assertEqual(a_obs[0].id, teaching_id)
            self.assertAlmostEqual(a_obs[0].activation.earned_commitment, 0.8)

            b_obs = b_rehydrated.obsessions.all()
            # b has the shared activation (commitment 0.7) AND the inherited
            # bootstrapped copy from parent/child formation — but because
            # activation happened BEFORE the relationship, no extra is added:
            # propagation skips defs that already have an activation on target.
            self.assertEqual(len(b_obs), 1)
            self.assertEqual(b_obs[0].id, teaching_id)

            # Rehydrated agent can still ingest and the trauma fires
            r = b_rehydrated.ingest("Planning to teach thermodynamics tomorrow.")
            inherited = [st for st in r.trauma_warnings if st.trauma.id == trauma_id]
            self.assertEqual(len(inherited), 1)

            # Retirement state survived — selection's retirement events
            # hydrate retired_ids in pop2. Add a failure that crosses threshold.
            a_ob = a_rehydrated.obsessions.all()[0]
            a_rehydrated.record_failure(
                context="c2", failure="f2", attempted_solutions=[],
                cost="x", unsolvable_at_time=True, linked_obsession_id=a_ob.id,
            )
            a_rehydrated.record_failure(
                context="c3", failure="f3", attempted_solutions=[],
                cost="x", unsolvable_at_time=True, linked_obsession_id=a_ob.id,
            )
            pop2.selection.run()
            self.assertIn("a", pop2.retired_ids)

            pop2.close()

            # --- Session 3: reopen and verify retirement persisted ---
            pop3 = Population.new(storage=SQLiteStorage(path))
            self.assertIn("a", pop3.retired_ids)
            pop3.close()


if __name__ == "__main__":
    unittest.main()
