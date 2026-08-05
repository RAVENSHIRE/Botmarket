"""Tests for the venue adapters.

The paper venue is exercised directly. The Hyperliquid venue is driven by fake
SDK clients: the network is unreachable from CI, and more importantly the point
of these tests is the *translation* — signed sizes, nested response envelopes,
environment isolation — which a live endpoint would only obscure.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from botmarket.db.models import VenueAccount
from botmarket.domain.errors import InvalidAction
from botmarket.domain.venue import (
    Environment,
    ExecutionVenue,
    MarketDataFeed,
    OrderRequest,
    OrderType,
    Side,
)
from botmarket.venues import hyperliquid as hl
from botmarket.venues.paper import PaperMarketData, PaperVenue


@pytest.fixture
def paper_account(db):
    """A funded paper account."""
    from botmarket.db.models import Agent

    agent = Agent(name="Trader", agent_type="trader")
    db.add(agent)
    db.flush()
    account = VenueAccount(
        agent_id=agent.id,
        venue="paper",
        environment="paper",
        label="paper",
        paper_balance=10_000.0,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@pytest.fixture
def paper(db, paper_account):
    """A paper venue over that account."""
    return PaperVenue(db, paper_account)


def buy(symbol="BTC", size="0.01", **kw):
    """Build a market buy."""
    return OrderRequest(symbol=symbol, side=Side.BUY, size=Decimal(size), **kw)


def sell(symbol="BTC", size="0.01", **kw):
    """Build a market sell."""
    return OrderRequest(symbol=symbol, side=Side.SELL, size=Decimal(size), **kw)


# --- Protocol conformance ------------------------------------------------


def test_both_venues_satisfy_the_protocol(db, paper_account):
    """The abstraction is only worth having if both sides really implement it."""
    assert isinstance(PaperVenue(db, paper_account), ExecutionVenue)
    assert isinstance(PaperMarketData(), MarketDataFeed)

    venue = hl.HyperliquidVenue(
        hl.Clients(info=FakeInfo()), environment=Environment.TESTNET, address="0xabc"
    )
    assert isinstance(venue, ExecutionVenue)
    assert isinstance(venue.market_data, MarketDataFeed)


# --- Paper market data ---------------------------------------------------


def test_paper_prices_are_deterministic():
    """A test asserting on a factor needs the prices under it to hold still.

    Timestamps are anchored to ``now`` and so differ between calls by design;
    the price series is the part that must not move.
    """
    first = PaperMarketData().candles("BTC", limit=50)
    second = PaperMarketData().candles("BTC", limit=50)
    assert [c.close for c in first] == [c.close for c in second]
    assert [c.volume for c in first] == [c.volume for c in second]


def test_different_symbols_get_different_series():
    btc = [c.close for c in PaperMarketData().candles("BTC", limit=30)]
    eth = [c.close for c in PaperMarketData().candles("ETH", limit=30)]
    assert btc != eth


def test_paper_candles_are_chronological():
    bars = PaperMarketData().candles("ETH", limit=40)
    assert len(bars) == 40
    assert [b.timestamp for b in bars] == sorted(b.timestamp for b in bars)


def test_paper_quote_brackets_the_mid():
    quote = PaperMarketData().quote("BTC")
    assert quote.bid < quote.mid < quote.ask
    assert quote.spread_bps > 0


# --- Paper execution -----------------------------------------------------


def test_buy_opens_a_position(paper, paper_account):
    result = paper.place_order(buy())
    assert result.accepted
    assert result.filled_size == Decimal("0.01")

    state = paper.account_state()
    position = state.position("BTC")
    assert position is not None
    assert position.side is Side.BUY
    assert position.size == Decimal("0.01")


def test_buying_twice_averages_the_entry(paper):
    paper.place_order(buy(size="0.01"))
    paper.place_order(buy(size="0.03"))
    position = paper.account_state().position("BTC")
    assert position.size == Decimal("0.04")


def test_selling_closes_and_books_pnl(paper, paper_account):
    paper.place_order(buy(size="0.02"))
    opening = paper_account.paper_balance

    paper.place_order(sell(size="0.02"))
    assert paper.account_state().position("BTC") is None
    # Crossing the spread twice costs money, so a flat round trip cannot profit.
    assert paper_account.paper_balance <= opening


def test_an_oversized_sell_flips_the_position(paper):
    paper.place_order(buy(size="0.01"))
    paper.place_order(sell(size="0.03"))
    position = paper.account_state().position("BTC")
    assert position.side is Side.SELL
    assert position.size == Decimal("0.02")


def test_reduce_only_without_a_position_is_refused(paper):
    result = paper.place_order(sell(reduce_only=True))
    assert not result.accepted
    assert "no opposing position" in result.reason.lower()


def test_reduce_only_cannot_flip_a_position(paper):
    """Reducing must never open the other side by accident."""
    paper.place_order(buy(size="0.01"))
    paper.place_order(sell(size="0.05", reduce_only=True))
    assert paper.account_state().position("BTC") is None


def test_close_position_flattens(paper):
    paper.place_order(buy(size="0.02"))
    result = paper.close_position("BTC")
    assert result.accepted
    assert paper.account_state().position("BTC") is None


def test_closing_nothing_is_refused(paper):
    result = paper.close_position("ETH")
    assert not result.accepted
    assert "no open position" in result.reason.lower()


def test_dust_below_the_size_step_is_refused(paper):
    result = paper.place_order(buy(size="0.000001"))
    assert not result.accepted
    assert "rounds to zero" in result.reason


def test_slippage_works_against_the_taker(paper):
    """A venue that filled at the mid would flatter every strategy."""
    quote = PaperMarketData().quote("BTC")
    bought = paper.place_order(buy(size="0.01"))
    assert bought.average_price >= quote.ask

    sold = paper.place_order(sell(size="0.02"))
    assert sold.average_price <= quote.bid


def test_limit_orders_fill_at_the_limit(paper):
    result = paper.place_order(
        buy(size="0.01", order_type=OrderType.LIMIT, limit_price=Decimal("50000"))
    )
    assert result.average_price == Decimal("50000")


def test_available_margin_falls_as_positions_open(paper):
    before = paper.account_state().balance().available
    paper.place_order(buy(size="0.05"))
    assert paper.account_state().balance().available < before


def test_losses_accumulate_into_the_daily_counter(paper, paper_account):
    """The daily loss cap can only work if losses are actually recorded."""
    paper.place_order(buy(size="0.02"))
    paper.place_order(sell(size="0.02"))
    assert paper_account.realised_pnl_today > 0


# --- Hyperliquid fakes ---------------------------------------------------


class FakeInfo:
    """Stands in for the SDK's read-only client."""

    def __init__(self, *, mids=None, state=None, bars=None):
        self._mids = mids or {"BTC": "65000.0", "ETH": "3200.0"}
        self._state = state or {
            "marginSummary": {"accountValue": "5000", "totalMarginUsed": "1000"},
            "assetPositions": [],
        }
        self._bars = bars or []

    def meta(self):
        return {
            "universe": [
                {"name": "BTC", "szDecimals": 3, "maxLeverage": 40},
                {"name": "ETH", "szDecimals": 2, "maxLeverage": 25},
            ]
        }

    def all_mids(self):
        return self._mids

    def user_state(self, address):
        return self._state

    def candles_snapshot(self, name, interval, startTime, endTime):
        return self._bars


class FakeExchange:
    """Records calls and returns canned SDK responses."""

    def __init__(self, response=None):
        self.calls: list[tuple] = []
        self._response = response or filled(sz="0.5", px="65010")

    def market_open(self, name, is_buy, sz, px, slippage):
        self.calls.append(("market_open", name, is_buy, sz, slippage))
        return self._response

    def market_close(self, coin):
        self.calls.append(("market_close", coin))
        return self._response

    def order(self, name, is_buy, sz, limit_px, order_type, reduce_only):
        self.calls.append(("order", name, is_buy, sz, limit_px, reduce_only))
        return self._response

    def update_leverage(self, leverage, name):
        self.calls.append(("update_leverage", leverage, name))
        return {"status": "ok"}


def filled(*, sz: str, px: str, oid: int = 42) -> dict:
    """A successful SDK order response."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {"statuses": [{"filled": {"totalSz": sz, "avgPx": px, "oid": oid}}]},
        },
    }


def venue(*, info=None, exchange=None, environment=Environment.TESTNET):
    """Build a Hyperliquid venue over fakes."""
    return hl.HyperliquidVenue(
        hl.Clients(info=info or FakeInfo(), exchange=exchange),
        environment=environment,
        address="0xabc",
    )


# --- Hyperliquid behaviour ----------------------------------------------


def test_environment_picks_the_endpoint():
    assert hl.api_url(Environment.TESTNET) == hl.TESTNET_API_URL
    assert hl.api_url(Environment.MAINNET) == hl.MAINNET_API_URL


def test_paper_has_no_hyperliquid_endpoint():
    with pytest.raises(InvalidAction):
        hl.api_url(Environment.PAPER)


def test_hyperliquid_refuses_to_run_as_paper():
    with pytest.raises(InvalidAction):
        venue(environment=Environment.PAPER)


def test_instrument_rules_come_from_the_venue():
    """Rounding to a finer step than the exchange allows gets orders rejected."""
    instrument = venue().market_data.instrument("BTC")
    assert instrument.size_step == Decimal("0.001")
    assert instrument.max_leverage == 40


def test_unknown_symbols_are_reported():
    with pytest.raises(InvalidAction, match="does not quote"):
        venue().market_data.quote("DOGE")


def test_positions_decode_the_signed_size():
    """Hyperliquid signs size to mean direction; a missed sign inverts a book."""
    state = {
        "marginSummary": {"accountValue": "5000", "totalMarginUsed": "1000"},
        "assetPositions": [
            {
                "position": {
                    "coin": "BTC",
                    "szi": "-0.5",
                    "entryPx": "64000",
                    "positionValue": "32000",
                    "leverage": {"value": 3},
                    "unrealizedPnl": "-120.5",
                    "liquidationPx": "70000",
                }
            }
        ],
    }
    account = venue(info=FakeInfo(state=state)).account_state()
    position = account.position("BTC")
    assert position.side is Side.SELL
    assert position.size == Decimal("0.5")
    assert position.leverage == 3
    assert position.liquidation_price == Decimal("70000")


def test_zero_size_positions_are_dropped():
    state = {
        "marginSummary": {"accountValue": "1", "totalMarginUsed": "0"},
        "assetPositions": [{"position": {"coin": "BTC", "szi": "0"}}],
    }
    assert venue(info=FakeInfo(state=state)).account_state().positions == []


def test_available_never_goes_negative():
    state = {
        "marginSummary": {"accountValue": "100", "totalMarginUsed": "500"},
        "assetPositions": [],
    }
    assert venue(info=FakeInfo(state=state)).account_state().balance().available == Decimal(0)


def test_a_read_only_account_cannot_trade():
    with pytest.raises(InvalidAction, match="read-only"):
        venue().place_order(buy(size="0.5"))


def test_market_order_is_forwarded_and_parsed():
    exchange = FakeExchange()
    result = venue(exchange=exchange).place_order(buy(size="0.5"))

    assert result.accepted
    assert result.filled_size == Decimal("0.5")
    assert result.average_price == Decimal("65010")
    assert result.order_id == "42"
    assert result.environment is Environment.TESTNET
    assert ("market_open", "BTC", True, 0.5, hl.DEFAULT_SLIPPAGE) in exchange.calls


def test_leverage_is_set_before_the_order():
    """On Hyperliquid leverage is account state, not an order field."""
    exchange = FakeExchange()
    venue(exchange=exchange).place_order(buy(size="0.5", leverage=5))
    assert exchange.calls[0] == ("update_leverage", 5, "BTC")


def test_size_is_rounded_to_the_venue_step():
    exchange = FakeExchange()
    venue(exchange=exchange).place_order(buy(size="0.5009"))
    assert exchange.calls[0][3] == 0.5


def test_a_size_that_rounds_away_is_refused():
    exchange = FakeExchange()
    result = venue(exchange=exchange).place_order(buy(size="0.0001"))
    assert not result.accepted
    assert exchange.calls == []


def test_limit_orders_pass_the_price_through():
    exchange = FakeExchange()
    venue(exchange=exchange).place_order(
        buy(size="0.5", order_type=OrderType.LIMIT, limit_price=Decimal("60000"))
    )
    assert exchange.calls[0] == ("order", "BTC", True, 0.5, 60000.0, False)


def test_a_limit_order_without_a_price_is_refused():
    exchange = FakeExchange()
    result = venue(exchange=exchange).place_order(
        buy(size="0.5", order_type=OrderType.LIMIT)
    )
    assert not result.accepted
    assert "needs a limit price" in result.reason


def test_a_nested_error_is_not_read_as_a_fill():
    """The envelope says ok while the order inside it failed."""
    response = {
        "status": "ok",
        "response": {"data": {"statuses": [{"error": "Insufficient margin"}]}},
    }
    result = venue(exchange=FakeExchange(response)).place_order(buy(size="0.5"))
    assert not result.accepted
    assert result.reason == "Insufficient margin"
    assert result.filled_size == Decimal(0)


def test_an_outright_failure_is_reported():
    result = venue(exchange=FakeExchange({"status": "err", "response": "nope"})).place_order(
        buy(size="0.5")
    )
    assert not result.accepted
    assert result.reason == "nope"


def test_an_empty_status_list_is_not_a_fill():
    response = {"status": "ok", "response": {"data": {"statuses": []}}}
    result = venue(exchange=FakeExchange(response)).place_order(buy(size="0.5"))
    assert not result.accepted


def test_closing_with_no_position_is_refused():
    exchange = FakeExchange()
    result = venue(exchange=exchange).close_position("BTC")
    assert not result.accepted
    assert exchange.calls == []


def test_closing_a_position_calls_market_close():
    state = {
        "marginSummary": {"accountValue": "5000", "totalMarginUsed": "100"},
        "assetPositions": [
            {
                "position": {
                    "coin": "BTC",
                    "szi": "0.5",
                    "entryPx": "64000",
                    "positionValue": "32000",
                    "leverage": {"value": 1},
                    "unrealizedPnl": "10",
                }
            }
        ],
    }
    exchange = FakeExchange()
    result = venue(info=FakeInfo(state=state), exchange=exchange).close_position("BTC")
    assert result.accepted
    assert ("market_close", "BTC") in exchange.calls
    # Closing a long is a sell.
    assert result.side is Side.SELL


def test_candles_are_sorted_and_trimmed():
    bars = [
        {"t": 3000, "o": "3", "h": "3", "l": "3", "c": "3", "v": "1"},
        {"t": 1000, "o": "1", "h": "1", "l": "1", "c": "1", "v": "1"},
        {"t": 2000, "o": "2", "h": "2", "l": "2", "c": "2", "v": "1"},
    ]
    got = venue(info=FakeInfo(bars=bars)).market_data.candles("BTC", limit=2)
    assert [float(c.close) for c in got] == [2.0, 3.0]


def test_a_closed_symbol_can_be_reopened(paper):
    """Closing zeroes the position row; reopening must revive it.

    The row is unique per (account, symbol), so an implementation that treats a
    flat symbol as "never traded" tries to insert a second row and makes the
    symbol permanently untradable.
    """
    paper.place_order(buy(size="0.01"))
    paper.close_position("BTC")
    assert paper.account_state().position("BTC") is None

    result = paper.place_order(buy(size="0.02"))
    assert result.accepted
    reopened = paper.account_state().position("BTC")
    assert reopened is not None
    assert reopened.size == Decimal("0.02")
    assert reopened.side is Side.BUY


def test_a_closed_symbol_can_be_reopened_on_the_other_side(paper):
    paper.place_order(buy(size="0.01"))
    paper.close_position("BTC")
    paper.place_order(sell(size="0.01"))
    reopened = paper.account_state().position("BTC")
    assert reopened.side is Side.SELL


def test_reopening_does_not_inherit_the_old_entry_price(paper):
    """A revived row must be a new position, not a resumed one."""
    first = paper.place_order(buy(size="0.01"))
    paper.close_position("BTC")
    paper.place_order(
        buy(size="0.01", order_type=OrderType.LIMIT, limit_price=Decimal("1000"))
    )
    reopened = paper.account_state().position("BTC")
    assert reopened.entry_price == Decimal("1000")
    assert reopened.entry_price != first.average_price


# --- Contract with the real SDK -----------------------------------------

sdk = pytest.importorskip(
    "hyperliquid.info",
    reason="the 'live' extra is not installed",
)


def test_the_adapter_matches_the_installed_sdk():
    """Guard the seam between our fakes and the real Hyperliquid SDK.

    The fakes above are only meaningful if they mirror the real thing, and the
    exchange itself is unreachable from CI. Checking the installed SDK's
    signatures catches the realistic failure — a version bump renaming or
    reordering a parameter — which the fakes alone would happily hide.
    """
    import inspect

    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info

    def params(fn) -> list[str]:
        return [p for p in inspect.signature(fn).parameters if p != "self"]

    def required(fn) -> list[str]:
        """Parameters with no default — the ones a caller must supply."""
        return [
            name
            for name, p in inspect.signature(fn).parameters.items()
            if name != "self" and p.default is inspect.Parameter.empty
        ]

    # Constructors, as botmarket.venues.hyperliquid.build_clients calls them.
    assert "skip_ws" in params(Info.__init__)
    exchange_args = params(Exchange.__init__)
    assert exchange_args[0] == "wallet"
    assert exchange_args[1] == "base_url"
    assert "account_address" in exchange_args

    # Read methods, called positionally by HyperliquidMarketData.
    assert params(Info.candles_snapshot)[:4] == ["name", "interval", "startTime", "endTime"]
    # The adapter calls these with no arguments, so nothing may be required.
    assert required(Info.meta) == []
    assert required(Info.all_mids) == []
    assert required(Info.user_state) == ["address"]

    # Order methods, called positionally by HyperliquidVenue.place_order.
    assert params(Exchange.market_open)[:5] == ["name", "is_buy", "sz", "px", "slippage"]
    assert params(Exchange.order)[:6] == [
        "name", "is_buy", "sz", "limit_px", "order_type", "reduce_only",
    ]
    assert params(Exchange.update_leverage)[:2] == ["leverage", "name"]
    assert params(Exchange.market_close)[0] == "coin"
