"""Event persistence, including the market price series.

The market has no table of its own: each tick writes a ``price`` event whose
``magnitude`` is the closing price. That series is the single source of truth
for both the current price and the tick counter.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from botmarket.db.models import Event

PRICE_KIND = "price"


def add(db: Session, *, tick: int, kind: str, description: str, magnitude: float = 0.0) -> Event:
    """Persist a world event and return it."""
    event = Event(tick=tick, kind=kind, description=description, magnitude=magnitude)
    db.add(event)
    db.flush()
    return event


def latest_tick(db: Session) -> int:
    """Return the highest tick recorded so far (``0`` before the first tick)."""
    return db.scalar(select(func.max(Event.tick))) or 0


def price_history(db: Session, *, limit: int = 200) -> list[float]:
    """Return the most recent closing prices in chronological order."""
    stmt = (
        select(Event.magnitude)
        .where(Event.kind == PRICE_KIND)
        .order_by(Event.tick.desc())
        .limit(limit)
    )
    return list(reversed(list(db.scalars(stmt))))


def recent(db: Session, *, limit: int = 20, exclude_price: bool = True) -> list[Event]:
    """Return recent world events, newest first.

    Price ticks are excluded by default: they are bookkeeping rather than news.
    """
    stmt = select(Event).order_by(Event.id.desc()).limit(limit)
    if exclude_price:
        stmt = stmt.where(Event.kind != PRICE_KIND)
    return list(db.scalars(stmt))
