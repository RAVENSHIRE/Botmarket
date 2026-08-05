"""The venue port: where an agent's orders actually go.

Botmarket agents decide the same way regardless of what is on the other side of
the trade. This module defines the vocabulary and the two protocols that make
that true:

* :class:`MarketDataFeed` — where prices come from.
* :class:`ExecutionVenue` — where orders go and what they do to an account.

Two implementations exist. The paper venue is backed by the simulated market and
is the default, so a fresh checkout never touches an exchange. The Hyperliquid
venue places real perpetual orders. Because both satisfy the same protocol, the
only thing that changes when an agent goes live is which object it was handed.

Everything here is pure vocabulary — no HTTP, no database, no credentials.

Money is :class:`~decimal.Decimal` throughout. Exchange balances are not the
place for binary floating point: a repeated float round-trip silently drifts,
and drift in a position size is a real loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol, runtime_checkable


class Side(str, Enum):
    """Direction of an order."""

    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> Side:
        """Return the side that closes a position opened on this one."""
        return Side.SELL if self is Side.BUY else Side.BUY

    @property
    def sign(self) -> int:
        """Return ``+1`` for a long-increasing side, ``-1`` for a short."""
        return 1 if self is Side.BUY else -1


class OrderType(str, Enum):
    """How an order should be filled."""

    MARKET = "market"
    LIMIT = "limit"


class Environment(str, Enum):
    """Which world a venue is pointed at.

    This is deliberately not a boolean. A venue must be able to assert its
    environment on every call, and ``testnet``/``mainnet`` read unambiguously in
    a log line where ``is_live=False`` does not.
    """

    PAPER = "paper"
    TESTNET = "testnet"
    MAINNET = "mainnet"

    @property
    def is_real_money(self) -> bool:
        """Whether a loss here costs the operator actual money."""
        return self is Environment.MAINNET


@dataclass(frozen=True)
class Instrument:
    """A tradable symbol on a venue."""

    symbol: str
    #: Smallest tradable increment of size, e.g. ``0.001`` BTC.
    size_step: Decimal = Decimal("0.0001")
    #: Smallest price increment.
    price_step: Decimal = Decimal("0.01")
    #: Venue-enforced minimum notional for a single order.
    min_notional: Decimal = Decimal("10")
    max_leverage: int = 10

    def round_size(self, size: Decimal) -> Decimal:
        """Round ``size`` down to a tradable increment.

        Rounding *down* is deliberate: rounding up could push an order past a
        risk limit that was checked against the requested size.
        """
        if self.size_step <= 0:
            return size
        return (size // self.size_step) * self.size_step


@dataclass(frozen=True)
class Quote:
    """A point-in-time price for an instrument."""

    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: datetime

    @property
    def mid(self) -> Decimal:
        """Return the midpoint between bid and ask."""
        return (self.bid + self.ask) / 2

    @property
    def spread_bps(self) -> Decimal:
        """Return the bid/ask spread in basis points."""
        if self.mid == 0:
            return Decimal(0)
        return (self.ask - self.bid) / self.mid * Decimal(10_000)


@dataclass(frozen=True)
class Candle:
    """One OHLCV bar."""

    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class Balance:
    """An account's cash position on a venue."""

    currency: str
    total: Decimal
    #: Free margin — what a new order can actually draw on.
    available: Decimal


@dataclass(frozen=True)
class Position:
    """An open perpetual position."""

    symbol: str
    side: Side
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: int = 1
    unrealised_pnl: Decimal = Decimal(0)
    liquidation_price: Decimal | None = None

    @property
    def notional(self) -> Decimal:
        """Return the position's current notional value."""
        return abs(self.size) * self.mark_price


@dataclass(frozen=True)
class AccountState:
    """Everything a risk check needs to know about an account right now."""

    environment: Environment
    balances: list[Balance] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)

    def balance(self, currency: str = "USDC") -> Balance:
        """Return the balance for ``currency``, or a zero balance."""
        for entry in self.balances:
            if entry.currency == currency:
                return entry
        return Balance(currency=currency, total=Decimal(0), available=Decimal(0))

    def position(self, symbol: str) -> Position | None:
        """Return the open position in ``symbol``, if any."""
        return next((p for p in self.positions if p.symbol == symbol), None)

    @property
    def gross_notional(self) -> Decimal:
        """Return the summed notional of every open position."""
        return sum((p.notional for p in self.positions), Decimal(0))


@dataclass(frozen=True)
class OrderRequest:
    """An intent to trade, before any venue has seen it."""

    symbol: str
    side: Side
    size: Decimal
    order_type: OrderType = OrderType.MARKET
    #: Required for a limit order, ignored for a market order.
    limit_price: Decimal | None = None
    leverage: int = 1
    #: Set when the order may only shrink an existing position.
    reduce_only: bool = False
    #: Caller-supplied idempotency key, echoed back by the venue.
    client_id: str | None = None

    def notional_at(self, price: Decimal) -> Decimal:
        """Return what this order is worth at ``price``."""
        return abs(self.size) * price


@dataclass(frozen=True)
class OrderResult:
    """What a venue did with an :class:`OrderRequest`."""

    accepted: bool
    symbol: str
    side: Side
    #: Size actually filled, which may be below the requested size.
    filled_size: Decimal = Decimal(0)
    average_price: Decimal = Decimal(0)
    order_id: str | None = None
    client_id: str | None = None
    environment: Environment = Environment.PAPER
    #: Populated when ``accepted`` is false.
    reason: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def notional(self) -> Decimal:
        """Return the filled notional."""
        return self.filled_size * self.average_price


@runtime_checkable
class MarketDataFeed(Protocol):
    """Read-only market data. Never requires credentials."""

    @property
    def environment(self) -> Environment:
        """Which world this feed reports on."""
        ...

    def instrument(self, symbol: str) -> Instrument:
        """Return trading rules for ``symbol``."""
        ...

    def quote(self, symbol: str) -> Quote:
        """Return the current best bid/ask for ``symbol``."""
        ...

    def candles(self, symbol: str, *, interval: str = "1h", limit: int = 100) -> list[Candle]:
        """Return recent OHLCV bars, oldest first."""
        ...


@runtime_checkable
class ExecutionVenue(Protocol):
    """Somewhere an agent can actually place an order."""

    @property
    def environment(self) -> Environment:
        """Which world this venue trades in."""
        ...

    @property
    def name(self) -> str:
        """Short venue identifier, e.g. ``paper`` or ``hyperliquid``."""
        ...

    def account_state(self) -> AccountState:
        """Return balances and open positions."""
        ...

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Submit ``request`` and report what happened."""
        ...

    def close_position(self, symbol: str) -> OrderResult:
        """Flatten the open position in ``symbol``."""
        ...
