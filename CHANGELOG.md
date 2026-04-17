# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Author field updated to `djwarf <hello@switchsides.co.uk>` (shipped in the next release; v0.1.0 on PyPI still shows the initial metadata).
- Design documents (`DESIGN.md`, `DESIGN-MULTI.md`, `DESIGN-META.md`) have current-status sections describing what's implemented vs still deferred, so readers can distinguish live behaviour from architectural intent.
- README points to `CONTRIBUTING.md` and `CHANGELOG.md` alongside the design docs.

### Added

- `CONTRIBUTING.md`: dev setup, PR expectations, areas good for contribution.
- GitHub issue templates (bug report, feature request), PR template, disabled blank issues.
- README badges: PyPI version, Python versions, licence, CI status.
- GitHub release for v0.1.0 with highlighted release notes.

## [0.1.0] - 2026-04-17

Initial release.

### Added

- **Per-agent memory** (`DESIGN.md`): utility-gated ingest, impressions with
  frame-shifted regeneration at retrieval, trauma as a separate verbatim
  encoding class, six obsession-seed pathways including identity-level provision.
- **Multi-agent architecture** (`DESIGN-MULTI.md`):
  - Three ownership modes: `private`, `shared-from-owner`, `pooled`.
  - Four relationship kinds (`team`, `peer`, `parent_child`, `master_prodigy`)
    with per-kind `KindMeta` defaults and direction-aware propagation.
  - `SharedObsessions` pool for shared definitions; `ObsessionRegistry`
    splits `ObsessionDefinition` (identity) from `ObsessionActivation`
    (per-agent state with `earned_commitment` + `bootstrapped_commitment`).
  - `RelationshipGraph` with flat queries (non-transitive by design).
  - `PoolRegistry` for team pools; pool-scoped obsessions and pool traumas.
  - `TraumaShares` for per-agent trauma sharing via relationship edges.
  - Formation-time obsession propagation with per-relationship attenuation.
  - Eager trauma propagation on `record_failure`.
  - Render layer: `SurfacedTrauma` wrapper with `AccessMode` enum
    (ORIGIN / FULL / WARNING / POOL) and per-mode rendering.
- **Meta-layer** (`DESIGN-META.md`):
  - `Creator` produces agents, queries failure-registry view via Evolution,
    supports `WARN` / `REFUSE` / `IGNORE` policies.
  - `Selection` applies population pressure (retirement, config promotion).
  - `Bonding` produces relationships via pluggable strategies (`genetic`,
    `teambuild`, `hiring`, `luck` with seeded RNG).
  - `EvolutionStore` is single source of truth for population-level history.
- **Provider-agnostic LLM layer**:
  - `Provider` protocol and `ProviderSemantics` that hosts all prompts and
    JSON schemas in one place.
  - Concrete providers: `LlamaCppProvider` (local GGUF), `OllamaProvider`,
    `AnthropicProvider`, `OpenAICompatibleProvider` (covers OpenAI, DeepSeek,
    Mistral, Groq, Together, xAI, Fireworks), `GeminiProvider`.
  - `MockLLM` for tests and prototyping.
  - `<think>` reasoning-token stripping in providers.
- **Plug-and-play storage layer**:
  - `Storage` protocol: append-only event log (indexed `kind` + `agent_id`)
    + id-keyed entity collections.
  - `InMemoryStorage` (default, transient) and `SQLiteStorage` (persistent,
    stdlib, WAL journal mode).
  - Write-through caches in every store; `Population.rehydrate_agent` for
    restoring agents across sessions.
- **Package** (`pyproject.toml`): installable, optional-dep extras per
  provider, `obsess-demo` script entry.
- **Examples** (`examples/`): quickstart, multi-agent relationships, team
  pools, persistence, real-LLM provider selection.
- **Docs** (`docs/INTEGRATIONS.md`): LangChain, Claude Agent SDK, raw
  tool-loop agent patterns.
- **Tests**: 61 passing (57 unit/contract + 4 llama-cpp integration skipped
  without `OBSESS_GGUF_PATH`); validated end-to-end against Qwen3-4B-Q4_K_M.

### Notes

- This repository was initially published under the name `engram` on GitHub
  and renamed to `obsess` before PyPI publish due to a namespace collision
  with a pre-existing placeholder package.

[Unreleased]: https://github.com/Djwarf/obsess/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Djwarf/obsess/releases/tag/v0.1.0
