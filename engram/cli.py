from __future__ import annotations

import json
import sys

from engram.embed import SentenceTransformerEmbedder
from engram.population import Population
from engram.types import SeedType


def _pretty(result_dict: dict) -> str:
    return json.dumps(result_dict, indent=2, default=str)


def demo() -> None:
    """End-to-end walkthrough of the architecture.
    Uses Nomic-embed-v2-moe for real semantic similarity. Mock LLM still
    handles the semantic-judgment layer (scoring, impression formation,
    regeneration) until we wire up a local model."""

    print("Loading Nomic v2 MoE embedder (first run downloads ~500MB)...")
    embedder = SentenceTransformerEmbedder(target_dim=256)
    print(f"  embedder dim: {embedder.dim} (Matryoshka-truncated from 768)")
    print()

    pop = Population.new(embedder=embedder)
    mem = pop.spawn(agent_id="demo_agent")

    print("=" * 60)
    print("Seeding obsessions")
    print("=" * 60)

    physics = mem.seed_obsession(
        domain="physics",
        description="quantum field theory, renormalization, gauge symmetry",
        seed_types=[SeedType.CURIOSITY, SeedType.DELIBERATE_STUDY, SeedType.BEST_IN_WORLD],
        commitment=0.9,
    )
    teaching = mem.seed_obsession(
        domain="teaching_my_kid",
        description="explain science to my child in ways they understand",
        seed_types=[SeedType.NEED_FOR_SUCCESS],
        commitment=0.6,
    )
    provision = mem.seed_obsession(
        domain="family_provision",
        description="provide for everyone who depends on me",
        seed_types=[SeedType.PROVISION],
        commitment=1.0,
        identity_level=True,
    )

    print(f"  physics: {physics.commitment}")
    print(f"  teaching: {teaching.commitment}")
    print(f"  provision (identity-level): {provision.commitment}")

    print()
    print("=" * 60)
    print("Ingest: high-alignment content (physics)")
    print("=" * 60)
    r = mem.ingest("Renormalization handles UV divergences in QFT by absorbing infinities into bare parameters.")
    print(f"  action: {r.action}")
    print(f"  scored: {r.scored_obsessions[:3]}")
    if r.impression:
        print(f"  impression: {r.impression.seed_text}")

    print()
    print("=" * 60)
    print("Ingest: low-alignment content (should drop)")
    print("=" * 60)
    r = mem.ingest("Taylor Swift's new album dropped today. Critics are calling it her best yet.")
    print(f"  action: {r.action}   (dropped at the gate)")
    print(f"  scored: {r.scored_obsessions[:3]}")

    print()
    print("=" * 60)
    print("Record a trauma (teaching failure)")
    print("=" * 60)
    trauma = mem.record_failure(
        context="Tried to explain entropy to my 7-year-old using dice analogies",
        failure="Could not ground it in anything they understood; they lost interest",
        attempted_solutions=["dice analogies", "verbal 2nd law", "analogy to messy rooms"],
        cost="They disengaged from science that evening",
        unsolvable_at_time=True,
        linked_obsession_id=teaching.id,
    )
    print(f"  trigger_pattern: {trauma.trigger_pattern}")
    print(f"  still_firing: {trauma.still_firing}")

    print()
    print("=" * 60)
    print("Ingest something similar -> trauma should SELF-SURFACE")
    print("=" * 60)
    r = mem.ingest("Thinking about how to explain thermodynamics to a 7-year-old tomorrow.")
    print(f"  action: {r.action}")
    print(f"  trauma_warnings: {len(r.trauma_warnings)}")
    for w in r.trauma_warnings:
        print(f"    - failure: {w.failure[:80]}")
        print(f"      tradeoffs: {w.resolution_tradeoffs}")

    print()
    print("=" * 60)
    print("Resolve the trauma with a tradeoff (still keeps firing)")
    print("=" * 60)
    mem.resolve_with_tradeoff(
        trauma.id,
        "Used Lego-block analogy; worked for entropy but oversimplified the microstate count",
    )
    print("  tradeoff appended. Surfacing again:")
    r = mem.ingest("Wondering how to explain heat death to my child tomorrow.")
    for w in r.trauma_warnings:
        print(f"    - failure: {w.failure[:80]}")
        print(f"      tradeoffs: {w.resolution_tradeoffs}")
    print("  (note: the warning still fires, now carrying the tradeoff)")

    print()
    print("=" * 60)
    print("Query (retrieval regenerates through current frame)")
    print("=" * 60)
    q = mem.query("What do I know about QFT?")
    print(f"  frame: {q.current_frame}")
    print(f"  impressions used: {len(q.impressions_used)}")
    print(f"  answer: {q.answer}")

    print()
    print("=" * 60)
    print("Snapshot")
    print("=" * 60)
    print(_pretty(mem.snapshot()))

    print()
    print("=" * 60)
    print("Evolution store (meta-layer observation)")
    print("=" * 60)
    for ev in pop.evolution.all():
        print(f"  {ev.kind:<28} agent={ev.agent_id} payload={ev.payload}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "demo":
        demo()
    else:
        print(f"unknown command: {args[0]}")
        print("try: python -m engram.cli demo")
        sys.exit(1)


if __name__ == "__main__":
    main()
