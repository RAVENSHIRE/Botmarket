"""Memecoin service: launch, buy and sell against the bonding curve.

Persistence and economic rules for coins, layered on a SQLAlchemy ``Session``
(mirroring the style of ``app.social.posts``). All price math is delegated to
``app.economy.bonding_curve`` so this module only handles state transitions and
validation.

Trades are expressed in **token quantity**; the native-token cost/proceeds are
computed from the curve. Native token is the agent's ``wallet`` balance.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.economy import bonding_curve as bc
from app.models import Agent, Coin, CoinHolding, Transaction


def _get_coin(db: Session, coin_id: int) -> Coin:
    coin = db.get(Coin, coin_id)
    if coin is None:
        raise ValueError(f"Coin {coin_id} not found")
    return coin


def _get_agent(db: Session, agent_id: int) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"Agent {agent_id} not found")
    return agent


def _holding(db: Session, coin_id: int, agent_id: int) -> CoinHolding:
    """Return the agent's holding for a coin, creating a zero one if absent."""
    holding = db.scalar(
        select(CoinHolding).where(
            CoinHolding.coin_id == coin_id, CoinHolding.agent_id == agent_id
        )
    )
    if holding is None:
        holding = CoinHolding(coin_id=coin_id, agent_id=agent_id, balance=0.0)
        db.add(holding)
        db.flush()
    return holding


def _maybe_graduate(coin: Coin) -> None:
    """Flip status to graduated once the reserve crosses the threshold."""
    if coin.status == "active" and coin.reserve >= bc.GRADUATION_RESERVE:
        coin.status = "graduated"


def launch_coin(
    db: Session,
    *,
    creator_id: int,
    name: str,
    symbol: str,
    tick: int = 0,
    base_price: float = bc.DEFAULT_BASE_PRICE,
    slope: float = bc.DEFAULT_SLOPE,
    initial_buy: float = 0.0,
) -> Coin:
    """Create a new coin and optionally seed the creator's initial allocation.

    Raises:
        ValueError: if the creator is unknown, the symbol is taken, or the
            creator cannot afford ``initial_buy``.
    """
    _get_agent(db, creator_id)
    if db.scalar(select(Coin).where(Coin.symbol == symbol)):
        raise ValueError(f"Symbol '{symbol}' already exists")

    coin = Coin(
        name=name,
        symbol=symbol,
        creator_id=creator_id,
        base_price=base_price,
        slope=slope,
        tick=tick,
    )
    db.add(coin)
    db.flush()

    db.add(
        Transaction(
            agent_id=creator_id, amount=0.0, kind="coin_launch", coin_id=coin.id, tick=tick
        )
    )

    if initial_buy > 0:
        buy(db, coin_id=coin.id, agent_id=creator_id, qty=initial_buy, tick=tick)

    return coin


def buy(db: Session, *, coin_id: int, agent_id: int, qty: float, tick: int = 0) -> dict:
    """Buy ``qty`` tokens of a coin for the agent.

    Raises:
        ValueError: unknown coin/agent, non-positive qty, or insufficient wallet.
    """
    if qty <= 0:
        raise ValueError("qty must be positive")
    coin = _get_coin(db, coin_id)
    agent = _get_agent(db, agent_id)

    cost = bc.buy_cost(coin.base_price, coin.slope, coin.supply, qty)
    if cost > agent.wallet:
        raise ValueError(
            f"Insufficient funds: cost {cost:.2f} exceeds wallet {agent.wallet:.2f}"
        )

    agent.wallet -= cost
    coin.supply += qty
    coin.reserve += cost
    _maybe_graduate(coin)

    holding = _holding(db, coin_id, agent_id)
    holding.balance += qty

    db.add(
        Transaction(
            agent_id=agent_id, amount=cost, kind="coin_buy", coin_id=coin_id, tick=tick
        )
    )

    return {
        "coin_id": coin_id,
        "agent_id": agent_id,
        "qty": qty,
        "cost_or_proceeds": round(cost, 4),
        "new_spot_price": round(bc.spot_price(coin.base_price, coin.slope, coin.supply), 4),
        "wallet": round(agent.wallet, 4),
        "holding": round(holding.balance, 4),
        "status": coin.status,
    }


def sell(db: Session, *, coin_id: int, agent_id: int, qty: float, tick: int = 0) -> dict:
    """Sell ``qty`` tokens of a coin back to the curve.

    Raises:
        ValueError: unknown coin/agent, non-positive qty, or holding too small.
    """
    if qty <= 0:
        raise ValueError("qty must be positive")
    coin = _get_coin(db, coin_id)
    agent = _get_agent(db, agent_id)

    holding = _holding(db, coin_id, agent_id)
    if qty > holding.balance:
        raise ValueError(
            f"Insufficient holding: sell {qty} exceeds balance {holding.balance}"
        )

    proceeds = bc.sell_proceeds(coin.base_price, coin.slope, coin.supply, qty)
    agent.wallet += proceeds
    coin.supply -= qty
    coin.reserve = max(0.0, coin.reserve - proceeds)
    holding.balance -= qty

    db.add(
        Transaction(
            agent_id=agent_id, amount=proceeds, kind="coin_sell", coin_id=coin_id, tick=tick
        )
    )

    return {
        "coin_id": coin_id,
        "agent_id": agent_id,
        "qty": qty,
        "cost_or_proceeds": round(proceeds, 4),
        "new_spot_price": round(bc.spot_price(coin.base_price, coin.slope, coin.supply), 4),
        "wallet": round(agent.wallet, 4),
        "holding": round(holding.balance, 4),
        "status": coin.status,
    }


def _serialize(db: Session, coin: Coin) -> dict:
    """Enrich a coin row with computed price and market cap."""
    return {
        "id": coin.id,
        "name": coin.name,
        "symbol": coin.symbol,
        "creator_id": coin.creator_id,
        "creator_name": coin.creator.name if coin.creator else None,
        "supply": round(coin.supply, 4),
        "reserve": round(coin.reserve, 4),
        "base_price": coin.base_price,
        "slope": coin.slope,
        "spot_price": round(bc.spot_price(coin.base_price, coin.slope, coin.supply), 6),
        "market_cap": round(bc.market_cap(coin.base_price, coin.slope, coin.supply), 4),
        "status": coin.status,
        "tick": coin.tick,
    }


def list_coins(db: Session) -> list[dict]:
    """Return all coins, newest first, enriched with price/market cap."""
    coins = db.scalars(select(Coin).order_by(Coin.id.desc()))
    return [_serialize(db, c) for c in coins]


def get_coin(db: Session, coin_id: int) -> dict:
    """Return one coin enriched with price/market cap and top holders."""
    coin = _get_coin(db, coin_id)
    data = _serialize(db, coin)
    data["holders"] = top_holders(db, coin_id)
    return data


def top_holders(db: Session, coin_id: int, limit: int = 10) -> list[dict]:
    """Return the largest holders of a coin (balance descending)."""
    rows = db.scalars(
        select(CoinHolding)
        .where(CoinHolding.coin_id == coin_id, CoinHolding.balance > 0)
        .order_by(CoinHolding.balance.desc())
        .limit(limit)
    )
    return [
        {
            "agent_id": h.agent_id,
            "agent_name": h.agent.name if h.agent else None,
            "balance": round(h.balance, 4),
        }
        for h in rows
    ]
