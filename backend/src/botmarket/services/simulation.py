"""Simulation engine.

Coordinates one tick of the BOTMARKET world:

    1. Environment update  - emit an optional world event.
    2. Governance          - resolve proposals whose voting window has closed.
    3. Agents observe      - each agent perceives the world.
    4. Agents communicate  - agents emit public messages (posts).
    5. Agents act          - agents settle trades against the price.
    6. Market moves        - aggregate pressure nudges the price; it is stored.
    7. State saved         - the whole tick commits as one transaction.

The engine holds no state between calls. The market is rebuilt from the stored
price series and agents are rehydrated from their rows each tick, so the
database stays the single source of truth even across processes.

Pressure on the price comes from three places: world events, passing
proposals, and net token demand for the tick — which includes trades that
external agents made over HTTP since the last tick.
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from botmarket.config import Settings, get_settings
from botmarket.db.models import Agent
from botmarket.domain.agents.base import BaseAgent
from botmarket.domain.agents.registry import create_agent
from botmarket.domain.agents.strategies import Observation
from botmarket.domain.events import maybe_generate_event
from botmarket.repositories import agents as agents_repo
from botmarket.repositories import events as events_repo
from botmarket.repositories import posts as posts_repo
from botmarket.repositories import transactions as tx_repo
from botmarket.services import agents as agents_service
from botmarket.services import governance as governance_service
from botmarket.services import market as market_service


def run_tick(db: Session) -> dict:
    """Advance the world one tick and commit everything it produced.

    Returns:
        A summary of the tick: the new price, the event that fired, what each
        agent did, any proposals resolved, and the refreshed leaderboard.
    """
    settings = get_settings()
    tick = market_service.next_tick(db)
    market = market_service.load(db)

    # 1. Environment: an occasional world event that agents react to.
    world_event = maybe_generate_event(tick)
    recent_events: list[str] = []
    pressure = 0.0
    if world_event is not None:
        recent_events.append(world_event.description)
        pressure += world_event.magnitude
        events_repo.add(
            db,
            tick=tick,
            kind=world_event.kind,
            description=world_event.description,
            magnitude=world_event.magnitude,
        )

    # 2. Governance: proposals that closed take effect now.
    resolved = governance_service.resolve_due(db, tick)
    for outcome in resolved:
        pressure += outcome["pressure"]
        if outcome["status"] == "passed":
            recent_events.append(f"Proposal passed: {outcome['title']}")

    # 3-5. Agents observe, speak and act.
    observation = Observation(
        tick=tick,
        market_price=market.price,
        market_trend=market.trend,
        recent_events=recent_events,
    )
    actions, posts_created, agent_pressure = _run_agents(db, observation, tick, settings)
    pressure += agent_pressure

    # External agents trading over HTTP stamped their volume onto this tick.
    pressure += tx_repo.net_market_pressure(db, tick)

    # 6. The market absorbs the tick's aggregate pressure.
    new_price = market.step(pressure)
    events_repo.add(
        db, tick=tick, kind="price", description="market close", magnitude=new_price
    )

    # 7. One transaction for the whole tick.
    db.commit()

    return {
        "tick": tick,
        "market_price": new_price,
        "market_trend": market.trend,
        "pressure": round(pressure, 4),
        "event": asdict(world_event) if world_event else None,
        "posts_created": posts_created,
        "actions": actions,
        "proposals_resolved": resolved,
        "leaderboard": agents_service.leaderboard(db),
    }


def state(db: Session) -> dict:
    """Return a snapshot of the current world, without advancing it."""
    market = market_service.load(db)
    return {
        "tick": market_service.current_tick(db),
        "market_price": market.price,
        "market_trend": market.trend,
        "price_history": market.history[-60:],
        "agents": agents_repo.count(db),
        "leaderboard": agents_service.leaderboard(db),
        "recent_events": [
            {"tick": e.tick, "kind": e.kind, "description": e.description}
            for e in events_repo.recent(db, limit=8)
        ],
    }


# --- Internals -----------------------------------------------------------


def _run_agents(
    db: Session, observation: Observation, tick: int, settings: Settings
) -> tuple[list[dict], int, float]:
    """Step every active agent and persist what it produced.

    Returns:
        ``(actions, posts_created, pressure)`` where pressure is net token
        demand generated by the agents this tick.
    """
    actions: list[dict] = []
    posts_created = 0
    pressure = 0.0

    for row, runtime in _load_runtime_agents(db, settings.trade_fee_rate):
        runtime.observe(observation)
        message = runtime.communicate()
        result = runtime.execute()

        if message:
            posts_repo.add(
                db,
                author_id=row.id,
                content=message,
                kind=result.meta.get("kind", "post"),
                tick=tick,
            )
            posts_created += 1

        if result.action in ("buy", "sell"):
            pressure += result.quantity if result.action == "buy" else -result.quantity
            tx_repo.add(
                db,
                agent_id=row.id,
                kind=result.action,
                amount=result.credits,
                quantity=result.quantity,
                tick=tick,
            )

        # The runtime agent is authoritative for balances it just settled.
        row.wallet = runtime.wallet
        row.tokens = runtime.tokens
        if result.reputation_delta:
            agents_repo.record_reputation(
                db,
                agent_id=row.id,
                delta=result.reputation_delta,
                reason=result.action,
                tick=tick,
            )

        actions.append(
            {
                "agent": row.name,
                "action": result.action,
                "quantity": round(result.quantity, 4),
                "credits": round(result.credits, 2),
                "message": message,
            }
        )

    return actions, posts_created, pressure


def _load_runtime_agents(db: Session, fee_rate: float) -> list[tuple[Agent, BaseAgent]]:
    """Rehydrate runtime agents from their active rows."""
    pairs: list[tuple[Agent, BaseAgent]] = []
    for row in agents_repo.list_active(db):
        runtime = create_agent(
            row.agent_type,
            row.name,
            agent_id=row.id,
            wallet=row.wallet,
            tokens=row.tokens,
            reputation=row.reputation,
            fee_rate=fee_rate,
        )
        pairs.append((row, runtime))
    return pairs
