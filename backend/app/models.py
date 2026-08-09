"""SQLAlchemy ORM models for BOTMARKET.

Core entities of the simulated agent economy:

* :class:`Agent`       - an autonomous participant with a wallet and reputation.
* :class:`Post`        - public social content produced by agents.
* :class:`Event`       - simulation/market events emitted each tick.
* :class:`Transaction` - value transfers affecting agent wallets.
* :class:`Reputation`  - append-only reputation change log per agent.

Models use SQLAlchemy 2.0 typed mappings and are PostgreSQL-compatible.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Agent(Base):
    """An autonomous agent participating in the BOTMARKET economy."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # Agent role/archetype, e.g. "trader", "meme", "analyst".
    agent_type: Mapped[str] = mapped_column(String(50), index=True)
    personality: Mapped[str] = mapped_column(Text, default="")
    strategy: Mapped[str] = mapped_column(String(120), default="balanced")
    wallet: Mapped[float] = mapped_column(default=1000.0)
    reputation: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    posts: Mapped[list["Post"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    reputation_log: Mapped[list["Reputation"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class Post(Base):
    """A public social post authored by an agent."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    # Free-form category, e.g. "meme", "analysis", "trade_signal".
    kind: Mapped[str] = mapped_column(String(50), default="post")
    tick: Mapped[int] = mapped_column(default=0, index=True)
    likes: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    author: Mapped["Agent"] = relationship(back_populates="posts")


class Event(Base):
    """A simulation or market event emitted during a tick."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tick: Mapped[int] = mapped_column(default=0, index=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(Text)
    # Numeric impact (e.g. market move); optional/contextual.
    magnitude: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Transaction(Base):
    """A value transfer that affects one or two agent wallets."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    counterparty_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id"), nullable=True
    )
    amount: Mapped[float] = mapped_column(default=0.0)
    kind: Mapped[str] = mapped_column(String(50), default="trade")
    # Set for coin-related transactions (launch/buy/sell); NULL otherwise.
    coin_id: Mapped[int | None] = mapped_column(
        ForeignKey("coins.id"), nullable=True, index=True
    )
    tick: Mapped[int] = mapped_column(default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Reputation(Base):
    """Append-only reputation change record for an agent."""

    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    delta: Mapped[float] = mapped_column(default=0.0)
    reason: Mapped[str] = mapped_column(String(255), default="")
    tick: Mapped[int] = mapped_column(default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    agent: Mapped["Agent"] = relationship(back_populates="reputation_log")


class Coin(Base):
    """A memecoin launched by an agent and priced by a bonding curve.

    Price is a pure function of ``supply`` via the curve parameters
    ``base_price`` and ``slope`` (see ``app.economy.bonding_curve``). ``reserve``
    is the amount of native token collected by the curve. When ``reserve``
    crosses the graduation threshold the coin's ``status`` becomes
    ``"graduated"``.
    """

    __tablename__ = "coins"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    supply: Mapped[float] = mapped_column(default=0.0)  # tokens in circulation
    reserve: Mapped[float] = mapped_column(default=0.0)  # native token collected
    base_price: Mapped[float] = mapped_column(default=1.0)
    slope: Mapped[float] = mapped_column(default=0.01)
    status: Mapped[str] = mapped_column(String(20), default="active")
    tick: Mapped[int] = mapped_column(default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    creator: Mapped["Agent"] = relationship()
    holdings: Mapped[list["CoinHolding"]] = relationship(
        back_populates="coin", cascade="all, delete-orphan"
    )


class CoinHolding(Base):
    """An agent's balance of a particular coin."""

    __tablename__ = "coin_holdings"
    __table_args__ = (
        UniqueConstraint("coin_id", "agent_id", name="uq_holding_coin_agent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    coin_id: Mapped[int] = mapped_column(ForeignKey("coins.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    balance: Mapped[float] = mapped_column(default=0.0)

    coin: Mapped["Coin"] = relationship(back_populates="holdings")
    agent: Mapped["Agent"] = relationship()
