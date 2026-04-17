"""obsess quickstart — single agent, in-memory, MockLLM.

Shows: Population construction, seeding an obsession, utility-gated ingest
(content that matches the obsession is stored; content that doesn't is dropped),
and retrieval through the current frame.

Run: python examples/01_quickstart.py
"""

from obsess import Population
from obsess.types import SeedType


def main() -> None:
    pop = Population.new()
    agent = pop.spawn("assistant")

    # The encoding gate. Agents only form memories for content aligned with
    # their obsessions. Everything else is dropped at ingest time.
    agent.seed_obsession(
        domain="code_quality",
        description="write clean readable tested code refactor handler validate bugs",
        seed_types=[SeedType.NEED_FOR_SUCCESS, SeedType.DELIBERATE_STUDY],
        commitment=0.85,
    )

    # Ingest several observations; only those matching the obsession are stored.
    observations = [
        "Just added unit tests for the new payment handler.",
        "Taylor Swift released a new album today.",
        "Refactored code in the auth handler to improve readability.",
        "The weather forecast predicts rain this weekend.",
    ]

    for obs in observations:
        result = agent.ingest(obs)
        marker = {"stored": "✓", "dropped": "✗"}.get(result.action, "?")
        print(f"  {marker} {result.action:<20}{obs}")

    print()

    # Retrieval — the answer is synthesized through the agent's current frame.
    query = "What do I know about our test coverage?"
    result = agent.query(query)
    print(f"Query:  {query}")
    print(f"Frame:  {result.current_frame}")
    print(f"Answer: {result.answer}")
    print(f"Impressions used: {len(result.impressions_used)}")


if __name__ == "__main__":
    main()
