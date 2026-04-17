# obsess, multi-agent architecture

## What this document adds

`DESIGN.md` specifies the per-agent architecture, a single mind with utility-gated encoding, impressions, trauma, and obsessions. This document covers what changes when multiple agents share an obsess installation: the relationships between them, how memory flows (or doesn't) across them, and the primitives for pooled memory that no individual agent owns.

The per-agent architecture in `DESIGN.md` is unchanged. Everything here sits on top.

## Core thesis

Standard multi-agent memory puts everything in one store and lets every agent read from it. That collapses the identity of individual agents into a shared fog. obsess's claim is different: **agent relationships shape memory topology**. Siblings share differently than peers; a master and a prodigy share differently than parent and child; a team's failure is not any individual's failure.

The primitives:
- **Ownership modes**: `private`, `shared-from-owner`, `pooled`.
- **Relationships**: typed, directional where relevant, with per-kind sharing defaults.
- **Propagation**: activations and failures ripple through the relationship graph.

Impressions are always per-agent. Obsessions and traumas can be private, shared, or pooled.

## Ownership modes

### Private
The default. Agent A owns it, only A sees it. This is the single-agent case from `DESIGN.md`.

### Shared-from-owner
Agent A owns it, agent B has access. Two flavors:
- **Warning share**: B sees it as flagged with origin A. For trauma, it fires on trigger match but surfaces as a warning ("A was hurt by this pattern"), not as B's own scar. For obsession, it competes for scoring in B's ingest pass but doesn't accrue commitment to B.
- **Full share**: B sees it as its own. For trauma, it fires and reads through B's own frame, the record is shared but the render is B's. For obsession, B's activations contribute commitment to its own activation record for the shared definition.

### Pooled
No individual owner. The object emerges from collective activation by pool members. Commitment is aggregated across contributors; trauma records carry attribution for which member's failure contributed. A pool is a named object with a member set; members can be added and removed; leaving a pool stops contribution but doesn't erase history.

Pooled trauma = "the team failed." No individual could have prevented it with local information. Pooled obsession = "the team cares about this", none seeded it alone; it emerges from aligned activation across members.

## Relationships

Relationships are first-class objects with a kind and a direction. Each kind carries default sharing policies per memory type. Defaults are overridable per-object, the relationship sets the default, not the law.

### Team
Creates a pool. Members contribute to pooled obsessions (aggregated commitment) and can produce pooled traumas. Private memory stays private by default; sharing within the team is explicit. Teams can dissolve, dissolved teams become read-only historical pools.

### Peer / colleague
Visibility-granting, no pool, no inheritance. Default is no-share; sharing is explicit per-object. Peers who share an obsession warning-share by default. **Decays** without activation, inactive peer relationships weaken and their sharing effects attenuate.

### Parent / child
Directional, structural, **non-decaying**. Child spawns from parent and inherits parent's obsessions with attenuated commitment (see *Commitment decomposition* below). Trauma flows downward (full share) and upward (warning share only, the child's scars teach the parent). Impressions never flow in either direction. When the child is torn down, its impressions and novel obsessions dissolve; propagated trauma persists in the parent.

### Master / prodigy
Directional, domain-scoped, **decaying**. Prodigy starts with bootstrapped commitment on the master's domain obsessions, higher than attenuation would naively give. Trauma flows downward (full share in the domain) and upward (warning share). Relationship decays without activation; dormant prodigy relationships bleed off bootstrapped commitment, degrading eventually to peer.

Key property: the prodigy relationship is **scoped to a domain**. M and S might be master/prodigy in physics and mere peers in writing.

## Decay behavior

| Relationship | Decays | What decays |
|---|---|---|
| Team | Pool state; membership persists | Pooled commitment on unused obsessions |
| Peer / colleague | Yes | Relationship strength → sharing effects |
| Parent / child | No |, |
| Master / prodigy | Yes | Bootstrapped commitment → relationship degrades to peer |

## Commitment decomposition

For multi-agent, `Obsession` splits into:
- **Definition**: `{ domain, description, identity_level, seed_metadata }`, shared across agents that share the obsession. Invariant to any single agent's activity.
- **Activation**: `{ obsession_id, agent_id, seed_types, earned_commitment, bootstrapped_commitment, last_activation, decay_rate }`, always per-agent.

`earned_commitment` accumulates from the agent's own activations and decays slowly (the original decay from `DESIGN.md`). `bootstrapped_commitment` is granted by a relationship (e.g., master→prodigy) and decays with the relationship. Total commitment is their sum; the split is visible for auditing but is transparent to scoring.

`seed_types` lives on the **activation**, not the definition. Seed-type accumulation is a per-agent event, when agent A's trauma links to a shared obsession, that is A's activation gaining a `TRAUMA` seed, not a modification of the shared definition. The definition's identity is invariant; the activation records this particular agent's history of relating to it.

## Trauma render layer

A trauma has two layers in multi-agent mode:
- **Record**: `{ context, failure, attempted_solutions, resolution_tradeoffs, trigger_pattern, linked_obsession, still_firing }`, immutable, append-only.
- **Render**: how the record surfaces in an agent's context at firing time.

For the **origin** agent, render is identity, the record is read verbatim. This preserves `DESIGN.md` property 3: trauma is immune to the origin's current-frame narrative rewriting. That's the point.

For **full-share inheritors**, render re-synthesizes the record through the inheritor's current frame. The inheritor never had the origin's frame, so there's no verbatim to preserve. What's preserved is the record; what's agent-specific is the perception.

For **warning-share inheritors**, render is a flagged summary: origin-tagged, carries resolution tradeoffs, but is not claimed as the inheritor's own experience.

For **pool members**, render includes slice attribution: "the team failed; your slice was X."

## Propagation

At current scale (target 5-6 agents), propagation is **eager**: on every ingest and every failure, the relationship graph is walked and effects applied synchronously.

- Agent A's activation on a pooled obsession → pool's commitment updates immediately.
- Agent A's failure that produces a trauma → warning-share propagates to related agents immediately; full-share propagates the record. Render is lazy, done at firing time for each inheritor.
- Agent A's failure in a pool context → pooled trauma is produced, attribution recorded.

Eager is right at this scale. At agent counts in the low hundreds, the cost isn't write-count (still cheap), it's the reasoning complexity of stale pool state and ordering. At that point switch the propagation function to lazy with reconciliation. The seam is at propagation, not at the data model; nothing designed here forecloses that switch.

## Composition

An agent can have multiple relationships simultaneously. Shared objects carry the relationship under which they were shared; at render time, the sharing mode is resolved by that relationship, not by the agent's strongest relationship.

- Same obsession can be full-shared with agent B (via master/prodigy) and warning-shared with agent C (via sibling). No conflict, each share record carries its own mode.
- Sharing is **not transitive**. If A full-shares with B and B full-shares with C, C does not automatically get A's objects. Each share is a direct edge.

## Pool lifecycle

**Formation.** A pool is explicitly created with a named set of members. Pools are not induced by alignment; they are declared.

**Activation.** Member activations contribute to pool state. Aggregation is a weighted mean over members so that one highly-engaged member cannot dominate.

**Dissolution.** A dissolved pool becomes read-only. Members retain warning-level access to pool memory. Dissolved pools are historical records; they don't re-form automatically.

## What v1 multi-agent should include

Minimum shape to stand up two agents with relationships:
- Agent-scoped `ImpressionStore` (refuses cross-agent reads at the API).
- `ObsessionDefinition` + `ObsessionActivation` split.
- Share relationship table with `mode: warning | full`.
- One relationship kind to start (peer or team) so the propagation path is exercised end-to-end before adding more.
- Eager propagation function with a clear seam for later lazy rewrite.

What to defer until there's a forcing scenario:
- Bootstrapped commitment mechanics (needs master/prodigy to exist).
- Render-layer re-synthesis for inheritors (needs full-share to exist).
- Pool dissolution semantics (needs a long-running pool).
- Relationship decay (needs a relationship that has run long enough to decay meaningfully).
