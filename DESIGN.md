# obsess, a memory system modeled on a specific mind

## Why this exists

Standard AI memory (RAG, vector DB) embeds everything and sorts later. It has no model of what should have been ignored at the gate, no model of what a memory *means* to the person who owns it, and no model of failure as a separate encoding class. This project is a deliberate departure: we design memory by modeling it on the owner of the system, not on "general human memory" or on what's easy to implement with a vector store.

The owner has described their own memory with the following properties. The architecture below encodes those properties directly.

## Observed properties of the owner's memory

1. **Utility-gated encoding.** Information only fully stores if it serves an active expertise or obsession. Names, news, pop culture, filtered at the gate, never encoded. Physics, math, domains of mastery, encoded richly.

2. **Compression at encode, regeneration at retrieve.** What persists is a summary, not the original text. On recall, the memory is re-synthesized *through the owner's current frame*, not played back verbatim. Fidelity is to the current understanding, not to the source.

3. **Two pathways:**
   - **Regular** memory is reconstructive (property 2).
   - **Trauma** memory is verbatim, self-surfacing. It is not emotionally negative by definition, it is failure-linked. The trigger to encode a trauma is `surprise × cost × unsolvability-at-time`. Trauma surfaces itself when the current context pattern-matches the past failure.
   - The trauma *record* is always immutable (append-only). For the origin agent, the record reads verbatim, immunity to current-frame narrative rewriting is the point. In multi-agent contexts, inheritors of a shared trauma re-synthesize the record through their own frame at firing time; see DESIGN-MULTI.md for the render-layer split.

4. **Trauma keeps firing after resolution.** Solving a trauma does not silence it, the warning keeps firing, but now carries the resolution context (which tradeoff was taken, what it cost). Most problems are not solvable perfectly; the residual uncertainty is preserved.

5. **Trauma → obsession.** Unsolved trauma seeds obsession. Obsession is the encoding gate. So failure-to-close drives what future knowledge forms. Feedback loop.

6. **Six obsession-seed pathways:** trauma, curiosity, need-for-success, deliberate study, being-best-in-the-world, and **provision / burden-of-care** (responsibility for people who depend on you). Each leaves distinct metadata on the obsession.

7. **Provision is identity-level.** Unlike the other five (each domain-specific), provision is always-on and acts as a *global priority modulator*. It raises the commitment level on any obsession that is instrumentally useful for supporting the people the owner is responsible for. It also makes any trauma linked to provision unsilenceable, the stakes do not let it fade.

## Architecture

### Core objects

- **Obsession**: `{ domain_signature, commitment, seed_types[], seed_metadata, last_activation, decay_rate }`. Multiple seed types can accumulate on one obsession. Commitment is 0..1 and decays without activation.
- **Impression**: the compressed seed produced at ingest time, shaped by the frame at encoding and tagged with the obsession that gated it. Not a recording of the source, it's what impressed upon the system *through* the current frame. At retrieval, impressions are re-synthesized through the *current* frame, which may differ from `frame_at_encode`. Impressions are *seeds*, not outputs.
- **Trauma**: verbatim record `{ context, failure, attempted_solutions, resolution_tradeoffs, trigger_pattern, linked_obsession, still_firing }`. Never rewritten, only appended with resolution notes.

### Pipelines

**Ingest.**
1. Score incoming content against each active obsession. Any one above a threshold → encode.
2. If matched against a known trauma trigger pattern → surface the trauma *before* encoding, as a warning with tradeoff context.
3. If a failure event is detected in the content (user-flagged or LLM-classified) → append to trauma store, with `unsolvability-at-time` recorded if so. Link to an obsession (seeds a new one if none fits).
4. High-alignment content → form an impression (compressed through the current obsession frame) and store with obsession link.
5. Low-alignment content → drop.

**Retrieve (pull, user-initiated).**
1. Identify relevant impressions via obsession alignment + semantic match.
2. Identify any trauma whose trigger matches the query.
3. LLM regenerates an answer by re-synthesizing impressions through the **current** obsession frame (not the frame they were encoded in). Trauma records are surfaced verbatim alongside.

**Retrieve (push, trauma firing).**
1. On every ingest and every query, the active context is matched against trauma trigger patterns.
2. Matches surface verbatim, interrupting the main flow, with resolution tradeoffs attached.

**Consolidation (background).**
- Within an obsession, merge related impressions.
- Decay commitment on obsessions without recent activation (except identity-level ones like provision).
- Never delete trauma. Update its status, append tradeoffs, but keep the record.

### Why this is a real departure

Standard RAG: `embed(chunk) → store → retrieve top-k → return text`.

Obsess:
- Writes are *gated*, not accepted by default.
- Storage is *impression*, not chunk, compression is part of encoding.
- Retrieval is *regeneration*, not playback, the answer is synthesized through the current frame of mind.
- Trauma is a *separate class* with different encoding, storage, and triggering rules, and it's *push-based*, not pull-based.
- Obsessions are first-class. They are the encoding gate, the retrieval lens, and the thing that carries identity-level state like provision.

## Stack

- Python 3.10+ (tested 3.10 to 3.13), in a venv.
- `sentence-transformers` for semantic embeddings (optional; `HashEmbedder` works with no deps).
- Provider-agnostic LLM layer in `obsess/providers/` with concrete backends for llama.cpp, Ollama, Anthropic, OpenAI-compatible (OpenAI, DeepSeek, Mistral, Groq, Together, xAI, Fireworks), and Gemini. `MockLLM` runs the flow without any SDK.
- NumPy for similarity. Storage is plug-and-play via the `Storage` protocol in `obsess/storage/`; `InMemoryStorage` and `SQLiteStorage` ship with the library.

## Current status (v0.1.0)

Implemented and tested (61 tests across Python 3.10 to 3.13):

- Per-agent memory: utility-gated ingest, impressions with frame-shifted regeneration, trauma as a separate verbatim class, six obsession seed pathways.
- Multi-agent architecture per `DESIGN-MULTI.md`: four relationship kinds, formation-time obsession propagation, eager trauma propagation, pool primitives, render layer.
- Meta-layer per `DESIGN-META.md`: Creator, Selection, Bonding fully built.
- Real LLM providers with Qwen3-4B end-to-end integration test.
- Persistent storage via `SQLiteStorage`; agents survive process restart via `Population.rehydrate_agent`.
- CLI (`obsess-demo`) for the original single-agent walkthrough.

Still deferred (not yet implemented):

- Background consolidation loop: `Obsession.decay()` and `KindMeta.decays` are defined but no scheduler invokes them. Decay is caller-driven today.
- Activation-time obsession propagation (the existing path is formation-time only).
- LLM-driven trauma render for FULL-share inheritors (current render is templated).
- Pool aggregation (weighted-mean commitment across members).
- Semantic failure-registry matching (Creator uses exact domain-overlap today).
- Any UI beyond the CLI.
