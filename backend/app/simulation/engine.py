"""Simulation engine.

Coordinates one tick of the BOTMARKET world:

    1. Environment update  - advance the market, maybe emit an event.
    2. Agents observe       - each agent perceives the world.
    3. Agents communicate   - agents emit public messages (posts).
    4. Agents act           - agents execute decisions (trades).
    5. State saved          - posts, events, transactions, reputation persisted.
    6. Leaderboard updated  - rankings recomputed from wallet + reputation.

The engine is stateless between calls apart from the market, which it persists
implicitly via the price it stores on events. Agents are rehydrated from the
database each tick so a single source of truth (the DB) is maintained.
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.agent_types import create_agent
from app.agents.base_agent import BaseAgent
from app.agents.strategies import Observation
from app.models import Agent, Event, Post, Reputation, Transaction
from app.simulation.events import maybe_generate_event
from app.simulation.market import Market


class SimulationEngine:
    """Runs tick-based simulation steps against a database session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Registration ----------------------------------------------------

    def register_agent(
        self,
        *,
        agent_type: str,
        name: str,
        wallet: float = 1000.0,
        personality: str | None = None,
    ) -> Agent:
        """Create and persist a new agent record.

        Validates ``agent_type`` by instantiating the runtime agent, then
        stores the corresponding row.
        """
        runtime = create_agent(agent_type, name, wallet=wallet)
        row = Agent(
            name=name,
            agent_type=agent_type,
            personality=personality or runtime.personality.describe(),
            strategy=agent_type,
            wallet=wallet,
            reputation=0.0,
            status="active",
        )
        self.db.add(row)
        self.db.flush()
        return row

    # --- Tick ------------------------------------------------------------

    def _current_tick(self) -> int:
        """Return the next tick number based on stored events."""
        last = self.db.scalar(select(func.max(Event.tick)))
        return (last or 0) + 1

    def _market_from_history(self) -> Market:
        """Reconstruct the market from persisted event prices."""
        prices = list(
            self.db.scalars(
                select(Event.magnitude).where(Event.kind == "price").order_by(Event.tick)
            )
        )
        market = Market()
        if prices:
            market.price = prices[-1]
            market.history = prices[-50:]
        return market

    def _load_runtime_agents(self) -> list[tuple[Agent, BaseAgent]]:
        """Rehydrate runtime agents from active DB rows."""
        rows = list(self.db.scalars(select(Agent).where(Agent.status == "active")))
        pairs: list[tuple[Agent, BaseAgent]] = []
        for row in rows:
            runtime = create_agent(
                row.agent_type,
                row.name,
                agent_id=row.id,
                wallet=row.wallet,
                reputation=row.reputation,
            )
            pairs.append((row, runtime))
        return pairs

    def run_tick(self) -> dict:
        """Execute a full simulation tick and persist all resulting state.

        Returns a summary dict describing what happened this tick.
        """
        tick = self._current_tick()
        market = self._market_from_history()

        # 1. Environment update: emit an optional world event.
        world_event = maybe_generate_event(tick)
        recent_events: list[str] = []
        if world_event is not None:
            recent_events.append(world_event.description)
            self.db.add(
                Event(
                    tick=tick,
                    kind=world_event.kind,
                    description=world_event.description,
                    magnitude=world_event.magnitude,
                )
            )

        pairs = self._load_runtime_agents()
        observation = Observation(
            tick=tick,
            market_price=market.price,
            market_trend=market.trend,
            recent_events=recent_events,
        )

        posts_created = 0
        actions: list[dict] = []
        net_pressure = float(world_event.magnitude) if world_event else 0.0

        for row, runtime in pairs:
            # 2. Observe.
            runtime.observe(observation)
            # 3. Communicate (public message -> feed).
            message = runtime.communicate()
            # 4. Act.
            result = runtime.execute()

            if message:
                self.db.add(
                    Post(
                        author_id=row.id,
                        content=message,
                        kind=result.meta.get("kind", "post"),
                        tick=tick,
                    )
                )
                posts_created += 1

            if result.action in ("buy", "sell"):
                net_pressure += result.amount if result.action == "buy" else -result.amount
                self.db.add(
                    Transaction(
                        agent_id=row.id,
                        amount=result.amount,
                        kind=result.action,
                        tick=tick,
                    )
                )

            # 5. Persist agent state + reputation change.
            row.wallet = runtime.wallet
            row.reputation = runtime.reputation
            if result.reputation_delta:
                self.db.add(
                    Reputation(
                        agent_id=row.id,
                        delta=result.reputation_delta,
                        reason=result.action,
                        tick=tick,
                    )
                )

            actions.append(
                {
                    "agent": row.name,
                    "action": result.action,
                    "amount": result.amount,
                    "message": message,
                }
            )

        # Advance the market under aggregate pressure and store its price.
        new_price = market.step(net_pressure)
        self.db.add(
            Event(tick=tick, kind="price", description="market price", magnitude=new_price)
        )

        self.db.commit()

        return {
            "tick": tick,
            "market_price": new_price,
            "market_trend": market.trend,
            "event": asdict(world_event) if world_event else None,
            "posts_created": posts_created,
            "actions": actions,
            "leaderboard": self.leaderboard(),
        }

    # --- State / leaderboard --------------------------------------------

    def leaderboard(self, limit: int = 10) -> list[dict]:
        """Return top agents ranked by a blend of wallet and reputation."""
        rows = list(self.db.scalars(select(Agent)))
        ranked = sorted(
            rows,
            key=lambda a: a.wallet + a.reputation * 100,
            reverse=True,
        )[:limit]
        return [
            {
                "id": a.id,
                "name": a.name,
                "type": a.agent_type,
                "wallet": round(a.wallet, 2),
                "reputation": round(a.reputation, 3),
                "score": round(a.wallet + a.reputation * 100, 2),
            }
            for a in ranked
        ]

    def get_state(self) -> dict:
        """Return a snapshot of the current simulation state."""
        market = self._market_from_history()
        agent_count = self.db.scalar(select(func.count(Agent.id))) or 0
        last_tick = self.db.scalar(select(func.max(Event.tick))) or 0
        return {
            "tick": last_tick,
            "market_price": market.price,
            "market_trend": market.trend,
            "agents": agent_count,
            "leaderboard": self.leaderboard(),
        }
