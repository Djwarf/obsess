# obsess

[![PyPI](https://img.shields.io/pypi/v/obsess.svg)](https://pypi.org/project/obsess/)
[![Python](https://img.shields.io/pypi/pyversions/obsess.svg)](https://pypi.org/project/obsess/)
[![License](https://img.shields.io/pypi/l/obsess.svg)](LICENSE)
[![CI](https://github.com/Djwarf/obsess/actions/workflows/tests.yml/badge.svg)](https://github.com/Djwarf/obsess/actions/workflows/tests.yml)

**A memory system for LLM multi-agent pipelines.** Plug-and-play LLM providers (llama.cpp, Ollama, Anthropic, OpenAI-compatible, Gemini), plug-and-play storage (in-memory, SQLite, or your own), and a memory model that treats agent relationships as first-class: siblings share differently than peers, a master and a prodigy share differently than parent and child, a team's failure is not any individual's failure.

Standard multi-agent memory puts everything in one store and lets every agent read from it. obsess doesn't. Memory is **utility-gated** (only content that matches an active obsession is encoded), **compressed into impressions** (regenerated through the current frame at retrieval), and distinguishes **trauma** (verbatim, self-surfacing, failure-linked) from regular recall. When multiple agents are in play, relationships shape what flows between them: obsessions inherit through parent/child edges, warnings propagate across peers, team failures live in pools.

---

## Install

```bash
pip install obsess

# Or with LLM providers you use:
pip install "obsess[anthropic]"           # Claude
pip install "obsess[llamacpp]"            # Local GGUF
pip install "obsess[openai]"              # OpenAI + compatible (DeepSeek, Mistral, Groq, ...)
pip install "obsess[all-providers]"       # Everything

# With semantic embeddings (optional; HashEmbedder works with no deps):
pip install "obsess[embeddings]"
```

From source:

```bash
git clone https://github.com/djwarf/obsess
cd obsess
pip install -e ".[all]"
```

---

## Quickstart

```python
from obsess import Population
from obsess.types import SeedType

pop = Population.new()                    # in-memory; swap storage with SQLiteStorage(path)
agent = pop.spawn("assistant")

# What this agent cares about, the encoding gate
agent.seed_obsession(
    domain="code_quality",
    description="write clean readable tested code",
    seed_types=[SeedType.NEED_FOR_SUCCESS],
    commitment=0.8,
)

# Ingest, only gate-clearing content is encoded
agent.ingest("I just fixed a null check in the auth handler.")    # stored
agent.ingest("Taylor Swift released a new album today.")          # dropped

# Retrieve, synthesized through the current frame
result = agent.query("What do I know about the auth handler?")
print(result.answer)
```

See [`examples/`](examples/) for multi-agent scenarios, pools, persistence, and real-LLM integration.

---

## Why obsess

| Standard RAG | obsess |
|---|---|
| Everything embeds, sorts at retrieval | Gate at encode: most content is *not* stored |
| Chunks are stored verbatim | Impressions are compressed through the current frame |
| Retrieval is playback | Retrieval is regeneration through the *current* frame |
| Failure is just more text | Trauma is a separate encoding class, verbatim, self-surfacing, immune to narrative rewriting |
| Multi-agent = shared store, everyone reads | Multi-agent = typed relationships, sharing rules per kind, non-transitive |
| Memory is static | Relationship topology shapes what flows across agents |

---

## Provider selection

The semantic layer (scoring, impression formation, regeneration) lives in one place; swapping LLM backends is a drop-in change.

```python
from obsess import Population, ProviderSemantics

# Local GGUF via llama.cpp (Qwen3, Gemma, Llama, Mistral, ...)
from obsess.providers import LlamaCppProvider
llm = ProviderSemantics(LlamaCppProvider("/path/to/model.gguf"))

# Anthropic (Claude)
from obsess.providers import AnthropicProvider
llm = ProviderSemantics(AnthropicProvider(model="claude-sonnet-4-6"))

# OpenAI, and DeepSeek, Mistral, Groq, Together, xAI, Fireworks via the same class
from obsess.providers import OpenAICompatibleProvider
llm = ProviderSemantics(OpenAICompatibleProvider(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key="...",
    strict_schema=False,  # DeepSeek doesn't do strict JSON schema yet
))

# Google Gemini
from obsess.providers import GeminiProvider
llm = ProviderSemantics(GeminiProvider(model="gemini-2.5-flash"))

# Ollama
from obsess.providers import OllamaProvider
llm = ProviderSemantics(OllamaProvider(model="qwen3:4b"))

pop = Population.new()
agent = pop.spawn("assistant", llm=llm)
```

Writing a new provider is ~50 lines implementing the `Provider` protocol. See [`obsess/providers/`](obsess/providers/).

---

## Storage selection

```python
from obsess import Population
from obsess.storage.sqlite import SQLiteStorage

# In-memory (default; transient)
pop = Population.new()

# SQLite (persistent across sessions)
pop = Population.new(storage=SQLiteStorage("obsess.db"))

# Rehydrate agents from a prior session
for agent_id in pop.agent_ids_on_record():
    pop.rehydrate_agent(agent_id)          # pass llm= if needed
```

Custom backends (Postgres, Redis, DynamoDB, ...) implement the `Storage` protocol. See [`obsess/storage/`](obsess/storage/).

---

## Multi-agent: relationships and pools

```python
from obsess import Population, ObsessionSpec, RelationshipKind
from obsess.types import SeedType

pop = Population.new()

# A shared obsession both agents can activate against
code_quality = pop.shared_obsessions.define(
    domain="code_quality",
    description="write clean readable tested code",
)

master = pop.creator.propose("master", [ObsessionSpec(
    shared_definition_id=code_quality.id,
    seed_types=[SeedType.DELIBERATE_STUDY],
    commitment=0.9,
)]).agent

prodigy = pop.spawn("prodigy")

# Prodigy inherits the master's obsession with bootstrapped commitment
pop.form_relationship(RelationshipKind.MASTER_PRODIGY, "master", "prodigy")
assert prodigy.obsessions.get(code_quality.id) is not None

# When master records a failure, prodigy sees it via trauma propagation
master.record_failure(
    context="missed a null check in review",
    failure="production bug shipped",
    attempted_solutions=["manual review"],
    cost="hotfix + postmortem",
    unsolvable_at_time=True,
    linked_obsession_id=code_quality.id,
)

# Prodigy encounters similar context, master's warning fires, rendered through
# prodigy's current frame
r = prodigy.ingest("About to review a PR for null safety.")
for surfaced in r.trauma_warnings:
    print(f"[{surfaced.access.value}] {surfaced.rendered_text}")
```

Four relationship kinds:

- `TEAM`, pool formation, warning-share both directions.
- `PEER`, visibility-granting, no-share by default.
- `PARENT_CHILD`, directional, non-decaying, obsessions inherit attenuated.
- `MASTER_PRODIGY`, directional, decaying, prodigy bootstraps to master's level.

See [`DESIGN-MULTI.md`](DESIGN-MULTI.md) for the full relationship model.

---

## Integrating with agent frameworks

obsess is framework-neutral, it provides memory state; your framework provides the reasoning loop. See [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) for patterns with LangChain, the Claude Agent SDK, and raw tool-loop agents.

The core pattern is a sandwich around each LLM call:

```python
# Before the LLM call
ingest_result = agent.ingest(observation)
warnings = [st.rendered_text for st in ingest_result.trauma_warnings]

# Augment the prompt
prompt = (
    f"{user_message}\n\n"
    f"Memory warnings: {warnings}" if warnings else user_message
)

# Your framework's call
response = my_framework.chat(prompt)

# After, flag failures explicitly if you detect one
if detected_failure:
    agent.record_failure(context=..., failure=..., ...)
```

---

## Documentation

- [`DESIGN.md`](DESIGN.md): per-agent memory architecture (utility gate, impressions, trauma, obsessions).
- [`DESIGN-MULTI.md`](DESIGN-MULTI.md): multi-agent model. Ownership modes, relationship kinds, pools, propagation, render layer.
- [`DESIGN-META.md`](DESIGN-META.md): meta-layer. Creator, Evolution selection, Bonding.
- [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md): plugging obsess into common agent frameworks (LangChain, Claude Agent SDK, raw tool loops).
- [`examples/`](examples/): runnable scenarios.
- [`CHANGELOG.md`](CHANGELOG.md): release notes.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): how to contribute.

---

## Status

Alpha (v0.1.0). The architecture is complete and tested (61 tests, CI green on Python 3.10 to 3.13, end-to-end verified against Qwen3-4B). The API may evolve with real-world use. Feedback and contributions welcome.
