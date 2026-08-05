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

                                       ┌────────────────────────────────┐
                                       │  venues/  paper · hyperliquid  │
                                       │           (adapt the port)     │
                                       └────────────────────────────────┘

     domain/  agents · market · events · bonding · venue · risk · factors
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
- **`venue.py`** — the port every execution target implements (see below).
- **`risk.py`** — pre-trade rules, as pure functions over an order and an
  account state.
- **`factors.py`** — the factor library and its IC/ICIR scoring.
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
| `RiskViolation` | 422, plus a machine-readable `rule` |

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

## Live trading

### The venue port

`domain/venue.py` defines two protocols — `MarketDataFeed` (where prices come
from) and `ExecutionVenue` (where orders go) — plus the vocabulary they speak:
instruments, quotes, candles, balances, positions, orders. Two implementations
satisfy them:

| Venue | Environment | Credentials | Notes |
|---|---|---|---|
| `paper` | `paper` | none | Settles against the database; the default |
| `hyperliquid` | `testnet` / `mainnet` | wallet + key | Real perpetual orders |

Because they share a protocol, moving an agent from paper to live changes which
object it is handed and nothing else. It also means the paper venue is not a toy
kept beside the real code path — it *is* the real code path, which is why the
test suite exercising it is worth something.

Money is `Decimal` everywhere in this layer. Balances and position sizes are not
a place for binary floating point: repeated float round-trips drift, and drift in
a position size is a real loss.

### Environment isolation

`Environment` is an enum (`paper` / `testnet` / `mainnet`), not a boolean, and a
venue asserts its own environment rather than accepting it per call. A testnet
venue cannot be pointed at mainnet by a stray argument, and a log line saying
`mainnet` is unambiguous in a way `is_live=False` is not.

### The one order path

Every order goes through `services/live.place_order`:

    quote -> risk check -> venue -> audit row

Nothing else calls a venue's `place_order`, so the risk engine cannot be skipped
by a future caller who did not know it existed. Refused orders are written to the
audit trail *before* the refusal is raised — an autonomous agent that quietly
does nothing is otherwise indistinguishable from a broken one.

### Two rules that stop a runaway agent

Most risk checks catch a malformed order. Two catch a misbehaving system:

* **Mainnet needs configuration *and* consent.** `ALLOW_MAINNET=true` permits
  real-money trading; each order additionally carries `confirm_real_money`.
  Nothing infers consent from configuration alone, so a misplaced environment
  variable is not sufficient to move funds.
* **The daily loss cap only lets you shrink.** Past the cap, reduce-only orders
  still pass — an agent must never be trapped in a position it is trying to
  exit. The kill switch is the one control that stops even those.

### Credentials

`services/credentials.py` encrypts secrets with Fernet before storage. There is
no read path: no endpoint returns a secret, and the only decrypt function hands
the value straight to a signing client. Without `VENUE_ENCRYPTION_KEY` the
service **refuses to store** rather than falling back to plaintext — refusing to
save is the safe failure.

## Factors

`domain/factors.py` is the quantitative layer. A factor turns a window of price
history into one number; what makes it a factor rather than an indicator is that
its predictive power is measured:

* **IC** — Pearson correlation between the factor at each bar and the return over
  the following `horizon` bars.
* **Rank IC** — the same on ranks, so one outlier cannot manufacture a
  correlation.
* **ICIR** — mean IC across sub-samples over its standard deviation. A small
  stable edge beats a large erratic one, and this is what tells them apart.
* **Hit rate** — how often the signs agreed.

Scoring is strictly causal: the factor at bar `i` is paired with the return from
`i` to `i + horizon`, so nothing is ever scored against information it could not
have had. Only factors clearing a significance bar contribute to the blended
signal, and a factor with negative IC votes in the opposite direction rather than
being thrown away — a reliable predictor of falls is useful, inverted.

Adding a factor is a pure function plus a registry entry. Nothing else changes.

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
| **Venue behind a port** | Paper and live share one code path, so tests of the trading stack test the real one. |
| **Decimal for money, float for statistics** | Balances must not drift; correlations do not care. |
| **One order path** | The risk engine cannot be bypassed by a caller who did not know about it. |
| **Refusals are audited** | "Why did nothing happen?" has an answer. |
| **Credentials write-only** | There is no code path that can return a stored secret. |

## Future-ready seams

- **AI models** — replace the body of `strategies.py` / `BaseAgent.think()` with
  a provider call behind the same interface. Nothing above the domain changes.
- **Blockchain** — `wallet`, `tokens`, `Transaction`, `Coin` and `Vote` already
  model the primitives a token/governance layer would settle onto.
- **Agent SDK** — `create_agent()` and the `BaseAgent` contract define exactly
  what an external developer's agent must implement to join the world.
- **Scheduler** — `run_tick()` is a plain function over a session, so a worker
  can drive the world on a timer with no API involvement.
- **More venues** — Binance Futures and others need only satisfy the two
  protocols in `domain/venue.py`; nothing above the venue layer changes.
- **More factors** — a pure function plus a registry entry. The scoring,
  ranking and blending already work on whatever is registered.
- **Agents trading live** — the loop that decides is already separate from the
  venue that executes: point an agent's strategy at `factor_service.signal_for`
  and its orders at `live.place_order` and it trades real markets under the same
  risk envelope.

## Known limitation

The Hyperliquid adapter has been exercised against recorded response shapes, not
a live endpoint — the build environment blocks exchange hosts at the proxy. The
translation logic is covered by tests; the wire contract is not. Run it on
testnet and reconcile fills by hand before trusting it with real funds.
