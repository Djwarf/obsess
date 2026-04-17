"""Persistent obsess across sessions via SQLiteStorage.

Shows:
- Constructing a Population on a SQLite file.
- State surviving close() + reopen.
- Rehydrating an existing agent (no new spawn event fires).
- Continuing the agent's behavior — accumulated traumas still surface.

Run: python examples/04_persistence.py
"""

import os
import tempfile

from obsess import Population
from obsess.storage.sqlite import SQLiteStorage
from obsess.types import SeedType


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "obsess.db")

        # --- Session 1: build state ---
        print("=== Session 1: creating state ===")
        pop = Population.new(storage=SQLiteStorage(db_path))
        agent = pop.spawn("assistant")

        agent.seed_obsession(
            domain="code_quality",
            description="write clean readable tested code without bugs",
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.8,
        )
        ob = agent.obsessions.all()[0]

        agent.record_failure(
            context="Tried to explain edge cases in review.",
            failure="Reviewer missed the null case; bug shipped.",
            attempted_solutions=["detailed review comments"],
            cost="hotfix required",
            unsolvable_at_time=True,
            linked_obsession_id=ob.id,
        )
        print(f"  stored {len(agent.my_traumas())} trauma(s) for {agent.agent_id}")
        pop.close()

        # --- Session 2: reload and continue ---
        print()
        print("=== Session 2: reopening existing DB ===")
        pop2 = Population.new(storage=SQLiteStorage(db_path))

        recorded = pop2.agent_ids_on_record()
        print(f"  agents on record: {recorded}")

        agent2 = pop2.rehydrate_agent("assistant")
        print(f"  rehydrated {agent2.agent_id}")
        print(f"  obsessions restored: {[o.domain for o in agent2.obsessions.all()]}")
        print(f"  traumas restored: {len(agent2.my_traumas())}")

        # The restored trauma still fires on similar context.
        result = agent2.ingest("Reviewing a PR with tricky edge cases.")
        print(f"  warnings on new ingest: {len(result.trauma_warnings)}")
        for st in result.trauma_warnings:
            print(f"    [{st.access.value}] {st.rendered_text}")

        pop2.close()


if __name__ == "__main__":
    main()
