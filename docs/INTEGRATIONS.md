# Integrating obsess with agent frameworks

obsess is framework-neutral, it owns memory state, your framework owns the reasoning loop. This doc shows how to plug obsess into common setups.

The core pattern is a **sandwich** around each LLM call:

```
observation ──▶ agent.ingest(observation) ──▶ trauma_warnings
                                                    │
                                                    ▼
                    framework_prompt ◀────── augment prompt with warnings
                                                    │
                                                    ▼
                                             framework.chat(prompt)
                                                    │
                                                    ▼
                    agent.record_failure(...) ◀── if failure detected
```

obsess does not wrap or replace your agent framework. It runs alongside.

---

## Framework-neutral pattern

```python
from obsess import Population
from obsess.types import SeedType

pop = Population.new()
agent = pop.spawn("my_bot")

agent.seed_obsession(
    domain="customer_service",
    description="resolve customer issues quickly without escalation",
    seed_types=[SeedType.NEED_FOR_SUCCESS],
    commitment=0.8,
)

def reason(user_message: str) -> str:
    # 1. Feed the observation to obsess. This updates the agent's state and
    #    returns any trauma warnings that fire in this context.
    ingest = agent.ingest(user_message)
    warnings = [st.rendered_text for st in ingest.trauma_warnings]

    # 2. Augment the prompt with obsess's memory output.
    memory_context = ""
    if warnings:
        memory_context += "Past failure warnings:\n" + "\n".join(f"- {w}" for w in warnings)
    prior = agent.query(user_message)
    if prior.impressions_used:
        memory_context += f"\nPrior context: {prior.answer}"

    prompt = f"{memory_context}\n\nUser: {user_message}" if memory_context else user_message

    # 3. Run your framework's reasoning, this is up to you.
    answer = your_framework.chat(prompt)

    # 4. If the framework's outcome was a failure, record it so future
    #    similar contexts trigger the warning.
    if looked_like_a_failure(answer):
        agent.record_failure(
            context=user_message,
            failure=answer,
            attempted_solutions=["single-shot response"],
            cost="user dissatisfaction",
            unsolvable_at_time=True,
        )

    return answer
```

---

## LangChain

Wrap your existing LangChain chain/agent with obsess ingest/record_failure hooks. obsess state lives next to, not inside, the LangChain chain.

```python
from obsess import Population
from obsess.types import SeedType
from langchain_core.messages import HumanMessage
from langchain_anthropic import ChatAnthropic

pop = Population.new()
agent = pop.spawn("support_bot")
agent.seed_obsession(
    domain="billing_support",
    description="resolve billing issues escalation refund",
    seed_types=[SeedType.NEED_FOR_SUCCESS],
    commitment=0.8,
)

llm = ChatAnthropic(model="claude-sonnet-4-6")

def chat(user_message: str) -> str:
    ingest = agent.ingest(user_message)
    warnings_text = "\n".join(
        f"WARNING from past: {st.rendered_text}"
        for st in ingest.trauma_warnings
    )
    prompt = f"{warnings_text}\n\n{user_message}" if warnings_text else user_message

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content
```

For multi-agent LangChain setups (e.g., LangGraph), give each node its own `Memory` via `pop.spawn(agent_id)`; form relationships between them so trauma/obsession share as you want:

```python
pop.form_relationship(RelationshipKind.TEAM, "node_a", "node_b")
```

Failures in one node's execution propagate as warnings to related nodes on subsequent runs.

---

## Claude Agent SDK

Give each Claude-Code-style subagent a dedicated obsess `Memory`. Hook obsess into the SDK's lifecycle: ingest the incoming task, query for relevant past work, record failure on tool errors.

```python
from anthropic import Anthropic
from obsess import Population
from obsess.types import SeedType

client = Anthropic()
pop = Population.new()

def make_agent(agent_id: str, domain: str, description: str):
    pop.spawn(agent_id).seed_obsession(
        domain=domain,
        description=description,
        seed_types=[SeedType.NEED_FOR_SUCCESS],
        commitment=0.8,
    )
    return pop.get_agent(agent_id)

code_reviewer = make_agent("reviewer", "code_review", "find bugs security issues style")
test_writer = make_agent("tester", "test_coverage", "unit integration tests edge cases")

# Peer relationship, they work alongside but don't inherit each other's obsessions.
# Warning-share trauma would require explicit sharing (peer default is NONE).
from obsess.relationships import RelationshipKind
pop.form_relationship(RelationshipKind.PEER, "reviewer", "tester")

def run_reviewer(task: str) -> str:
    ingest = code_reviewer.ingest(task)
    memory_bits = [st.rendered_text for st in ingest.trauma_warnings]

    system = "You are a code reviewer."
    if memory_bits:
        system += "\n\nPrior warnings:\n" + "\n".join(memory_bits)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        system=system,
        messages=[{"role": "user", "content": task}],
        max_tokens=2048,
    )
    return response.content[0].text
```

---

## Raw tool-loop agents

If you roll your own agent loop, the sandwich pattern is the same. Tool-call failures are a natural signal for `record_failure`:

```python
while not done:
    observation = get_observation()
    ingest = agent.ingest(observation)

    tool_call = decide_next_action(
        observation,
        warnings=[st.rendered_text for st in ingest.trauma_warnings],
    )

    try:
        result = execute(tool_call)
    except ToolError as e:
        agent.record_failure(
            context=observation,
            failure=str(e),
            attempted_solutions=[tool_call.name],
            cost="tool error; retry or escalate",
            unsolvable_at_time=True,
        )
        continue

    if is_successful(result):
        done = True
```

---

## Persistence patterns

For a long-running agent (chatbot, assistant, coding agent), back obsess with SQLite so state survives restart:

```python
from obsess.storage.sqlite import SQLiteStorage

pop = Population.new(storage=SQLiteStorage("~/.my_app/obsess.db"))

# On first run:
agent = pop.spawn("assistant")

# On subsequent runs:
if "assistant" in pop.agent_ids_on_record():
    agent = pop.rehydrate_agent("assistant")
else:
    agent = pop.spawn("assistant")
```

`Population.close()` when done to flush pending writes.

---

## Observing what's happening

Everything that happens at the meta layer fires an event into `EvolutionStore`. This is your instrumentation hook:

```python
for ev in pop.evolution.query(kind="failure_recorded"):
    print(ev.agent_id, ev.payload)

# Per-agent event stream
for ev in pop.evolution.query(agent_id="assistant"):
    print(ev.kind, ev.payload)
```

Event kinds: `spawn`, `agent_proposed`, `agent_created`, `agent_refused`, `agent_retired`, `shared_obsession_defined`, `shared_obsession_activated`, `obsession_propagated`, `failure_recorded`, `trauma_resolved`, `trauma_fired`, `trauma_shared`, `relationship_formed`, `pool_formed`, `pool_member_added`, `pool_member_removed`, `config_promoted`.

---

## When to reach for which primitive

| Situation | Primitive |
|---|---|
| Give an agent its own memory | `Population.spawn(agent_id)` |
| Share a priority across agents | `pop.shared_obsessions.define(...)` → each agent `activate_shared_obsession(...)` |
| Model mentorship: inheritor bootstraps from mentor | `RelationshipKind.MASTER_PRODIGY` |
| Model a task-subordinate that inherits attenuated | `RelationshipKind.PARENT_CHILD` |
| Two independent agents that should warn each other | `RelationshipKind.PEER` with explicit warning-share |
| A team whose collective failures must propagate to everyone | `pop.bonding.teambuild(...)`, creates a pool |
| An LLM-provider-agnostic agent | `ProviderSemantics(AnyProvider)`, same obsess code either way |
| State that survives restart | `SQLiteStorage("path.db")` + `rehydrate_agent` |
