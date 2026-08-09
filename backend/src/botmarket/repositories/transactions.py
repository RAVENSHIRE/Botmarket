"""Transaction ledger persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from botmarket.db.models import Transaction

# Ledger kinds that represent pressure on the native $BOT market.
MARKET_KINDS = ("buy", "sell")


def add(
    db: Session,
    *,
    agent_id: int,
    kind: str,
    amount: float,
    tick: int,
    quantity: float = 0.0,
    counterparty_id: int | None = None,
    coin_id: int | None = None,
) -> Transaction:
    """Record a ledger entry. ``amount`` is the signed credit delta for the agent."""
    row = Transaction(
        agent_id=agent_id,
        counterparty_id=counterparty_id,
        coin_id=coin_id,
        kind=kind,
        amount=amount,
        quantity=quantity,
        tick=tick,
    )
    db.add(row)
    db.flush()
    return row


def net_market_pressure(db: Session, tick: int) -> float:
    """Return signed $BOT demand recorded for ``tick``.

    Buys push the price up and sells push it down, so the tick's aggregate
    pressure is ``bought - sold`` measured in tokens. External agents trading
    between ticks stamp their transactions with the upcoming tick, which is how
    their activity feeds into the next price move.
    """
    bought = db.scalar(
        select(func.coalesce(func.sum(Transaction.quantity), 0.0)).where(
            Transaction.tick == tick, Transaction.kind == "buy"
        )
    )
    sold = db.scalar(
        select(func.coalesce(func.sum(Transaction.quantity), 0.0)).where(
            Transaction.tick == tick, Transaction.kind == "sell"
        )
    )
    return float(bought or 0.0) - float(sold or 0.0)


def recent(db: Session, *, limit: int = 50, agent_id: int | None = None) -> list[Transaction]:
    """Return recent ledger entries, newest first."""
    stmt = select(Transaction).order_by(Transaction.id.desc()).limit(limit)
    if agent_id is not None:
        stmt = stmt.where(Transaction.agent_id == agent_id)
    return list(db.scalars(stmt))


def for_coin(db: Session, coin_id: int, *, limit: int = 50) -> list[Transaction]:
    """Return recent ledger entries touching a coin, newest first."""
    stmt = (
        select(Transaction)
        .where(Transaction.coin_id == coin_id)
        .order_by(Transaction.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
