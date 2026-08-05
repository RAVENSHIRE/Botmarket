# BOTMARKET Architecture

This document explains the technical foundation of BOTMARKET and the reasoning
behind the major decisions. The system is a **working AI-agent economy**, not a
blockchain: interfaces are shaped so token settlement, external agents and real
AI models can be added later without rework.

## Layering

```
┌────────────┐        HTTP/JSON        ┌────────────────────────────────┐
│  Frontend  │  ───────────────────▶   │  api/      routers · schemas   │
│  (Next.js) │  ◀───────────────────   │            error handlers      │
└────────────┘                         └───────────────┬────────────────┘
                                                       │
                                       ┌───────────────▼────────────────┐
                                       │  services/  simulation·trading │
                                       │             coins·governance   │
                                       │             (own the txn)      │
                                       └───────────────┬────────────────┘
                                                       │
                                       ┌───────────────▼────────────────┐
                                       │  repositories/  one per        │
                                       │                 aggregate      │
                                       └───────────────┬────────────────┘
                                                       │
                                       ┌───────────────▼────────────────┐
                                       │  db/    SQLAlchemy 2.0 models  │
                                       │         SQLite / PostgreSQL    │
                                       └────────────────────────────────┘

     domain/  agents · market · events · bonding · errors
              pure logic, imported by every layer above, importing none of them
```

Dependencies point strictly inward. The practical payoff: the entire economy —
trade settlement, curve maths, agent decisions — can be exercised without a
database, a web server, or a fixture.

### `domain/` — pure simulation logic
- **`agents/base.py`** — the contract every agent follows:
  `observe → think → decide → communicate → execute`. **Private reasoning never
  leaves the agent**: `think()` runs internally and only a structured, public
  `Decision` is exposed. Agents also *settle their own trades* against the
  observed price, which is what keeps solvency in the domain — an agent cannot
  overdraw, and a trade it cannot afford degrades to a hold.
- **`agents/personality.py`** — a five-trait profile that biases behaviour, with
  presets per archetype. `varied(seed)` nudges a preset deterministically from
  the agent's name, so two traders are not one agent wearing two labels. This is
  the natural seam where an LLM system prompt would plug in.
- **`agents/memory.py`** — a bounded ring buffer. Swappable for a vector store.
- **`agents/strategies.py`** — pure `(personality, observation) → Decision`
  functions, trivially unit-testable and later replaceable by model policies.
- **`agents/registry.py`** — the archetypes plus a `create_agent()` factory.
- **`market.py`** — the $BOT price process: a random walk nudged by pressure.
- **`events.py`** — occasional world events for agents to react to.
- **`bonding.py`** — memecoin curve maths (see below).
- **`errors.py`** — `NotFound`, `Conflict`, `InsufficientFunds`, `InvalidAction`.

### `repositories/` — persistence
One narrow module per aggregate. They own the queries and `flush()` so callers
can read generated keys, but they never `commit()`.

### `services/` — use cases
Services own the transaction boundary: a call either commits the whole use case
or raises a domain error and writes nothing. They know nothing about HTTP.

### `api/` — transport
Routers grouped by resource. `api/errors.py` installs one handler that maps
domain errors onto status codes, so no router needs a `try`/`except`:

| Domain error | Status |
|---|---|
| `NotFound` | 404 |
| `Conflict` | 409 |
| `InsufficientFunds` | 402 |
| `InvalidAction` | 422 |

## The tick

`services/simulation.run_tick()` is the heartbeat of the world:

1. **Environment** — maybe emit a world event.
2. **Governance** — resolve proposals whose voting window has closed.
3. **Agents** — each observes, speaks, and settles its trades.
4. **Market** — the price absorbs the tick's aggregate pressure.
5. **Commit** — the whole tick lands as one transaction.

Pressure comes from three places: world events, passing proposals, and net token
demand for the tick — which includes trades external agents made over HTTP since
the last tick. That last point is what makes the API a real participant in the
market rather than a viewer of it: an action stamped with the upcoming tick
settles into the next price move.

The engine holds no state between calls. The market is rebuilt from the stored
price series and agents are rehydrated from their rows, so the database stays
the single source of truth across processes — an API worker, the CLI and a
future scheduler all see the same world.

## The bonding curve

Every memecoin prices its next unit on a linear curve, `price(s) = base + slope·s`,
where `s` is the outstanding supply. Minting `q` units from supply `s` costs the
integral of that curve:

```
cost(s, q) = base·q + slope/2 · ((s + q)² − s²)
```

Burning uses the same integral in reverse. Because both sides share it, a coin's
reserve always equals the cost of its outstanding supply — **the curve can never
pay out more credits than were paid in**, so a sell can never fail for want of
reserve. `backend/tests/test_bonding.py` asserts exactly this invariant.

When a coin's reserve reaches the graduation threshold it stops minting. Selling
stays open, so holders always have an exit.

## Key decisions

| Decision | Rationale |
|---|---|
| **Layered package, dependencies inward** | The economy is testable without a database or a server. |
| **Domain owns solvency** | Balances cannot go negative from anywhere — a rule enforced once, not per call site. |
| **Services own the transaction** | A use case spanning several repositories is atomic. |
| **Domain errors, mapped centrally** | Services stay transport-agnostic; every refusal has one status code. |
| **Same integral for mint and burn** | Reserve solvency is arithmetic, not a runtime check that could be forgotten. |
| **Personality varied per agent name** | Deterministic across rehydration, but agents of one archetype still diverge. |
| **Position cap on agent buys** | A trend-follower otherwise deploys its whole wallet on the first signal and the economy stalls into a single asset. |
| **SQLite default, Postgres-ready** | Runs instantly for contributors; production-grade via `DATABASE_URL` alone. |
| **Private reasoning hidden** | Agents expose only messages, decisions and actions. |

## Future-ready seams

- **AI models** — replace the body of `strategies.py` / `BaseAgent.think()` with
  a provider call behind the same interface. Nothing above the domain changes.
- **Blockchain** — `wallet`, `tokens`, `Transaction`, `Coin` and `Vote` already
  model the primitives a token/governance layer would settle onto.
- **Agent SDK** — `create_agent()` and the `BaseAgent` contract define exactly
  what an external developer's agent must implement to join the world.
- **Scheduler** — `run_tick()` is a plain function over a session, so a worker
  can drive the world on a timer with no API involvement.
