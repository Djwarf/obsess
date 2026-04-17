# Contributing to obsess

Thanks for considering a contribution. This document covers how to get a local dev environment running, what to work on, and the expectations around issues and PRs.

## Dev environment

```bash
git clone https://github.com/Djwarf/obsess
cd obsess
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[all]"            # installs obsess plus every optional provider SDK
```

Run the full test suite:

```bash
python -m unittest discover -s tests -v
```

The llama.cpp integration test is skipped by default. To exercise it, point it at a local GGUF file:

```bash
OBSESS_GGUF_PATH=/path/to/model.gguf python -m unittest tests.test_llama_cpp
```

## Where to start

Good areas for contribution, roughly ordered by approachability:

- **New LLM providers.** Implement the `Provider` protocol in `obsess/providers/` for a backend that isn't covered yet. See the existing providers as templates; each is around 50 lines.
- **New storage backends.** Implement the `Storage` protocol in `obsess/storage/` (Postgres, Redis, DynamoDB, etc.). See `memory.py` and `sqlite.py` as references.
- **Documentation.** Tutorials, framework integration write-ups in `docs/INTEGRATIONS.md`, example scripts in `examples/`, better error messages.
- **Decay and consolidation loop** (DESIGN.md, DESIGN-MULTI.md). `Obsession.decay()` exists but is not invoked anywhere; relationship-strength decay is defined in `KIND_META` but not applied. A background consolidation pass that runs on a cadence would close this gap.
- **Activation-time obsession propagation.** Formation-time propagation is implemented in `Population.form_relationship`. The analogue for "master later activates a new shared obsession and prodigy inherits" is not.
- **LLM-driven trauma render.** `SurfacedTrauma.rendered_text` for FULL inheritors uses a template string. A real LLM re-synthesis through the inheritor's frame is a natural extension.
- **Pool aggregation.** Weighted-mean commitment across pool members (DESIGN-MULTI.md) is specified but not computed or exposed.
- **Semantic failure-registry matching.** `Creator._check_failure_registry` uses exact domain-string overlap. Embedding-based similarity (using the existing `Embedder`) would match fuzzy cases.
- **Pool dissolution, retirement enforcement, slice attribution.** Smaller refinements listed as deferred in the design docs.

Open an issue before starting on anything non-trivial so we can align on the approach.

## Pull request expectations

- Tests accompany behavioral changes. `python -m unittest discover -s tests` must pass.
- Public API gets docstrings. Internal helpers may skip them.
- Style matches the surrounding code. No enforced linter in v1; leave the code better than you found it.
- One logical change per PR. Unrelated fixes go in separate PRs.
- Reference the issue number in the PR description when relevant.

## Commit style

- Imperative mood in the subject line ("Add X" not "Added X").
- Keep the subject under 72 characters.
- Body explains the why when the change is non-obvious.

## Reporting bugs and requesting features

Use the GitHub issue forms:

- [Bug report](https://github.com/Djwarf/obsess/issues/new?template=bug_report.yml)
- [Feature request](https://github.com/Djwarf/obsess/issues/new?template=feature_request.yml)

## Architecture pointers

The design docs spell out the reasoning behind the architecture; read them before touching anything structural:

- [`DESIGN.md`](DESIGN.md): per-agent memory (utility gate, impressions, trauma, obsessions).
- [`DESIGN-MULTI.md`](DESIGN-MULTI.md): multi-agent model (ownership modes, relationships, pools, propagation, render layer).
- [`DESIGN-META.md`](DESIGN-META.md): meta-layer operators (Creator, Evolution selection, Bonding).

## Licence

MIT. By contributing you agree your contributions are licensed under the same terms (see [LICENSE](LICENSE)).
