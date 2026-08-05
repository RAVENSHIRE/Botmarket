"""The paper venue: real mechanics, imaginary money.

This is the default and it needs no credentials, so a fresh checkout can run the
whole live-trading code path — orders, risk checks, positions, PnL — without an
exchange account existing anywhere. That matters for more than convenience: the
paper venue is the same object shape as the live one, so every test of the
trading stack exercises the code that will later face real money.

Fills are immediate and at the quote, with a configurable slippage. It does not
pretend to model an order book; it models an account faithfully, which is the
part the risk engine and the agent care about.

Prices come from the simulated market by default, so paper trading tracks the
same world the rest of Botmarket lives in.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from botmarket.db.models import VenueAccount, VenuePosition
from botmarket.domain.venue import (
    AccountState,
    Balance,
    Candle,
    Environment,
    Instrument,
    OrderRequest,
    OrderResult,
    OrderType,
    Position,
    Quote,
    Side,
)

#: Instruments the paper venue knows how to price.
PAPER_INSTRUMENTS: dict[str, Instrument] = {
    "BTC": Instrument(
        symbol="BTC",
        size_step=Decimal("0.0001"),
        price_step=Decimal("0.5"),
        min_notional=Decimal("10"),
        max_leverage=20,
    ),
    "ETH": Instrument(
        symbol="ETH",
        size_step=Decimal("0.001"),
        price_step=Decimal("0.05"),
        min_notional=Decimal("10"),
        max_leverage=20,
    ),
    "SOL": Instrument(
        symbol="SOL",
        size_step=Decimal("0.01"),
        price_step=Decimal("0.01"),
        min_notional=Decimal("10"),
        max_leverage=10,
    ),
}

#: Opening prices for the synthetic series, in USDC.
_ANCHORS: dict[str, Decimal] = {
    "BTC": Decimal("65000"),
    "ETH": Decimal("3200"),
    "SOL": Decimal("150"),
}

DEFAULT_SPREAD_BPS = Decimal("2")


class PaperMarketData:
    """Synthetic but deterministic market data.

    The series is seeded from the symbol, so the same symbol always produces the
    same history within a process. A test that asserts on a factor value needs
    the data under it to hold still.
    """

    environment = Environment.PAPER

    def __init__(self, *, seed: int = 7, spread_bps: Decimal = DEFAULT_SPREAD_BPS) -> None:
        self._seed = seed
        self._spread_bps = spread_bps

    def instrument(self, symbol: str) -> Instrument:
        """Return trading rules for ``symbol``, defaulting to generic ones."""
        return PAPER_INSTRUMENTS.get(
            symbol.upper(), Instrument(symbol=symbol.upper())
        )

    def _series(self, symbol: str, length: int) -> list[Decimal]:
        """Return a deterministic random-walk price series for ``symbol``."""
        rng = random.Random(f"{self._seed}:{symbol.upper()}")
        price = _ANCHORS.get(symbol.upper(), Decimal("100"))
        series: list[Decimal] = []
        for _ in range(length):
            drift = Decimal(str(round(rng.gauss(0, 0.006), 6)))
            price = max(price * (Decimal(1) + drift), Decimal("0.01"))
            series.append(price.quantize(Decimal("0.01")))
        return series

    def quote(self, symbol: str) -> Quote:
        """Return a synthetic bid/ask around the latest price."""
        mid = self._series(symbol, 200)[-1]
        half = mid * self._spread_bps / Decimal(20_000)
        return Quote(
            symbol=symbol.upper(),
            bid=(mid - half).quantize(Decimal("0.01")),
            ask=(mid + half).quantize(Decimal("0.01")),
            timestamp=datetime.now(UTC),
        )

    def candles(self, symbol: str, *, interval: str = "1h", limit: int = 100) -> list[Candle]:
        """Return synthetic OHLCV bars, oldest first."""
        closes = self._series(symbol, limit + 1)
        step = _interval_delta(interval)
        now = datetime.now(UTC)
        candles: list[Candle] = []

        for i in range(1, len(closes)):
            open_, close = closes[i - 1], closes[i]
            high = max(open_, close) * Decimal("1.002")
            low = min(open_, close) * Decimal("0.998")
            candles.append(
                Candle(
                    symbol=symbol.upper(),
                    timestamp=now - step * (len(closes) - 1 - i),
                    open=open_,
                    high=high.quantize(Decimal("0.01")),
                    low=low.quantize(Decimal("0.01")),
                    close=close,
                    volume=Decimal(1000 + (i * 37) % 900),
                )
            )
        return candles


class PaperVenue:
    """An execution venue that settles against the database, not an exchange."""

    name = "paper"
    environment = Environment.PAPER

    def __init__(
        self,
        db: Session,
        account: VenueAccount,
        *,
        market_data: PaperMarketData | None = None,
        slippage_bps: Decimal = Decimal("1"),
    ) -> None:
        self._db = db
        self._account = account
        self._data = market_data or PaperMarketData()
        self._slippage_bps = slippage_bps

    # --- Reads -----------------------------------------------------------

    def account_state(self) -> AccountState:
        """Return the paper account's cash and open positions."""
        positions: list[Position] = []
        margin_used = Decimal(0)

        for row in self._account.positions:
            if row.size == 0:
                continue
            mark = self._data.quote(row.symbol).mid
            side = Side(row.side)
            entry = Decimal(str(row.entry_price))
            size = Decimal(str(row.size))
            pnl = (mark - entry) * size * Decimal(side.sign)
            margin_used += size * entry / Decimal(max(row.leverage, 1))
            positions.append(
                Position(
                    symbol=row.symbol,
                    side=side,
                    size=size,
                    entry_price=entry,
                    mark_price=mark,
                    leverage=row.leverage,
                    unrealised_pnl=pnl.quantize(Decimal("0.01")),
                )
            )

        total = Decimal(str(self._account.paper_balance))
        return AccountState(
            environment=Environment.PAPER,
            balances=[
                Balance(
                    currency="USDC",
                    total=total.quantize(Decimal("0.01")),
                    available=max(Decimal(0), total - margin_used).quantize(Decimal("0.01")),
                )
            ],
            positions=positions,
        )

    # --- Writes ----------------------------------------------------------

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Fill ``request`` immediately at the quote plus slippage.

        The caller is expected to have run the risk checks already; this method
        enforces only what the *venue* would — instrument rounding, and the
        rule that a reduce-only order cannot flip a position.
        """
        instrument = self._data.instrument(request.symbol)
        size = instrument.round_size(abs(request.size))
        if size <= 0:
            return OrderResult(
                accepted=False,
                symbol=request.symbol,
                side=request.side,
                environment=Environment.PAPER,
                reason=f"Size rounds to zero at the {instrument.size_step} step",
            )

        quote = self._data.quote(request.symbol)
        fill_price = self._fill_price(request, quote)

        position = self._position_row(request.symbol)
        if request.reduce_only:
            if position is None or Side(position.side) is request.side:
                return OrderResult(
                    accepted=False,
                    symbol=request.symbol,
                    side=request.side,
                    environment=Environment.PAPER,
                    reason="Reduce-only order has no opposing position to close",
                )
            size = min(size, Decimal(str(position.size)))

        realised = self._apply_fill(request, size, fill_price)
        self._db.flush()

        return OrderResult(
            accepted=True,
            symbol=request.symbol.upper(),
            side=request.side,
            filled_size=size,
            average_price=fill_price,
            order_id=f"paper-{request.symbol.upper()}-{self._account.id}",
            client_id=request.client_id,
            environment=Environment.PAPER,
            raw={"realised_pnl": str(realised)},
        )

    def close_position(self, symbol: str) -> OrderResult:
        """Flatten the open position in ``symbol``."""
        row = self._position_row(symbol)
        if row is None or row.size == 0:
            return OrderResult(
                accepted=False,
                symbol=symbol.upper(),
                side=Side.SELL,
                environment=Environment.PAPER,
                reason=f"No open position in {symbol.upper()}",
            )
        return self.place_order(
            OrderRequest(
                symbol=symbol.upper(),
                side=Side(row.side).opposite,
                size=Decimal(str(row.size)),
                reduce_only=True,
            )
        )

    # --- Internals -------------------------------------------------------

    def _fill_price(self, request: OrderRequest, quote: Quote) -> Decimal:
        """Return the price this order fills at, including slippage.

        Slippage always works against the taker, which is the honest direction:
        a paper venue that filled at the mid would flatter every strategy.
        """
        if request.order_type is OrderType.LIMIT and request.limit_price is not None:
            return request.limit_price
        base = quote.ask if request.side is Side.BUY else quote.bid
        drag = base * self._slippage_bps / Decimal(10_000)
        price = base + drag if request.side is Side.BUY else base - drag
        return price.quantize(Decimal("0.01"))

    def _position_row(self, symbol: str) -> VenuePosition | None:
        """Return the *open* position for ``symbol``, if any.

        Closed positions are excluded: for reduce-only checks and closing, a
        flat symbol is the same as one that was never traded.
        """
        return next(
            (p for p in self._account.positions if p.symbol == symbol.upper() and p.size > 0),
            None,
        )

    def _any_position_row(self, symbol: str) -> VenuePosition | None:
        """Return the stored row for ``symbol`` whether or not it is open.

        Closing a position zeroes its row rather than deleting it, and there is
        a unique constraint on (account, symbol). Opening a new position has to
        revive that row — inserting a second one would violate the constraint
        and, before this existed, made a symbol untradable once it had been
        closed.
        """
        return next(
            (p for p in self._account.positions if p.symbol == symbol.upper()),
            None,
        )

    def _apply_fill(
        self, request: OrderRequest, size: Decimal, price: Decimal
    ) -> Decimal:
        """Update cash and position for a fill, returning realised PnL."""
        symbol = request.symbol.upper()
        row = self._any_position_row(symbol)
        realised = Decimal(0)

        if row is None:
            self._db.add(
                VenuePosition(
                    account_id=self._account.id,
                    symbol=symbol,
                    side=request.side.value,
                    size=float(size),
                    entry_price=float(price),
                    leverage=request.leverage,
                )
            )
            self._db.flush()
            self._db.refresh(self._account)
            return realised

        if row.size == 0:
            # Reopening a symbol that was previously closed out.
            row.side = request.side.value
            row.size = float(size)
            row.entry_price = float(price)
            row.leverage = request.leverage
            return realised

        held = Decimal(str(row.size))
        entry = Decimal(str(row.entry_price))
        side = Side(row.side)

        if side is request.side:
            # Adding to the position: the entry becomes a weighted average.
            total = held + size
            row.entry_price = float(((entry * held) + (price * size)) / total)
            row.size = float(total)
        else:
            closed = min(size, held)
            realised = (price - entry) * closed * Decimal(side.sign)
            self._credit(realised)
            remaining = held - closed
            row.size = float(remaining)

            leftover = size - closed
            if leftover > 0:
                # The order was larger than the position: flip to the new side.
                row.side = request.side.value
                row.size = float(leftover)
                row.entry_price = float(price)
                row.leverage = request.leverage

        return realised.quantize(Decimal("0.01"))

    def _credit(self, amount: Decimal) -> None:
        """Apply realised PnL to the paper balance and the daily loss counter."""
        self._account.paper_balance = float(
            Decimal(str(self._account.paper_balance)) + amount
        )
        today = datetime.now(UTC).date().isoformat()
        if self._account.pnl_day != today:
            self._account.pnl_day = today
            self._account.realised_pnl_today = 0.0
        if amount < 0:
            self._account.realised_pnl_today = float(
                Decimal(str(self._account.realised_pnl_today)) + abs(amount)
            )


def _interval_delta(interval: str) -> timedelta:
    """Return the wall-clock length of a candle interval."""
    units = {"m": "minutes", "h": "hours", "d": "days"}
    suffix = interval[-1]
    if suffix not in units or not interval[:-1].isdigit():
        return timedelta(hours=1)
    return timedelta(**{units[suffix]: int(interval[:-1])})
