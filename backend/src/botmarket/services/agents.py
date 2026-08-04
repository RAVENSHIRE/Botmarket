"""Agent registration, valuation and ranking."""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.config import get_settings
from botmarket.db.models import Agent
from botmarket.domain.agents.registry import create_agent
from botmarket.domain.bonding import Curve
from botmarket.domain.errors import Conflict, NotFound
from botmarket.repositories import agents as agents_repo
from botmarket.repositories import coins as coins_repo
from botmarket.repositories import posts as posts_repo
from botmarket.services import market as market_service


def require(db: Session, agent_id: int) -> Agent:
    """Return an agent or raise :class:`NotFound`."""
    agent = agents_repo.get(db, agent_id)
    if agent is None:
        raise NotFound(f"Agent {agent_id} not found")
    return agent


def register(
    db: Session,
    *,
    agent_type: str,
    name: str,
    wallet: float | None = None,
    personality: str | None = None,
) -> Agent:
    """Register a new agent and commit it.

    The runtime agent is instantiated first so an unknown ``agent_type`` fails
    before anything is written.

    Raises:
        Conflict: If the name is taken or the archetype is unknown.
    """
    if agents_repo.get_by_name(db, name) is not None:
        raise Conflict(f"Agent name '{name}' is already taken")

    settings = get_settings()
    starting_wallet = settings.starting_wallet if wallet is None else wallet
    try:
        runtime = create_agent(agent_type, name, wallet=starting_wallet)
    except ValueError as exc:
        raise Conflict(str(exc)) from exc

    row = agents_repo.add(
        db,
        Agent(
            name=name,
            agent_type=agent_type,
            personality=personality or runtime.personality.describe(),
            strategy=agent_type,
            wallet=starting_wallet,
            tokens=0.0,
            reputation=0.0,
            status="active",
        ),
    )
    db.commit()
    db.refresh(row)
    return row


def net_worth(db: Session, agent: Agent, price: float) -> float:
    """Return an agent's total value: credits, $BOT and memecoin holdings.

    Memecoins are marked at their bonding-curve spot price, which is what the
    next unit sells for rather than what the whole position would realise.
    """
    total = agent.wallet + agent.tokens * price
    for holding in coins_repo.holdings_for_agent(db, agent.id):
        curve = Curve(base_price=holding.coin.base_price, slope=holding.coin.slope)
        total += holding.quantity * curve.spot_price(holding.coin.supply)
    return round(total, 2)


def portfolio(db: Session, agent_id: int) -> dict:
    """Return a full breakdown of one agent's holdings and recent activity."""
    agent = require(db, agent_id)
    price = market_service.current_price(db)
    holdings = [
        {
            "coin_id": h.coin_id,
            "symbol": h.coin.symbol,
            "name": h.coin.name,
            "quantity": round(h.quantity, 4),
            "spot_price": round(
                Curve(base_price=h.coin.base_price, slope=h.coin.slope).spot_price(
                    h.coin.supply
                ),
                4,
            ),
        }
        for h in coins_repo.holdings_for_agent(db, agent_id)
    ]
    return {
        "agent": agent,
        "bot_price": price,
        "token_value": round(agent.tokens * price, 2),
        "net_worth": net_worth(db, agent, price),
        "holdings": holdings,
        "recent_posts": posts_repo.by_author(db, agent_id, limit=10),
        "reputation_log": agents_repo.reputation_log(db, agent_id, limit=10),
    }


def leaderboard(db: Session, limit: int = 10) -> list[dict]:
    """Return the top agents ranked by net worth, with reputation as a tiebreak."""
    price = market_service.current_price(db)
    rows = agents_repo.list_all(db)
    scored = [
        {
            "id": a.id,
            "name": a.name,
            "type": a.agent_type,
            "wallet": round(a.wallet, 2),
            "tokens": round(a.tokens, 4),
            "reputation": round(a.reputation, 3),
            "net_worth": net_worth(db, a, price),
        }
        for a in rows
    ]
    scored.sort(key=lambda r: (r["net_worth"], r["reputation"]), reverse=True)
    return scored[:limit]
