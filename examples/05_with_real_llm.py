"""obsess with a real LLM via the provider layer.

Shows:
- Wiring a Provider (Anthropic, OpenAI-compatible, Gemini, local GGUF, Ollama)
  into the semantic layer via ProviderSemantics.
- Same obsess code regardless of provider — swap the Provider instance, the
  rest of the pipeline is identical.

Provider selection is picked via the OBSESS_PROVIDER environment variable,
or falls back to MockLLM. See below for each provider's env vars.

Run:
    # Anthropic:
    OBSESS_PROVIDER=anthropic ANTHROPIC_API_KEY=... python examples/05_with_real_llm.py
    # OpenAI:
    OBSESS_PROVIDER=openai OPENAI_API_KEY=... python examples/05_with_real_llm.py
    # Local GGUF:
    OBSESS_PROVIDER=llamacpp OBSESS_GGUF_PATH=/path/to/model.gguf python examples/05_with_real_llm.py
    # Ollama (running daemon):
    OBSESS_PROVIDER=ollama OBSESS_OLLAMA_MODEL=qwen3:4b python examples/05_with_real_llm.py
    # Gemini:
    OBSESS_PROVIDER=gemini GOOGLE_API_KEY=... python examples/05_with_real_llm.py
"""

import os

from obsess import Population, ProviderSemantics
from obsess.llm import LLM, MockLLM
from obsess.types import SeedType


def pick_llm() -> LLM:
    choice = os.environ.get("OBSESS_PROVIDER", "mock").lower()
    if choice == "anthropic":
        from obsess.providers import AnthropicProvider
        return ProviderSemantics(AnthropicProvider(model="claude-sonnet-4-6"))
    if choice == "openai":
        from obsess.providers import OpenAICompatibleProvider
        return ProviderSemantics(OpenAICompatibleProvider(model="gpt-5"))
    if choice == "llamacpp":
        from obsess.providers import LlamaCppProvider
        path = os.environ["OBSESS_GGUF_PATH"]
        return ProviderSemantics(LlamaCppProvider(path, verbose=False))
    if choice == "ollama":
        from obsess.providers import OllamaProvider
        model = os.environ.get("OBSESS_OLLAMA_MODEL", "qwen3:4b")
        return ProviderSemantics(OllamaProvider(model=model))
    if choice == "gemini":
        from obsess.providers import GeminiProvider
        return ProviderSemantics(GeminiProvider(model="gemini-2.5-flash"))
    return MockLLM()


def main() -> None:
    llm = pick_llm()
    print(f"Using LLM: {type(llm).__name__}"
          f"{' / ' + type(llm.provider).__name__ if isinstance(llm, ProviderSemantics) else ''}")
    print()

    pop = Population.new()
    agent = pop.spawn("researcher", llm=llm)

    agent.seed_obsession(
        domain="physics",
        description="quantum field theory renormalization gauge symmetry",
        seed_types=[SeedType.CURIOSITY, SeedType.DELIBERATE_STUDY],
        commitment=0.9,
    )

    inputs = [
        "Renormalization handles UV divergences in QFT by absorbing infinities into bare parameters.",
        "Gauge invariance dictates the form of interactions in the Standard Model.",
        "The new season of my favorite show just dropped.",
    ]
    for text in inputs:
        r = agent.ingest(text)
        print(f"  {r.action:<20}{text[:70]}{'...' if len(text) > 70 else ''}")
    print()

    q = "What do I know about renormalization?"
    result = agent.query(q)
    print(f"Query:  {q}")
    print(f"Frame:  {result.current_frame}")
    print(f"Answer: {result.answer}")


if __name__ == "__main__":
    main()
