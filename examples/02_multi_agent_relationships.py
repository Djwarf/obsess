"""Two agents in a master/prodigy relationship.

Shows:
- Shared obsession definition activated by both agents.
- Obsession inheritance at relationship formation (prodigy bootstraps from master).
- Trauma propagation: master records a failure; prodigy later sees it fire,
  rendered through the prodigy's own frame (AccessMode.FULL).

Run: python examples/02_multi_agent_relationships.py
"""

from engram import ObsessionSpec, Population
from engram.relationships import RelationshipKind
from engram.types import SeedType


def main() -> None:
    pop = Population.new()

    # A shared obsession identity — both agents will activate against it.
    code_quality = pop.shared_obsessions.define(
        domain="code_quality",
        description="write clean readable tested code without null pointer bugs",
    )

    # Master: high commitment, deliberate study seed.
    master = pop.creator.propose("master", [ObsessionSpec(
        shared_definition_id=code_quality.id,
        seed_types=[SeedType.DELIBERATE_STUDY, SeedType.BEST_IN_WORLD],
        commitment=0.9,
    )]).agent

    # Prodigy is spawned fresh — no obsessions yet.
    prodigy = pop.spawn("prodigy")
    assert prodigy.obsessions.get(code_quality.id) is None

    # Forming the relationship propagates the master's shared obsessions
    # downstream with bootstrapped commitment (default attenuation = 1.0).
    pop.form_relationship(RelationshipKind.MASTER_PRODIGY, "master", "prodigy")

    prodigy_ob = prodigy.obsessions.get(code_quality.id)
    print(f"Prodigy inherited obsession: {prodigy_ob.domain}")
    print(f"  earned commitment:       {prodigy_ob.activation.earned_commitment:.2f}")
    print(f"  bootstrapped commitment: {prodigy_ob.activation.bootstrapped_commitment:.2f}")
    print(f"  total:                   {prodigy_ob.commitment:.2f}")
    print()

    # Master records a failure. This propagates a trauma share downstream.
    master.record_failure(
        context="Missed a null check in code review before merge.",
        failure="Production bug shipped; hotfix required.",
        attempted_solutions=["manual review", "CI linter"],
        cost="Hotfix + postmortem + lost trust",
        unsolvable_at_time=True,
        linked_obsession_id=code_quality.id,
    )

    # Prodigy encounters similar context. Master's trauma fires for prodigy
    # with AccessMode.FULL (full-share inheritance per parent/child defaults).
    observation = "About to review a PR that touches null-sensitive code paths."
    result = prodigy.ingest(observation)
    print(f"Prodigy ingested: {observation}")
    print(f"  action: {result.action}")
    print(f"  warnings fired: {len(result.trauma_warnings)}")
    for st in result.trauma_warnings:
        origin = "self" if st.trauma.origin_agent_id == prodigy.agent_id else st.trauma.origin_agent_id
        print(f"    [{st.access.value}] (origin: {origin})")
        print(f"      {st.rendered_text}")


if __name__ == "__main__":
    main()
