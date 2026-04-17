# obsess, meta-layer architecture

## What this document adds

`DESIGN.md` specifies the per-agent architecture. `DESIGN-MULTI.md` specifies how multiple agents relate: ownership modes, relationship kinds, pooling, propagation. This document covers the **meta-layer**: system components that operate on agents rather than alongside them. They create agents, apply selection pressure to populations over time, and produce the relationships between agents.

The meta-layer is not a third tier of obsess agents. Meta-components are **system components, not obsess agents**, they do not have utility-gated ingest, do not form impressions, and do not use trauma machinery. They have memory, but it is structured differently from agent memory, because they have different constraints.

## Core framing

Two tiers:

- **Tier 1, Agents.** Specific minds, bounded attention, per-agent memory (`DESIGN.md` + `DESIGN-MULTI.md`).
- **Tier 2, Meta-components.** Operate on the Tier-1 graph. Omniscient or near-omniscient in their scope. No frames, no impressions, no trauma.

Three meta-components:

- **Creator (God).** Produces new agents. All-knowing at decision time, all-obsessing, no utility gate, every domain is in scope for Creator's purpose.
- **Evolution (Darwin).** Maintains the population-level history. Observes outcomes; applies selection pressure.
- **Bonding (matchmaking / hiring / genetic / teambuilding / luck).** Produces relationships between agents.

## Why meta-components are not obsess agents

An obsess agent is defined by its specificity: a bounded frame, utility-gated attention, frame-shifted re-synthesis at retrieval, trauma as protection against a self-narrative that rewrites the past. Those properties are load-bearing for what Tier-1 agents are *for*: modeling a specific mind.

Meta-components have none of those constraints.

- **No bounded attention.** Creator is all-obsessing; the utility gate is always open. A gate that is always open is equivalent to no gate. Implementing one would be dead code.
- **No frame.** Meta-components do not have a perspectival view of the system; they have a god's-eye view (Creator), a population view (Evolution), or a graph view (Bonding). Without a frame, there is no encode-through-frame step, and therefore no impression primitive to form.
- **No trauma surprise.** Trauma encoding fires on `surprise × cost × unsolvability-at-time`. A Creator that is all-knowing at inspection time has no surprise. What it has instead is *model-reality contradiction*: cases where its model said X and reality said not-X. That is policy-shaped learning, not trauma.

Forcing trauma/impression/frame machinery onto meta-components would produce code that stubs out half the semantics. That hides the fact that these are genuinely different kinds of things.

## Evolution owns the meta-layer's memory

All population-level history lives in a single store owned by **Evolution**. This is a deliberate single-responsibility choice: Evolution is the memory of the system's history. Creator and Bonding do not keep parallel stores; they are read-mostly consumers that query Evolution's store when they need to consult it.

The store is append-only. Event categories:

- **Agent events.** Spawn, retire, major parameter changes.
- **Outcomes.** Failures, successes, milestones. Failures carry the proximate config, what the agent was when it failed.
- **Relationship events.** Formation, dissolution, strength changes.
- **Selection decisions.** Evolution's own actions: which agents were retired, which configs were rewarded, what selection pressure was applied when.

When Creator wants to check "has this config pattern failed before," it queries Evolution's store. When Bonding wants to check "how have pairings of this kind fared," it queries Evolution's store. The failure-registry concept Creator consults is a *view* over Evolution's store, not a separate table.

*Why not a shared store.* Multiple writers with no owner means no consistency guarantees, no clear decay/pruning policy, and schema drift. Evolution owning it centralizes those concerns in the component whose job already *is* to remember.

*Why not per-component private stores.* The same event (an agent failure) is relevant to all three meta-components. Three components observing it independently produces duplication that will drift out of sync. One record, queried from multiple places, is cleaner.

## Creator

**Job.** Produce new agents. Decide initial obsessions, commitment levels, starting relationships (in coordination with Bonding), and any parameters the architecture exposes (decay rates, alignment thresholds).

**Memory.** None of its own. At decision time, queries Evolution's store for past failures whose config signature matches the proposed config. The match returns a **failure-registry view**, a structurally simpler concept than trauma:

- **No render layer.** Creator has no frame.
- **No surprise score.** Matches are similarity-weighted pattern matches against prior failure configs, not `surprise × cost` encodings.
- **No self-narrative protection.** Creator is not at risk of rewriting its own history; it has no narrating self.

A failure-registry entry: `{ config_signature, failure_description, mitigation_if_known, outcome_of_mitigation }`. Creator consults these as anti-patterns, configs to avoid producing again unless the proposal includes a mitigation that addresses the prior failure.

**Decision shape.** Given a purpose/task context: propose an agent config, check against failure-registry, adjust or refuse if match, commit the agent. Post-commit, Creator records the spawn event to Evolution's store. The agent is then alive in Tier 1.

**Creator's bootstrapping.** Creator itself is exogenous, configured by the system builder, not produced by another component. A Creator-lineage (later Creators produced by earlier ones under Evolution's selection) is a possible future extension but is not part of this design.

## Evolution

**Job.** Two distinct jobs on two different timescales.

1. **Observation (event-triggered, synchronous).** Record every meaningful Tier-1 event into Evolution's store. Runs on every event-of-interest, failures, successes, spawns, retirements, relationship changes. Zero selection happens here; it is pure recording.

2. **Selection (periodic, cadence-based).** On a cadence independent of Tier-1 events, Evolution reads its own store, compares populations, identifies agents to retire, identifies configs to reward, adjusts selection pressure.

The two jobs are distinct operations with distinct timing because *noticing what happened* and *selecting based on accumulated history* operate on different timescales in biology and should here too. Observation cannot afford to miss events; selection cannot afford to be reactive to every event.

**What selection does.** Produces decisions: retire agent X (a Tier-1 event), promote config Y (weights Creator's future proposals toward Y), adjust relationship-formation priors (influences Bonding). Selection does *not* directly modify a running agent's memory.

**Why not modify running agents.** Reaching into a live agent's impression store or trauma records from outside is a migration problem with no clean semantics. A running agent's memory is coherent *to that agent*, external rewriting breaks that coherence. Evolution influences descendants and the population, not a live agent's internal state.

## Bonding

**Job.** Produce relationships between agents. Consumes Creator's output (new agents) and Evolution's history (past pairing outcomes); produces edges in the relationship graph defined in `DESIGN-MULTI.md`.

**Structure.** A core component with pluggable **strategies**. The core handles cross-cutting concerns: consulting Evolution's store, writing relationship-formation events back to Evolution, applying per-kind defaults from `DESIGN-MULTI.md`. Strategies are swappable:

- **Hiring.** Fit-based pairing, this agent needs a team member with compatible obsessions; find or propose one.
- **Genetic.** Lineage-based pairing, parent/child is structural and produced by Creator at spawn; Bonding records it and infers siblings from shared parentage.
- **Teambuilding.** Pool formation, Bonding declares a team and its initial members, producing a pool.
- **Luck.** Deliberately stochastic. Some agent pairings are chance. Luck is a first-class strategy, not an afterthought, the system should produce some non-optimal graph topology, because real-world relationships are not all fit-driven and modeling that honestly means making luck an explicit mechanism.

**Which component produces which relationship kind.**

| Relationship kind | Produced by | When |
|---|---|---|
| Parent / child | Creator | At spawn. The spawn itself is the relationship; Bonding records it. |
| Team | Bonding (teambuilding strategy) | When a team is declared. |
| Peer / colleague | Bonding (hiring or luck strategy) | When agents are paired for work proximity. |
| Master / prodigy | Human / higher-order policy, recorded by Bonding | Asserts a destiny claim, not Bonding's call to originate. |

Bonding does not originate master/prodigy. That relationship asserts an aspirational claim the system should not be making for itself at this stage. A human operator or privileged policy asserts it; Bonding records and applies it.

## Firing semantics

Meta-components are **event-triggered** and scope their work to the events they care about.

- **Creator** fires on *spawn requests*, from an operator, from a higher policy, or from Evolution (which may request a new agent as part of selection's output).
- **Bonding** fires on *relationship-creation requests*, from Creator (to establish parent/child and initial bonds at spawn), from Evolution (to adjust the graph), or from operators.
- **Evolution** fires two ways:
    - *Observation*, on every event-of-interest. Synchronous, fast, append-only write.
    - *Selection*, on a cadence independent of Tier-1 events. Reads Evolution's store, reasons over populations, produces selection decisions that become new events.

Tier-1 agents do not wait on Creator, Bonding, or Evolution's selection. They emit events; meta-components subscribe and respond asynchronously to the events they care about. The exception is Evolution's observation, which must not miss events, but observation is a cheap append, not a reasoning step.

## Implementation status (v0.1.0)

All three meta-components are built and tested:

- **`EvolutionStore`** in `obsess/evolution.py`: append-only event log, backed by any `Storage` backend, indexed on `kind` and `agent_id`. Every Tier-1 event-of-interest lands here automatically.
- **`Creator`** in `obsess/creator.py`: `propose(agent_id, obsessions, llm=None)` with `WARN` / `REFUSE` / `IGNORE` policy modes, structural (domain-overlap) failure-registry matching, emits `agent_proposed` / `agent_created` / `agent_refused` events.
- **`Selection`** in `obsess/selection.py`: `run()` reads the store, retires agents exceeding a failure threshold, promotes zero-failure configs, emits `agent_retired` and `config_promoted`. `Population.retired_ids` caches the retired set.
- **`Bonding`** in `obsess/bonding.py`: core-plus-strategies with `genetic`, `teambuild`, `hiring`, and `luck` (seeded RNG). Produces relationships via `Population.form_relationship`.

All three construct by default on `Population.new()` and are accessible as `pop.creator`, `pop.selection`, `pop.bonding`.

Still deferred:

- **Semantic failure-registry matching.** Creator currently matches on exact obsession-domain overlap. Embedding-based similarity (reusing the existing `Embedder`) is the natural upgrade.
- **LLM-driven fit scoring in `Bonding.hiring`.** Current hiring is structural (commitment threshold on a named domain).
- **Background scheduler for `Selection.run()`.** Selection cadence is manual; a long-running daemon would let cadence fire on its own.
- **Creator lineage.** Creator itself is exogenous; Creator-on-Creator production under Evolution's pressure is a future extension.
- **Enforcement of retirement.** Retirement is advisory: `Population.retired_ids` is populated but callers are not blocked from operating on retired agents.
