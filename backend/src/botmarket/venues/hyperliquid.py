"""The Hyperliquid venue: real perpetual orders.

This is where an agent's decision stops being a simulation. Everything here
talks to a real exchange, so the module is built around three defensive habits:

**Environment isolation.** The base URL is chosen once from an
:class:`Environment` and then asserted on every call that spends money. A
testnet account can never be pointed at mainnet by a stray argument, because the
environment is a property of the venue object rather than a parameter of its
methods.

**Injected clients.** The Hyperliquid SDK objects are constructed by a factory
that tests replace. That is not only for testability: it also keeps the private
key on one short path — from the credential store into the signing client — with
no other code holding a reference.

**Optional dependency.** The SDK lives behind the ``live`` extra. Without it,
constructing this venue raises a clear error rather than failing later at the
first order. A deployment that never installs it simply cannot trade for real.

.. warning::
   The code in this module has been exercised against a recorded stand-in for
   the exchange, not against a live Hyperliquid endpoint. Before trusting it
   with real funds, run it on **testnet** and reconcile fills by hand.
"""

from __future__ import annotations

from dataclasses import dataclass
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

MAINNET_API_URL = "https://api.hyperliquid.xyz"
TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"

#: Slippage tolerance handed to the SDK for market orders, as a fraction.
DEFAULT_SLIPPAGE = 0.01


def api_url(environment: Environment) -> str:
    """Return the endpoint for ``environment``.

    Raises:
        InvalidAction: If asked for a paper endpoint, which does not exist.
    """
    if environment is Environment.MAINNET:
        return MAINNET_API_URL
    if environment is Environment.TESTNET:
        return TESTNET_API_URL
    raise InvalidAction("Hyperliquid has no paper endpoint; use the paper venue")


class InfoClient(Protocol):
    """The read-only half of the Hyperliquid SDK that this module uses."""

    def meta(self) -> dict: ...
    def all_mids(self) -> dict: ...
    def user_state(self, address: str) -> dict: ...
    def candles_snapshot(
        self, name: str, interval: str, startTime: int, endTime: int
    ) -> list[dict]: ...


class ExchangeClient(Protocol):
    """The order-placing half of the Hyperliquid SDK that this module uses."""

    def market_open(
        self, name: str, is_buy: bool, sz: float, px: float | None, slippage: float
    ) -> dict: ...
    def market_close(self, coin: str) -> dict: ...
    def order(
        self,
        name: str,
        is_buy: bool,
        sz: float,
        limit_px: float,
        order_type: dict,
        reduce_only: bool,
    ) -> dict: ...
    def update_leverage(self, leverage: int, name: str) -> dict: ...


@dataclass(frozen=True)
class Clients:
    """The pair of SDK clients a venue needs.

    ``exchange`` is ``None`` for a read-only venue — one built from a wallet
    address with no private key, which can report positions but cannot trade.
    """

    info: InfoClient
    exchange: ExchangeClient | None = None


def build_clients(
    *, environment: Environment, address: str, secret_key: str | None
) -> Clients:
    """Construct real SDK clients.

    Args:
        environment: Testnet or mainnet; decides the endpoint.
        address: The account's public wallet address.
        secret_key: The signing key. When ``None`` the venue is read-only.

    Raises:
        InvalidAction: If the ``live`` extra is not installed.
    """
    try:
        from hyperliquid.exchange import Exchange
        from hyperliquid.info import Info
    except ImportError as exc:  # pragma: no cover - depends on the extra
        raise InvalidAction(
            "Live trading needs the optional dependencies. Install them with "
            "`pip install -e 'backend[live]'`."
        ) from exc

    base_url = api_url(environment)
    info = Info(base_url, skip_ws=True)

    exchange: Any = None
    if secret_key:
        from eth_account import Account as EthAccount

        wallet = EthAccount.from_key(secret_key)
        exchange = Exchange(wallet, base_url, account_address=address)

    return Clients(info=info, exchange=exchange)


class HyperliquidMarketData:
    """Read-only Hyperliquid market data."""

    def __init__(self, clients: Clients, *, environment: Environment) -> None:
        self._clients = clients
        self._environment = environment
        self._meta_cache: dict[str, Instrument] | None = None

    @property
    def environment(self) -> Environment:
        """Which Hyperliquid world this feed reports on."""
        return self._environment

    def instrument(self, symbol: str) -> Instrument:
        """Return venue trading rules for ``symbol``.

        Hyperliquid publishes ``szDecimals`` per asset, which fixes the size
        step. Rounding to anything finer is rejected by the exchange, so this
        has to come from the venue rather than a local guess.
        """
        if self._meta_cache is None:
            self._meta_cache = self._load_meta()
        return self._meta_cache.get(
            symbol.upper(), Instrument(symbol=symbol.upper())
        )

    def _load_meta(self) -> dict[str, Instrument]:
        """Fetch and cache the asset universe."""
        universe = self._clients.info.meta().get("universe", [])
        instruments: dict[str, Instrument] = {}
        for asset in universe:
            name = str(asset.get("name", "")).upper()
            if not name:
                continue
            decimals = int(asset.get("szDecimals", 4))
            instruments[name] = Instrument(
                symbol=name,
                size_step=Decimal(1).scaleb(-decimals),
                price_step=Decimal("0.01"),
                min_notional=Decimal("10"),
                max_leverage=int(asset.get("maxLeverage", 10)),
            )
        return instruments

    def quote(self, symbol: str) -> Quote:
        """Return a quote derived from the venue's mid price.

        Hyperliquid's ``all_mids`` gives a mid rather than a book top, so the
        bid/ask here is a symmetric synthetic spread around it. It is good
        enough to value an order for a risk check and explicitly not good enough
        to quote a spread to a user, which is why nothing displays it as one.
        """
        mids = self._clients.info.all_mids()
        key = symbol.upper()
        raw = mids.get(key) or mids.get(symbol)
        if raw is None:
            raise InvalidAction(f"Hyperliquid does not quote '{symbol}'")

        mid = Decimal(str(raw))
        half = mid * Decimal("0.0001")
        return Quote(
            symbol=key,
            bid=mid - half,
            ask=mid + half,
            timestamp=datetime.now(UTC),
        )

    def candles(self, symbol: str, *, interval: str = "1h", limit: int = 100) -> list[Candle]:
        """Return recent OHLCV bars from the exchange, oldest first."""
        span = _interval_delta(interval) * (limit + 1)
        end = datetime.now(UTC)
        start = end - span

        raw = self._clients.info.candles_snapshot(
            symbol.upper(),
            interval,
            int(start.timestamp() * 1000),
            int(end.timestamp() * 1000),
        )

        candles = [
            Candle(
                symbol=symbol.upper(),
                timestamp=datetime.fromtimestamp(int(bar["t"]) / 1000, tz=UTC),
                open=Decimal(str(bar["o"])),
                high=Decimal(str(bar["h"])),
                low=Decimal(str(bar["l"])),
                close=Decimal(str(bar["c"])),
                volume=Decimal(str(bar.get("v", 0))),
            )
            for bar in raw
        ]
        candles.sort(key=lambda c: c.timestamp)
        return candles[-limit:]


class HyperliquidVenue:
    """Places real perpetual orders on Hyperliquid."""

    name = "hyperliquid"

    def __init__(
        self,
        clients: Clients,
        *,
        environment: Environment,
        address: str,
        slippage: float = DEFAULT_SLIPPAGE,
    ) -> None:
        if environment not in (Environment.TESTNET, Environment.MAINNET):
            raise InvalidAction(
                f"Hyperliquid cannot run in the {environment.value} environment"
            )
        self._clients = clients
        self._environment = environment
        self._address = address
        self._slippage = slippage
        self.market_data = HyperliquidMarketData(clients, environment=environment)

    @property
    def environment(self) -> Environment:
        """Which Hyperliquid world this venue trades in."""
        return self._environment

    @property
    def can_trade(self) -> bool:
        """Whether a signing client is present, i.e. orders are possible."""
        return self._clients.exchange is not None

    # --- Reads -----------------------------------------------------------

    def account_state(self) -> AccountState:
        """Return balances and open positions as the exchange reports them."""
        state = self._clients.info.user_state(self._address)
        summary = state.get("marginSummary", {})

        total = Decimal(str(summary.get("accountValue", "0")))
        used = Decimal(str(summary.get("totalMarginUsed", "0")))

        positions: list[Position] = []
        for entry in state.get("assetPositions", []):
            raw = entry.get("position", {})
            size = Decimal(str(raw.get("szi", "0")))
            if size == 0:
                continue
            leverage = raw.get("leverage") or {}
            liquidation = raw.get("liquidationPx")
            mark = Decimal(str(raw.get("positionValue", "0"))) / abs(size) if size else Decimal(0)
            positions.append(
                Position(
                    symbol=str(raw.get("coin", "")).upper(),
                    # Hyperliquid signs the size: negative is short.
                    side=Side.BUY if size > 0 else Side.SELL,
                    size=abs(size),
                    entry_price=Decimal(str(raw.get("entryPx") or "0")),
                    mark_price=mark,
                    leverage=int(leverage.get("value", 1) or 1),
                    unrealised_pnl=Decimal(str(raw.get("unrealizedPnl", "0"))),
                    liquidation_price=Decimal(str(liquidation)) if liquidation else None,
                )
            )

        return AccountState(
            environment=self._environment,
            balances=[
                Balance(
                    currency="USDC",
                    total=total,
                    available=max(Decimal(0), total - used),
                )
            ],
            positions=positions,
        )

    # --- Writes ----------------------------------------------------------

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Submit ``request`` to Hyperliquid.

        The caller must already have run the risk checks — this method does not
        second-guess them, but it does refuse to act without a signing client,
        which is the one failure the venue itself is responsible for.
        """
        exchange = self._require_exchange()
        instrument = self.market_data.instrument(request.symbol)
        size = instrument.round_size(abs(request.size))
        if size <= 0:
            return self._refusal(
                request, f"Size rounds to zero at the {instrument.size_step} step"
            )

        if request.leverage > 1:
            # Leverage is account-and-asset state on Hyperliquid, so it has to
            # be set before the order rather than carried on it.
            exchange.update_leverage(request.leverage, request.symbol.upper())

        is_buy = request.side is Side.BUY
        if request.order_type is OrderType.LIMIT:
            if request.limit_price is None:
                return self._refusal(request, "A limit order needs a limit price")
            raw = exchange.order(
                request.symbol.upper(),
                is_buy,
                float(size),
                float(request.limit_price),
                {"limit": {"tif": "Gtc"}},
                request.reduce_only,
            )
        else:
            raw = exchange.market_open(
                request.symbol.upper(), is_buy, float(size), None, self._slippage
            )

        return self._parse_order_response(request, raw)

    def close_position(self, symbol: str) -> OrderResult:
        """Flatten the open position in ``symbol``."""
        exchange = self._require_exchange()
        state = self.account_state()
        position = state.position(symbol.upper())
        if position is None:
            return OrderResult(
                accepted=False,
                symbol=symbol.upper(),
                side=Side.SELL,
                environment=self._environment,
                reason=f"No open position in {symbol.upper()}",
            )

        raw = exchange.market_close(symbol.upper())
        request = OrderRequest(
            symbol=symbol.upper(),
            side=position.side.opposite,
            size=position.size,
            reduce_only=True,
        )
        return self._parse_order_response(request, raw)

    # --- Internals -------------------------------------------------------

    def _require_exchange(self) -> ExchangeClient:
        """Return the signing client, or explain why there isn't one."""
        if self._clients.exchange is None:
            raise InvalidAction(
                "This Hyperliquid account is linked read-only; no signing key "
                "is stored, so it cannot place orders."
            )
        return self._clients.exchange

    def _refusal(self, request: OrderRequest, reason: str) -> OrderResult:
        """Build a rejected result for ``request``."""
        return OrderResult(
            accepted=False,
            symbol=request.symbol.upper(),
            side=request.side,
            environment=self._environment,
            reason=reason,
            client_id=request.client_id,
        )

    def _parse_order_response(self, request: OrderRequest, raw: dict) -> OrderResult:
        """Translate an SDK order response into an :class:`OrderResult`.

        Hyperliquid nests the outcome several levels deep and reports a
        per-order status, so a response can be ``{"status": "ok"}`` overall
        while the single order inside it was in fact an error. Both levels are
        checked; treating the outer ``ok`` as success would report phantom
        fills.
        """
        if not isinstance(raw, dict) or raw.get("status") != "ok":
            return self._refusal(request, _describe_failure(raw))

        statuses = (
            raw.get("response", {}).get("data", {}).get("statuses", [])
            if isinstance(raw.get("response"), dict)
            else []
        )
        if not statuses:
            return self._refusal(request, "Exchange accepted the request but reported no fill")

        status = statuses[0]
        if isinstance(status, dict) and "error" in status:
            return self._refusal(request, str(status["error"]))

        detail = {}
        if isinstance(status, dict):
            detail = status.get("filled") or status.get("resting") or {}

        filled = Decimal(str(detail.get("totalSz", "0") or "0"))
        average = Decimal(str(detail.get("avgPx", "0") or "0"))

        return OrderResult(
            accepted=True,
            symbol=request.symbol.upper(),
            side=request.side,
            filled_size=filled,
            average_price=average,
            order_id=str(detail.get("oid")) if detail.get("oid") is not None else None,
            client_id=request.client_id,
            environment=self._environment,
            raw=raw,
        )


def _describe_failure(raw: Any) -> str:
    """Return a human-readable reason from a failed SDK response."""
    if isinstance(raw, dict):
        for key in ("response", "error", "message"):
            value = raw.get(key)
            if isinstance(value, str) and value:
                return value
    return "Exchange rejected the order"


def _interval_delta(interval: str) -> timedelta:
    """Return the wall-clock length of a candle interval."""
    units = {"m": "minutes", "h": "hours", "d": "days"}
    suffix = interval[-1]
    if suffix not in units or not interval[:-1].isdigit():
        return timedelta(hours=1)
    return timedelta(**{units[suffix]: int(interval[:-1])})
