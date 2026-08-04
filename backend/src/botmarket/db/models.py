"""SQLAlchemy ORM models for BOTMARKET.

Core entities of the simulated agent economy:

* :class:`Agent`       - an autonomous participant with a wallet and reputation.
* :class:`Post`        - public social content produced by agents.
* :class:`Event`       - simulation/market events emitted each tick.
* :class:`Transaction` - value transfers affecting agent wallets.
* :class:`Reputation`  - append-only reputation change log per agent.
* :class:`Coin`        - an agent-launched memecoin on a bonding curve.
* :class:`Holding`     - an agent's balance of a given memecoin.
* :class:`Proposal`    - a governance proposal funded from an agent's wallet.
* :class:`Vote`        - a token-weighted vote cast on a proposal.

Models use SQLAlchemy 2.0 typed mappings and are PostgreSQL-compatible.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from botmarket.db.session import Base


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class Agent(Base):
    """An autonomous agent participating in the BOTMARKET economy.

    ``wallet`` holds spendable credits; ``tokens`` holds units of the native
    $BOT token, whose price is set by the simulated market.
    """

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # Agent role/archetype, e.g. "trader", "meme", "analyst".
    agent_type: Mapped[str] = mapped_column(String(50), index=True)
    personality: Mapped[str] = mapped_column(Text, default="")
    strategy: Mapped[str] = mapped_column(String(120), default="balanced")
    wallet: Mapped[float] = mapped_column(default=1000.0)
    tokens: Mapped[float] = mapped_column(default=0.0)
    reputation: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    posts: Mapped[list[Post]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    reputation_log: Mapped[list[Reputation]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    holdings: Mapped[list[Holding]] = relationship(
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

    author: Mapped[Agent] = relationship(back_populates="posts")


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
    """A value transfer that affects one or two agent wallets.

    ``amount`` is always the signed credit delta for ``agent_id``: negative
    when the agent spends, positive when it receives. ``quantity`` records the
    matching token/coin movement where one applies.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    counterparty_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id"), nullable=True
    )
    coin_id: Mapped[int | None] = mapped_column(ForeignKey("coins.id"), nullable=True)
    amount: Mapped[float] = mapped_column(default=0.0)
    quantity: Mapped[float] = mapped_column(default=0.0)
    # e.g. "buy", "sell", "tip", "coin_buy", "coin_sell", "coin_launch", "proposal".
    kind: Mapped[str] = mapped_column(String(50), default="trade", index=True)
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

    agent: Mapped[Agent] = relationship(back_populates="reputation_log")


class Coin(Base):
    """An agent-launched memecoin priced by a linear bonding curve.

    ``supply`` is the number of units minted so far and ``reserve`` the credits
    paid in to mint them. Both are maintained by the coin service so the curve
    and the reserve never drift apart.
    """

    __tablename__ = "coins"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    creator_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    supply: Mapped[float] = mapped_column(default=0.0)
    reserve: Mapped[float] = mapped_column(default=0.0)
    base_price: Mapped[float] = mapped_column(default=1.0)
    slope: Mapped[float] = mapped_column(default=0.01)
    # "live" until the reserve target is hit, then "graduated".
    status: Mapped[str] = mapped_column(String(20), default="live", index=True)
    created_tick: Mapped[int] = mapped_column(default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    creator: Mapped[Agent] = relationship()
    holdings: Mapped[list[Holding]] = relationship(
        back_populates="coin", cascade="all, delete-orphan"
    )


class Holding(Base):
    """An agent's balance of a single memecoin."""

    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("agent_id", "coin_id", name="uq_holding_agent_coin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    coin_id: Mapped[int] = mapped_column(ForeignKey("coins.id"), index=True)
    quantity: Mapped[float] = mapped_column(default=0.0)

    agent: Mapped[Agent] = relationship(back_populates="holdings")
    coin: Mapped[Coin] = relationship(back_populates="holdings")


class Proposal(Base):
    """A governance proposal submitted by an agent at a cost in credits."""

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    # World effect applied to the market if the proposal passes.
    effect: Mapped[str] = mapped_column(String(50), default="signal")
    magnitude: Mapped[float] = mapped_column(default=0.0)
    cost: Mapped[float] = mapped_column(default=0.0)
    # "open" while voting, then "passed" or "rejected".
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_tick: Mapped[int] = mapped_column(default=0, index=True)
    closes_tick: Mapped[int] = mapped_column(default=0, index=True)
    resolved_tick: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    author: Mapped[Agent] = relationship()
    votes: Mapped[list[Vote]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class Vote(Base):
    """A weighted vote cast by an agent on a proposal.

    Weight is derived from the voter's $BOT holdings and reputation at the
    moment the vote is cast, so it is recorded rather than recomputed.
    """

    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("proposal_id", "agent_id", name="uq_vote_proposal_agent"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    support: Mapped[bool] = mapped_column(default=True)
    weight: Mapped[float] = mapped_column(default=0.0)
    tick: Mapped[int] = mapped_column(default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    proposal: Mapped[Proposal] = relationship(back_populates="votes")
    agent: Mapped[Agent] = relationship()
