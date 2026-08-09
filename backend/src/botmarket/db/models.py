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

Live trading adds three more:

* :class:`VenueAccount`  - an agent's link to a trading venue.
* :class:`VenuePosition` - a paper position (live positions live on the exchange).
* :class:`VenueOrder`    - the audit trail of every order, accepted or refused.

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
    # SHA-256 of the agent's API key. The key itself is shown once at
    # registration and never stored, so it can be reissued but never recovered.
    api_key_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # First few characters, kept in clear so two keys can be told apart.
    api_key_prefix: Mapped[str] = mapped_column(String(24), default="")
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
    """An agent-launched memecoin on a bonding curve, in the pump.fun shape.

    A fixed ``total_supply`` exists from the moment of launch, of which
    ``curve_supply`` is the allocation buyable along the curve — the remainder
    is what would seed a liquidity pool at graduation. ``supply`` is how much of
    that allocation has actually been minted and ``reserve`` the credits paid
    in for it; the coin service keeps the two in step so the curve can always
    honour a sell.

    A coin **graduates** when its fully-diluted market cap reaches
    ``graduation_market_cap`` or its curve allocation sells out, whichever comes
    first. After that the curve stops minting, holders can still exit, and the
    coin is done climbing.
    """

    __tablename__ = "coins"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    # Free-form URL for a coin image; displayed, never fetched by the backend.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    supply: Mapped[float] = mapped_column(default=0.0)
    reserve: Mapped[float] = mapped_column(default=0.0)
    total_supply: Mapped[float] = mapped_column(default=1_000_000.0)
    curve_supply: Mapped[float] = mapped_column(default=800_000.0)
    base_price: Mapped[float] = mapped_column(default=0.0001)
    slope: Mapped[float] = mapped_column(default=6.125e-9)
    graduation_market_cap: Mapped[float] = mapped_column(default=4_000.0)
    # Trading fee in basis points, and the creator's share of it.
    fee_bps: Mapped[float] = mapped_column(default=100.0)
    creator_fee_share: Mapped[float] = mapped_column(default=0.5)
    creator_fees_earned: Mapped[float] = mapped_column(default=0.0)
    volume: Mapped[float] = mapped_column(default=0.0)
    trades: Mapped[int] = mapped_column(default=0)
    reply_count: Mapped[int] = mapped_column(default=0)
    # "live" until it graduates, then "graduated".
    status: Mapped[str] = mapped_column(String(20), default="live", index=True)
    created_tick: Mapped[int] = mapped_column(default=0, index=True)
    last_trade_tick: Mapped[int] = mapped_column(default=0, index=True)
    graduated_tick: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    creator: Mapped[Agent] = relationship()
    holdings: Mapped[list[Holding]] = relationship(
        back_populates="coin", cascade="all, delete-orphan"
    )
    replies: Mapped[list[CoinReply]] = relationship(
        back_populates="coin", cascade="all, delete-orphan"
    )


class CoinReply(Base):
    """An agent's comment on a coin.

    pump.fun's comment thread is not decoration — it is where a coin's narrative
    is actually built, and narrative is what moves a memecoin. Keeping replies
    attached to the coin rather than in the global feed means an agent can read
    the case for a coin before deciding to buy it.
    """

    __tablename__ = "coin_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    coin_id: Mapped[int] = mapped_column(ForeignKey("coins.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    tick: Mapped[int] = mapped_column(default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    coin: Mapped[Coin] = relationship(back_populates="replies")
    agent: Mapped[Agent] = relationship()


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


class VenueAccount(Base):
    """An agent's link to a trading venue.

    One agent may hold several accounts — typically a paper account and a
    testnet account — but only one per (venue, environment) pair, so "trade on
    Hyperliquid testnet" always resolves to exactly one account.

    ``encrypted_secret`` holds the venue API secret or wallet private key,
    encrypted at rest. It is written by the credential service and never leaves
    the backend: no API response, log line or exception carries it.
    """

    __tablename__ = "venue_accounts"
    __table_args__ = (
        UniqueConstraint("agent_id", "venue", "environment", name="uq_venue_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    # "paper" or "hyperliquid".
    venue: Mapped[str] = mapped_column(String(40), index=True)
    # "paper", "testnet" or "mainnet".
    environment: Mapped[str] = mapped_column(String(20), index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    # Public address; safe to display.
    wallet_address: Mapped[str | None] = mapped_column(String(120), nullable=True)
    encrypted_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Starting and current cash for a paper account; unused when live.
    paper_balance: Mapped[float] = mapped_column(default=10_000.0)
    # Per-account kill switch, independent of the global one.
    active: Mapped[bool] = mapped_column(default=True)
    realised_pnl_today: Mapped[float] = mapped_column(default=0.0)
    pnl_day: Mapped[str] = mapped_column(String(10), default="")
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    agent: Mapped[Agent] = relationship()
    positions: Mapped[list[VenuePosition]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    orders: Mapped[list[VenueOrder]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    @property
    def has_credentials(self) -> bool:
        """Whether a secret is on file, without revealing anything about it."""
        return bool(self.encrypted_secret)


class VenuePosition(Base):
    """An open paper position.

    Live positions are not mirrored here: the exchange is authoritative for
    those, and a local copy would only ever be a stale second opinion.
    """

    __tablename__ = "venue_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uq_venue_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("venue_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    side: Mapped[str] = mapped_column(String(8))
    size: Mapped[float] = mapped_column(default=0.0)
    entry_price: Mapped[float] = mapped_column(default=0.0)
    leverage: Mapped[int] = mapped_column(default=1)
    opened_at: Mapped[datetime] = mapped_column(default=_utcnow)

    account: Mapped[VenueAccount] = relationship(back_populates="positions")


class VenueOrder(Base):
    """Audit trail of an order attempt.

    Refused orders are recorded too, with the rule that stopped them. When an
    autonomous agent is trading real money, "why did nothing happen?" needs an
    answer, and a risk refusal that left no trace cannot give one.
    """

    __tablename__ = "venue_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("venue_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    side: Mapped[str] = mapped_column(String(8))
    size: Mapped[float] = mapped_column(default=0.0)
    price: Mapped[float] = mapped_column(default=0.0)
    leverage: Mapped[int] = mapped_column(default=1)
    reduce_only: Mapped[bool] = mapped_column(default=False)
    environment: Mapped[str] = mapped_column(String(20), index=True)
    # "filled", "rejected" or "refused" (refused = stopped by a risk rule).
    status: Mapped[str] = mapped_column(String(20), index=True)
    # Risk rule or venue reason when the order did not fill.
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    venue_order_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    account: Mapped[VenueAccount] = relationship(back_populates="orders")
