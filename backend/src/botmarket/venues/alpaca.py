"""The Alpaca venue: real equities and spot crypto.

Alpaca differs from Hyperliquid in ways the venue port has to absorb rather than
leak upward:

* **Spot, not perpetuals.** There is no leverage on crypto and no funding rate,
  so instruments report ``max_leverage=1`` and the risk engine's leverage
  ceiling does the rest. Equities do support margin, but this adapter does not
  request it — an agent asking for 5× on a stock gets 1× and a clear refusal
  rather than a surprise margin position.
* **A short is a flat position, not a negative one.** Selling what you do not
  hold is rejected by Alpaca for crypto, so ``reduce_only`` maps onto "sell what
  you have" and nothing here tries to open a short.
* **Symbols carry a quote currency.** ``BTC`` on the venue port becomes
  ``BTC/USD`` on the wire, and back again on the way out, so agents keep using
  one vocabulary across venues.
* **Their "paper" is our testnet.** Alpaca's paper endpoint is a full
  simulation with real market data, which is exactly what ``Environment.TESTNET``
  means here — so it inherits the same gating, and ``mainnet`` remains the only
  setting that can lose money.

The HTTP client is injected, so every branch below is tested without a network.

.. warning::
   Exercised against recorded response shapes, not a live Alpaca endpoint. Run
   it on the paper endpoint and reconcile fills by hand before trading real
   money.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from botmarket.domain.errors import InvalidAction
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

LIVE_API_URL = "https://api.alpaca.markets"
PAPER_API_URL = "https://paper-api.alpaca.markets"
DATA_API_URL = "https://data.alpaca.markets"

#: Quote currency appended to a bare symbol for Alpaca's crypto pairs.
QUOTE_CURRENCY = "USD"

#: Interval names on the venue port mapped onto Alpaca timeframes.
TIMEFRAMES = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "30m": "30Min",
    "1h": "1Hour",
    "4h": "4Hour",
    "1d": "1Day",
}


def api_url(environment: Environment) -> str:
    """Return the trading endpoint for ``environment``.

    Raises:
        InvalidAction: If asked for a paper endpoint — Botmarket's own paper
            venue covers that, and Alpaca's paper API is mapped to testnet.
    """
    if environment is Environment.MAINNET:
        return LIVE_API_URL
    if environment is Environment.TESTNET:
        return PAPER_API_URL
    raise InvalidAction(
        "Alpaca has no offline mode; use the paper venue, or testnet for "
        "Alpaca's own paper endpoint"
    )


def to_wire(symbol: str) -> str:
    """Return the venue's symbol for a bare ticker.

    Crypto trades as a pair (``BTC/USD``); equities are bare (``AAPL``). A
    symbol that already carries a slash is passed through untouched.
    """
    upper = symbol.upper()
    if "/" in upper:
        return upper
    return f"{upper}/{QUOTE_CURRENCY}" if _looks_like_crypto(upper) else upper


def from_wire(symbol: str) -> str:
    """Return the bare ticker for a venue symbol."""
    return symbol.upper().split("/")[0]


#: Tickers Alpaca quotes as crypto pairs. Anything else is treated as equity.
_CRYPTO = frozenset(
    {"BTC", "ETH", "SOL", "DOGE", "AVAX", "LINK", "LTC", "BCH", "UNI", "AAVE", "DOT", "SHIB"}
)


def _looks_like_crypto(symbol: str) -> bool:
    """Whether ``symbol`` should be quoted as a crypto pair."""
    return symbol in _CRYPTO


class Transport(Protocol):
    """The HTTP surface this adapter needs.

    Injecting it keeps the credentials on one path and makes every branch below
    testable without a network — the same reason the Hyperliquid adapter takes
    its SDK clients rather than constructing them.
    """

    def get(self, url: str, *, params: dict | None = None) -> Any: ...
    def post(self, url: str, *, json: dict) -> Any: ...
    def delete(self, url: str) -> Any: ...


class HttpxTransport:
    """A :class:`Transport` backed by httpx, carrying Alpaca's auth headers."""

    def __init__(self, key_id: str, secret_key: str, *, timeout: float = 15.0) -> None:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - depends on the extra
            raise InvalidAction(
                "The Alpaca venue needs the optional dependencies. Install "
                "them with `pip install -e 'backend[live]'`."
            ) from exc

        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "APCA-API-KEY-ID": key_id,
                "APCA-API-SECRET-KEY": secret_key,
                "accept": "application/json",
            },
        )

    def get(self, url: str, *, params: dict | None = None) -> Any:
        """Perform a GET and return the decoded body."""
        return self._raise_or_decode(self._client.get(url, params=params))

    def post(self, url: str, *, json: dict) -> Any:
        """Perform a POST and return the decoded body."""
        return self._raise_or_decode(self._client.post(url, json=json))

    def delete(self, url: str) -> Any:
        """Perform a DELETE and return the decoded body."""
        return self._raise_or_decode(self._client.delete(url))

    @staticmethod
    def _raise_or_decode(response: Any) -> Any:
        """Return the JSON body, turning an error status into a domain error.

        Alpaca reports refusals as 4xx with a JSON ``message``. Surfacing that
        message is the difference between "order rejected: insufficient buying
        power" and an opaque 403.
        """
        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                detail = body.get("message") or body.get("error") or ""
            except Exception:  # noqa: BLE001 - a non-JSON error body is still an error
                detail = response.text[:200]
            raise InvalidAction(f"Alpaca returned {response.status_code}: {detail}")
        if not response.content:
            return {}
        return response.json()


def build_transport(*, key_id: str, secret_key: str) -> Transport:
    """Construct the real HTTP transport."""
    return HttpxTransport(key_id, secret_key)


class AlpacaMarketData:
    """Read-only Alpaca market data."""

    def __init__(
        self,
        transport: Transport,
        *,
        environment: Environment,
        data_url: str = DATA_API_URL,
    ) -> None:
        self._transport = transport
        self._environment = environment
        self._data_url = data_url

    @property
    def environment(self) -> Environment:
        """Which Alpaca world this feed reports on."""
        return self._environment

    def instrument(self, symbol: str) -> Instrument:
        """Return trading rules for ``symbol``.

        Alpaca allows fractional quantities on both crypto and most equities,
        and offers no leverage on crypto — so the ceiling reported here is 1×
        and the risk engine refuses anything higher before an order is built.
        """
        bare = from_wire(symbol)
        crypto = _looks_like_crypto(bare)
        return Instrument(
            symbol=bare,
            size_step=Decimal("0.000001") if crypto else Decimal("0.001"),
            price_step=Decimal("0.01"),
            min_notional=Decimal("1"),
            max_leverage=1,
        )

    def quote(self, symbol: str) -> Quote:
        """Return the current best bid/ask for ``symbol``."""
        bare = from_wire(symbol)
        wire = to_wire(bare)

        if _looks_like_crypto(bare):
            body = self._transport.get(
                f"{self._data_url}/v1beta3/crypto/us/latest/quotes",
                params={"symbols": wire},
            )
            entry = (body.get("quotes") or {}).get(wire)
        else:
            body = self._transport.get(
                f"{self._data_url}/v2/stocks/{wire}/quotes/latest"
            )
            entry = body.get("quote")

        if not entry:
            raise InvalidAction(f"Alpaca does not quote '{bare}'")

        bid = Decimal(str(entry.get("bp", 0)))
        ask = Decimal(str(entry.get("ap", 0)))
        if bid <= 0 or ask <= 0:
            raise InvalidAction(f"Alpaca returned no usable quote for '{bare}'")

        return Quote(symbol=bare, bid=bid, ask=ask, timestamp=_parse_time(entry.get("t")))

    def candles(self, symbol: str, *, interval: str = "1h", limit: int = 100) -> list[Candle]:
        """Return recent OHLCV bars, oldest first."""
        bare = from_wire(symbol)
        wire = to_wire(bare)
        timeframe = TIMEFRAMES.get(interval, "1Hour")
        start = datetime.now(UTC) - _interval_delta(interval) * (limit + 2)

        if _looks_like_crypto(bare):
            body = self._transport.get(
                f"{self._data_url}/v1beta3/crypto/us/bars",
                params={
                    "symbols": wire,
                    "timeframe": timeframe,
                    "start": start.isoformat(),
                    "limit": limit,
                },
            )
            raw = (body.get("bars") or {}).get(wire, [])
        else:
            body = self._transport.get(
                f"{self._data_url}/v2/stocks/{wire}/bars",
                params={
                    "timeframe": timeframe,
                    "start": start.isoformat(),
                    "limit": limit,
                },
            )
            raw = body.get("bars", [])

        candles = [
            Candle(
                symbol=bare,
                timestamp=_parse_time(bar.get("t")),
                open=Decimal(str(bar.get("o", 0))),
                high=Decimal(str(bar.get("h", 0))),
                low=Decimal(str(bar.get("l", 0))),
                close=Decimal(str(bar.get("c", 0))),
                volume=Decimal(str(bar.get("v", 0))),
            )
            for bar in raw
        ]
        candles.sort(key=lambda c: c.timestamp)
        return candles[-limit:]


class AlpacaVenue:
    """Places real orders on Alpaca."""

    name = "alpaca"

    def __init__(
        self,
        transport: Transport,
        *,
        environment: Environment,
        data_url: str = DATA_API_URL,
    ) -> None:
        if environment not in (Environment.TESTNET, Environment.MAINNET):
            raise InvalidAction(
                f"Alpaca cannot run in the {environment.value} environment"
            )
        self._transport = transport
        self._environment = environment
        self._base = api_url(environment)
        self.market_data = AlpacaMarketData(
            transport, environment=environment, data_url=data_url
        )

    @property
    def environment(self) -> Environment:
        """Which Alpaca world this venue trades in."""
        return self._environment

    # --- Reads -----------------------------------------------------------

    def account_state(self) -> AccountState:
        """Return cash and open positions as Alpaca reports them."""
        account = self._transport.get(f"{self._base}/v2/account")
        raw_positions = self._transport.get(f"{self._base}/v2/positions") or []

        positions: list[Position] = []
        for entry in raw_positions:
            size = Decimal(str(entry.get("qty", "0")))
            if size == 0:
                continue
            positions.append(
                Position(
                    symbol=from_wire(str(entry.get("symbol", ""))),
                    # Alpaca signs quantity; "short" also appears in `side`.
                    side=Side.BUY if size > 0 else Side.SELL,
                    size=abs(size),
                    entry_price=Decimal(str(entry.get("avg_entry_price", "0"))),
                    mark_price=Decimal(str(entry.get("current_price", "0") or "0")),
                    leverage=1,
                    unrealised_pnl=Decimal(str(entry.get("unrealized_pl", "0") or "0")),
                )
            )

        equity = Decimal(str(account.get("equity", "0")))
        buying_power = Decimal(str(account.get("cash", "0")))
        return AccountState(
            environment=self._environment,
            balances=[
                Balance(
                    currency=str(account.get("currency", "USD")),
                    total=equity,
                    available=max(Decimal(0), buying_power),
                )
            ],
            positions=positions,
        )

    # --- Writes ----------------------------------------------------------

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Submit ``request`` to Alpaca.

        The caller has already run the risk checks; what this method enforces is
        Alpaca's own shape — rounding to a tradable increment, and refusing to
        request leverage the venue will not give.
        """
        instrument = self.market_data.instrument(request.symbol)
        size = instrument.round_size(abs(request.size))
        if size <= 0:
            return self._refusal(
                request, f"Size rounds to zero at the {instrument.size_step} step"
            )
        if request.leverage > 1:
            return self._refusal(
                request, "Alpaca positions are unleveraged; request leverage 1"
            )

        payload: dict[str, Any] = {
            "symbol": to_wire(request.symbol),
            "qty": str(size),
            "side": request.side.value,
            "type": request.order_type.value,
            # Crypto trades around the clock, so GTC is the honest default.
            "time_in_force": "gtc",
        }
        if request.order_type is OrderType.LIMIT:
            if request.limit_price is None:
                return self._refusal(request, "A limit order needs a limit price")
            payload["limit_price"] = str(request.limit_price)
        if request.client_id:
            payload["client_order_id"] = request.client_id

        try:
            raw = self._transport.post(f"{self._base}/v2/orders", json=payload)
        except InvalidAction as exc:
            # A venue refusal is an outcome, not a crash: report it like any
            # other rejected order so the audit trail records the reason.
            return self._refusal(request, str(exc))

        return self._parse_order(request, raw)

    def close_position(self, symbol: str) -> OrderResult:
        """Flatten the open position in ``symbol``."""
        bare = from_wire(symbol)
        state = self.account_state()
        position = state.position(bare)
        if position is None:
            return OrderResult(
                accepted=False,
                symbol=bare,
                side=Side.SELL,
                environment=self._environment,
                reason=f"No open position in {bare}",
            )

        request = OrderRequest(
            symbol=bare,
            side=position.side.opposite,
            size=position.size,
            reduce_only=True,
        )
        try:
            raw = self._transport.delete(
                f"{self._base}/v2/positions/{to_wire(bare).replace('/', '%2F')}"
            )
        except InvalidAction as exc:
            return self._refusal(request, str(exc))

        return self._parse_order(request, raw)

    # --- Internals -------------------------------------------------------

    def _refusal(self, request: OrderRequest, reason: str) -> OrderResult:
        """Build a rejected result for ``request``."""
        return OrderResult(
            accepted=False,
            symbol=from_wire(request.symbol),
            side=request.side,
            environment=self._environment,
            reason=reason,
            client_id=request.client_id,
        )

    def _parse_order(self, request: OrderRequest, raw: Any) -> OrderResult:
        """Translate an Alpaca order response into an :class:`OrderResult`.

        A newly accepted order is usually ``new`` with nothing filled yet, which
        is still a success — the order is working. Only a terminal failure state
        counts as a rejection, so a resting order is not reported as a loss.
        """
        if not isinstance(raw, dict) or not raw.get("id"):
            return self._refusal(request, "Alpaca returned no order")

        status = str(raw.get("status", "")).lower()
        if status in ("rejected", "canceled", "expired"):
            return self._refusal(request, f"Alpaca {status} the order")

        filled = Decimal(str(raw.get("filled_qty", "0") or "0"))
        average = Decimal(str(raw.get("filled_avg_price", "0") or "0"))

        return OrderResult(
            accepted=True,
            symbol=from_wire(str(raw.get("symbol", request.symbol))),
            side=request.side,
            filled_size=filled,
            average_price=average,
            order_id=str(raw.get("id")),
            client_id=raw.get("client_order_id") or request.client_id,
            environment=self._environment,
            raw=raw,
        )


def _parse_time(value: Any) -> datetime:
    """Return a timezone-aware timestamp from an Alpaca RFC-3339 string."""
    if not value:
        return datetime.now(UTC)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _interval_delta(interval: str) -> timedelta:
    """Return the wall-clock length of a candle interval."""
    units = {"m": "minutes", "h": "hours", "d": "days"}
    suffix = interval[-1]
    if suffix not in units or not interval[:-1].isdigit():
        return timedelta(hours=1)
    return timedelta(**{units[suffix]: int(interval[:-1])})
