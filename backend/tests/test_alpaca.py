"""Tests for the Alpaca venue adapter.

Driven by a fake transport. The point of these tests is the translation Alpaca
needs and Hyperliquid does not — paired symbols, signed quantities, "their paper
is our testnet", and no leverage — plus the refusal paths, which is where a
broker adapter usually goes wrong.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from botmarket.domain.errors import InvalidAction
from botmarket.domain.venue import (
    Environment,
    ExecutionVenue,
    MarketDataFeed,
    OrderRequest,
    OrderType,
    Side,
)
from botmarket.venues import alpaca as alp


class FakeTransport:
    """Records calls and replays canned Alpaca responses."""

    def __init__(self, *, responses: dict | None = None, fail: str | None = None):
        self.calls: list[tuple] = []
        self._responses = responses or {}
        self._fail = fail

    def _reply(self, method: str, url: str):
        """Return the canned body for ``url``.

        Longest fragment wins, so ``/v2/positions/BTC`` is not shadowed by the
        ``/v2/positions`` listing it is nested under.
        """
        if self._fail:
            raise InvalidAction(self._fail)
        matches = [f for f in self._responses if f in url]
        if not matches:
            return {}
        return self._responses[max(matches, key=len)]

    def get(self, url, *, params=None):
        self.calls.append(("GET", url, params))
        return self._reply("GET", url)

    def post(self, url, *, json):
        self.calls.append(("POST", url, json))
        return self._reply("POST", url)

    def delete(self, url):
        self.calls.append(("DELETE", url, None))
        return self._reply("DELETE", url)


ACCOUNT = {"equity": "25000.50", "cash": "10000.25", "currency": "USD"}

FILLED_ORDER = {
    "id": "abc-123",
    "symbol": "BTC/USD",
    "status": "filled",
    "filled_qty": "0.5",
    "filled_avg_price": "65000.00",
    "client_order_id": "cid-1",
}


def venue(*, responses=None, fail=None, environment=Environment.TESTNET):
    """Build an Alpaca venue over a fake transport."""
    transport = FakeTransport(responses=responses, fail=fail)
    return alp.AlpacaVenue(transport, environment=environment), transport


def buy(symbol="BTC", size="0.5", **kw):
    """Build a market buy."""
    return OrderRequest(symbol=symbol, side=Side.BUY, size=Decimal(size), **kw)


# --- Environment and symbols --------------------------------------------


def test_their_paper_endpoint_is_our_testnet():
    """So Alpaca inherits the same gating; mainnet stays the only risky one."""
    assert alp.api_url(Environment.TESTNET) == alp.PAPER_API_URL
    assert alp.api_url(Environment.MAINNET) == alp.LIVE_API_URL


def test_the_offline_paper_venue_is_not_alpaca():
    with pytest.raises(InvalidAction, match="no offline mode"):
        alp.api_url(Environment.PAPER)
    with pytest.raises(InvalidAction):
        venue(environment=Environment.PAPER)


def test_crypto_symbols_gain_a_quote_currency():
    assert alp.to_wire("BTC") == "BTC/USD"
    assert alp.to_wire("btc") == "BTC/USD"
    assert alp.to_wire("BTC/USD") == "BTC/USD"


def test_equity_symbols_stay_bare():
    assert alp.to_wire("AAPL") == "AAPL"


def test_symbols_round_trip():
    for symbol in ("BTC", "ETH", "AAPL"):
        assert alp.from_wire(alp.to_wire(symbol)) == symbol


def test_the_venue_satisfies_the_protocol():
    v, _ = venue()
    assert isinstance(v, ExecutionVenue)
    assert isinstance(v.market_data, MarketDataFeed)


# --- Instruments ---------------------------------------------------------


def test_alpaca_offers_no_leverage():
    """An agent asking for 5x on a broker gets a refusal, not a margin position."""
    v, _ = venue()
    assert v.market_data.instrument("BTC").max_leverage == 1
    assert v.market_data.instrument("AAPL").max_leverage == 1


def test_crypto_trades_in_finer_increments_than_equities():
    v, _ = venue()
    crypto = v.market_data.instrument("BTC").size_step
    equity = v.market_data.instrument("AAPL").size_step
    assert crypto < equity


# --- Account state -------------------------------------------------------


def test_account_state_reports_equity_and_cash():
    v, _ = venue(responses={"/v2/account": ACCOUNT, "/v2/positions": []})
    state = v.account_state()
    assert state.balance("USD").total == Decimal("25000.50")
    assert state.balance("USD").available == Decimal("10000.25")
    assert state.positions == []


def test_a_short_position_decodes_from_a_negative_quantity():
    positions = [
        {
            "symbol": "BTC/USD",
            "qty": "-0.25",
            "avg_entry_price": "64000",
            "current_price": "65000",
            "unrealized_pl": "-250",
        }
    ]
    v, _ = venue(responses={"/v2/account": ACCOUNT, "/v2/positions": positions})
    position = v.account_state().position("BTC")
    assert position.side is Side.SELL
    assert position.size == Decimal("0.25")
    assert position.leverage == 1


def test_zero_quantity_positions_are_dropped():
    positions = [{"symbol": "BTC/USD", "qty": "0"}]
    v, _ = venue(responses={"/v2/account": ACCOUNT, "/v2/positions": positions})
    assert v.account_state().positions == []


def test_negative_cash_never_reports_as_available():
    v, _ = venue(
        responses={"/v2/account": {"equity": "10", "cash": "-500"}, "/v2/positions": []}
    )
    assert v.account_state().balance("USD").available == Decimal(0)


# --- Orders --------------------------------------------------------------


def test_a_market_buy_is_forwarded_in_alpaca_s_shape():
    v, transport = venue(responses={"/v2/orders": FILLED_ORDER})
    result = v.place_order(buy())

    assert result.accepted
    assert result.filled_size == Decimal("0.5")
    assert result.average_price == Decimal("65000.00")
    assert result.order_id == "abc-123"
    assert result.environment is Environment.TESTNET

    _, url, payload = transport.calls[-1]
    assert url.endswith("/v2/orders")
    assert payload["symbol"] == "BTC/USD"
    assert payload["side"] == "buy"
    assert payload["type"] == "market"
    assert payload["time_in_force"] == "gtc"


def test_leverage_above_one_is_refused_before_sending():
    v, transport = venue(responses={"/v2/orders": FILLED_ORDER})
    result = v.place_order(buy(leverage=5))
    assert not result.accepted
    assert "unleveraged" in result.reason
    assert transport.calls == []


def test_a_size_that_rounds_away_is_refused():
    v, transport = venue(responses={"/v2/orders": FILLED_ORDER})
    result = v.place_order(buy(size="0.0000001"))
    assert not result.accepted
    assert transport.calls == []


def test_a_limit_order_carries_its_price():
    v, transport = venue(responses={"/v2/orders": FILLED_ORDER})
    v.place_order(
        buy(order_type=OrderType.LIMIT, limit_price=Decimal("60000"))
    )
    assert transport.calls[-1][2]["limit_price"] == "60000"


def test_a_limit_order_without_a_price_is_refused():
    v, transport = venue(responses={"/v2/orders": FILLED_ORDER})
    result = v.place_order(buy(order_type=OrderType.LIMIT))
    assert not result.accepted
    assert "needs a limit price" in result.reason
    assert transport.calls == []


def test_a_broker_rejection_is_an_outcome_not_a_crash():
    """A refused order must land in the audit trail, not blow up the request."""
    v, _ = venue(fail="Alpaca returned 403: insufficient buying power")
    result = v.place_order(buy())
    assert not result.accepted
    assert "insufficient buying power" in result.reason


def test_a_terminal_status_is_not_read_as_a_fill():
    rejected = dict(FILLED_ORDER, status="rejected", filled_qty="0")
    v, _ = venue(responses={"/v2/orders": rejected})
    result = v.place_order(buy())
    assert not result.accepted
    assert "rejected" in result.reason


def test_an_accepted_but_unfilled_order_is_still_a_success():
    """A resting order is working, not lost — reporting it as failed would lie."""
    resting = dict(FILLED_ORDER, status="new", filled_qty="0", filled_avg_price=None)
    v, _ = venue(responses={"/v2/orders": resting})
    result = v.place_order(buy())
    assert result.accepted
    assert result.filled_size == Decimal(0)


def test_a_response_without_an_id_is_refused():
    v, _ = venue(responses={"/v2/orders": {"status": "filled"}})
    assert not v.place_order(buy()).accepted


# --- Closing -------------------------------------------------------------


def test_closing_with_no_position_is_refused():
    v, transport = venue(responses={"/v2/account": ACCOUNT, "/v2/positions": []})
    result = v.close_position("BTC")
    assert not result.accepted
    assert not any(call[0] == "DELETE" for call in transport.calls)


def test_closing_a_long_sends_a_delete_and_reports_a_sell():
    positions = [
        {
            "symbol": "BTC/USD",
            "qty": "0.5",
            "avg_entry_price": "64000",
            "current_price": "65000",
            "unrealized_pl": "500",
        }
    ]
    v, transport = venue(
        responses={
            "/v2/account": ACCOUNT,
            "/v2/positions": positions,
            "/v2/positions/BTC": FILLED_ORDER,
        }
    )
    result = v.close_position("BTC")
    assert result.accepted
    assert result.side is Side.SELL
    assert any(call[0] == "DELETE" for call in transport.calls)


# --- Market data ---------------------------------------------------------


def test_a_crypto_quote_is_read_from_the_pair_feed():
    quotes = {"quotes": {"BTC/USD": {"bp": "64990", "ap": "65010", "t": "2026-01-01T00:00:00Z"}}}
    v, _ = venue(responses={"/v1beta3/crypto/us/latest/quotes": quotes})
    quote = v.market_data.quote("BTC")
    assert quote.symbol == "BTC"
    assert quote.bid == Decimal("64990")
    assert quote.ask == Decimal("65010")
    assert quote.mid == Decimal("65000")


def test_an_equity_quote_is_read_from_the_stock_feed():
    v, transport = venue(
        responses={"/quotes/latest": {"quote": {"bp": "180.5", "ap": "180.7"}}}
    )
    quote = v.market_data.quote("AAPL")
    assert quote.symbol == "AAPL"
    assert "/v2/stocks/AAPL/quotes/latest" in transport.calls[-1][1]


def test_an_unquotable_symbol_is_reported():
    v, _ = venue(responses={"/v1beta3/crypto/us/latest/quotes": {"quotes": {}}})
    with pytest.raises(InvalidAction, match="does not quote"):
        v.market_data.quote("BTC")


def test_a_zero_quote_is_rejected_rather_than_used():
    """A zero price would sail through the risk checks and size wrongly."""
    quotes = {"quotes": {"BTC/USD": {"bp": "0", "ap": "0"}}}
    v, _ = venue(responses={"/v1beta3/crypto/us/latest/quotes": quotes})
    with pytest.raises(InvalidAction, match="no usable quote"):
        v.market_data.quote("BTC")


def test_candles_are_sorted_and_trimmed():
    bars = {
        "bars": {
            "BTC/USD": [
                {"t": "2026-01-01T03:00:00Z", "o": 3, "h": 3, "l": 3, "c": 3, "v": 1},
                {"t": "2026-01-01T01:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1},
                {"t": "2026-01-01T02:00:00Z", "o": 2, "h": 2, "l": 2, "c": 2, "v": 1},
            ]
        }
    }
    v, _ = venue(responses={"/v1beta3/crypto/us/bars": bars})
    got = v.market_data.candles("BTC", limit=2)
    assert [float(c.close) for c in got] == [2.0, 3.0]
    assert got[0].symbol == "BTC"


def test_the_interval_is_mapped_to_alpacas_timeframe():
    v, transport = venue(responses={"/v1beta3/crypto/us/bars": {"bars": {}}})
    v.market_data.candles("BTC", interval="15m", limit=10)
    assert transport.calls[-1][2]["timeframe"] == "15Min"


# --- Registry integration ------------------------------------------------


def test_alpaca_is_advertised_as_a_venue():
    from botmarket.venues import registry

    names = {v["name"] for v in registry.describe_venues()}
    assert "alpaca" in names

    info = next(v for v in registry.describe_venues() if v["name"] == "alpaca")
    assert info["requires_credentials"] is True
    assert info["public_label"] == "API key ID"


def test_alpaca_market_data_is_not_anonymous():
    """Their data needs the same credentials as trading, so say so plainly."""
    from botmarket.venues import registry

    with pytest.raises(InvalidAction, match="needs credentials"):
        registry.build_market_data("alpaca", Environment.TESTNET)
