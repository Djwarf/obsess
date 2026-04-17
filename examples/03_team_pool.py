"""Three agents on a team; one records a team failure that all members see.

Shows:
- Pool creation via Bonding.teambuild.
- Pool-scoped obsessions (only members can activate against them).
- Pool traumas (team failures; visible to all pool members without per-agent
  share records; rendered with AccessMode.POOL).

Run: python examples/03_team_pool.py
"""

from obsess import Population
from obsess.types import SeedType


def main() -> None:
    pop = Population.new()

    for agent_id in ["alice", "bob", "carol"]:
        pop.spawn(agent_id)

    # Form the team — pool + pairwise TEAM edges.
    pool = pop.bonding.teambuild("billing_team", ["alice", "bob", "carol"])
    print(f"Pool formed: {pool.name} (members: {sorted(pool.member_ids)})")
    print()

    # A pool-scoped obsession. Non-members can't activate against it.
    billing_def = pop.shared_obsessions.define(
        domain="billing_correctness",
        description="prevent overcharge underbill duplicate invoice errors",
        owner_pool_id=pool.id,
    )

    for agent_id in pool.member_ids:
        pop.get_agent(agent_id).activate_shared_obsession(
            billing_def.id,
            seed_types=[SeedType.NEED_FOR_SUCCESS],
            commitment=0.7,
        )

    # Alice records a team failure. This is a *pool trauma* — no individual
    # could have prevented it with local information. No TraumaShare records
    # are needed: pool membership is the access control.
    pop.get_agent("alice").record_failure(
        context="Billing pipeline sent duplicate invoice to customer after retry.",
        failure="No correlation between first send and retry — team-level state issue.",
        attempted_solutions=["idempotency check at producer", "retry-safe receiver"],
        cost="Customer complaint, refund issued, reputation hit",
        unsolvable_at_time=True,
        linked_obsession_id=billing_def.id,
        pool_id=pool.id,
    )
    print("Alice recorded a pool trauma (team failure).")
    print()

    # Each member encounters a similar context later. The team trauma fires
    # for all members, including the recorder, with AccessMode.POOL.
    observation = "Investigating a duplicate invoice issue this morning."
    for agent_id in ["alice", "bob", "carol"]:
        result = pop.get_agent(agent_id).ingest(observation)
        pool_warnings = [st for st in result.trauma_warnings if st.access.value == "pool"]
        print(f"{agent_id:<6} saw {len(pool_warnings)} pool warning(s)")
        for st in pool_warnings:
            print(f"       {st.rendered_text}")


if __name__ == "__main__":
    main()
