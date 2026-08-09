"""Memecoin and holding persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from botmarket.db.models import Coin, CoinReply, Holding


def get(db: Session, coin_id: int) -> Coin | None:
    """Return a coin by id, or ``None``."""
    return db.get(Coin, coin_id)


def get_by_symbol(db: Session, symbol: str) -> Coin | None:
    """Return a coin by its unique ticker symbol, or ``None``."""
    return db.scalar(select(Coin).where(Coin.symbol == symbol))


def list_all(db: Session, *, status: str | None = None) -> list[Coin]:
    """Return coins, newest first, optionally filtered by status."""
    stmt = select(Coin).order_by(Coin.id.desc())
    if status:
        stmt = stmt.where(Coin.status == status)
    return list(db.scalars(stmt))


def add(db: Session, coin: Coin) -> Coin:
    """Persist a new coin and assign its primary key."""
    db.add(coin)
    db.flush()
    return coin


def get_holding(db: Session, *, agent_id: int, coin_id: int) -> Holding | None:
    """Return an agent's holding of a coin, or ``None`` if it holds none."""
    return db.scalar(
        select(Holding).where(Holding.agent_id == agent_id, Holding.coin_id == coin_id)
    )


def upsert_holding(db: Session, *, agent_id: int, coin_id: int, delta: float) -> Holding:
    """Apply ``delta`` to an agent's holding, creating the row if needed."""
    holding = get_holding(db, agent_id=agent_id, coin_id=coin_id)
    if holding is None:
        holding = Holding(agent_id=agent_id, coin_id=coin_id, quantity=0.0)
        db.add(holding)
    holding.quantity = round(holding.quantity + delta, 6)
    db.flush()
    return holding


def holdings_for_agent(db: Session, agent_id: int) -> list[Holding]:
    """Return every non-empty coin holding for an agent."""
    stmt = select(Holding).where(Holding.agent_id == agent_id, Holding.quantity > 0)
    return list(db.scalars(stmt))


def holders(db: Session, coin_id: int) -> list[Holding]:
    """Return every non-empty holding of a coin, largest first."""
    stmt = (
        select(Holding)
        .where(Holding.coin_id == coin_id, Holding.quantity > 0)
        .order_by(Holding.quantity.desc())
    )
    return list(db.scalars(stmt))


def replies(db: Session, coin_id: int, *, limit: int = 50) -> list[CoinReply]:
    """Return a coin's comment thread, newest first."""
    stmt = (
        select(CoinReply)
        .where(CoinReply.coin_id == coin_id)
        .order_by(CoinReply.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
