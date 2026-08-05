"""Reads of world time and the native $BOT market.

The market is reconstructed from the persisted price series rather than held in
memory, so every process (API worker, CLI, test) sees the same world.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.domain.market import Market
from botmarket.repositories import events as events_repo


def current_tick(db: Session) -> int:
    """Return the most recently completed tick (``0`` before the first)."""
    return events_repo.latest_tick(db)


def next_tick(db: Session) -> int:
    """Return the tick that is currently accruing activity.

    Actions taken between ticks are stamped with this number, so they settle
    into the next price move rather than being retroactively applied.
    """
    return current_tick(db) + 1


def load(db: Session) -> Market:
    """Rebuild the market from its persisted price history."""
    prices = events_repo.price_history(db)
    market = Market()
    if prices:
        market.price = prices[-1]
        market.history = prices
    return market


def current_price(db: Session) -> float:
    """Return the latest $BOT price."""
    return load(db).price


def snapshot(db: Session, *, history_limit: int = 60) -> dict:
    """Return a price/trend snapshot suitable for the dashboard."""
    market = load(db)
    return {
        "tick": current_tick(db),
        "price": market.price,
        "trend": market.trend,
        "history": market.history[-history_limit:],
    }
