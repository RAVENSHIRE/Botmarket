"""Tests for the pre-trade risk engine.

These are the checks standing between an autonomous agent and a real account,
so each rule gets both a passing and a refusing case, and each refusal is
identified by its rule name rather than its message.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from botmarket.domain.risk import (
    RiskLimits,
    RiskViolation,
    check_order,
    clamp_to_limits,
    close_request,
)
from botmarket.domain.venue import (
    AccountState,
    Balance,
    Environment,
    Instrument,
    OrderRequest,
    Position,
    Side,
)

PRICE = Decimal("100")
INSTRUMENT = Instrument(symbol="BTC", min_notional=Decimal("10"), max_leverage=20)


def account(
    *,
    available: Decimal = Decimal("10000"),
    positions: list[Position] | None = None,
    environment: Environment = Environment.TESTNET,
) -> AccountState:
    """Build an account state for a test."""
    return AccountState(
        environment=environment,
        balances=[Balance(currency="USDC", total=available, available=available)],
        positions=positions or [],
    )


def order(**overrides) -> OrderRequest:
    """Build an order request, defaulting to a sane 1 BTC market buy."""
    body: dict = {"symbol": "BTC", "side": Side.BUY, "size": Decimal("1")}
    body.update(overrides)
    return OrderRequest(**body)


def run(request: OrderRequest, **overrides) -> None:
    """Run the risk check with sensible defaults."""
    body: dict = {
        "account": account(),
        "instrument": INSTRUMENT,
        "limits": RiskLimits(),
        "reference_price": PRICE,
    }
    body.update(overrides)
    check_order(request, **body)


def refusal(request: OrderRequest, **overrides) -> str:
    """Run the check, assert it refused, and return the rule that did it."""
    with pytest.raises(RiskViolation) as caught:
        run(request, **overrides)
    return caught.value.rule


def test_a_reasonable_order_passes():
    run(order())


def test_kill_switch_stops_everything():
    limits = RiskLimits(trading_enabled=False)
    assert refusal(order(), limits=limits) == "trading_disabled"
    # Even a reducing order, which every other rule would wave through.
    assert refusal(order(reduce_only=True), limits=limits) == "trading_disabled"


def test_mainnet_requires_both_configuration_and_confirmation():
    live = account(environment=Environment.MAINNET)

    # Configuration alone is not consent.
    assert (
        refusal(order(), account=live, limits=RiskLimits(allow_mainnet=True))
        == "confirmation_required"
    )
    # Confirmation alone is not permission.
    assert (
        refusal(
            order(),
            account=live,
            limits=RiskLimits(allow_mainnet=False),
            confirm_real_money=True,
        )
        == "mainnet_not_allowed"
    )
    # Both together are fine.
    run(
        order(),
        account=live,
        limits=RiskLimits(allow_mainnet=True),
        confirm_real_money=True,
    )


def test_testnet_needs_no_confirmation():
    """Confirmation guards real money only; testnet must stay frictionless."""
    run(order(), account=account(environment=Environment.TESTNET))


@pytest.mark.parametrize("size", [Decimal(0), Decimal("-1")])
def test_non_positive_size_refused(size):
    assert refusal(order(size=size)) == "invalid_size"


def test_leverage_ceiling_is_the_lower_of_venue_and_operator():
    assert refusal(order(leverage=10), limits=RiskLimits(max_leverage=5)) == "leverage_exceeded"
    # The instrument's own ceiling binds even when the operator allows more.
    tight = Instrument(symbol="BTC", max_leverage=2)
    assert (
        refusal(order(leverage=4), instrument=tight, limits=RiskLimits(max_leverage=20))
        == "leverage_exceeded"
    )
    run(order(leverage=5), limits=RiskLimits(max_leverage=5))


def test_dust_orders_refused():
    assert refusal(order(size=Decimal("0.01"))) == "below_min_notional"


def test_oversized_orders_refused():
    assert (
        refusal(order(size=Decimal("50")), limits=RiskLimits(max_order_value=Decimal("1000")))
        == "above_max_order_value"
    )


def test_position_limit_counts_the_existing_position():
    held = Position(
        symbol="BTC",
        side=Side.BUY,
        size=Decimal("45"),
        entry_price=PRICE,
        mark_price=PRICE,
    )
    limits = RiskLimits(max_position_value=Decimal("5000"), max_order_value=Decimal("1000"))
    assert (
        refusal(order(size=Decimal("8")), account=account(positions=[held]), limits=limits)
        == "position_limit"
    )


def test_opposing_orders_net_down_rather_than_adding():
    """Selling into a long position reduces exposure, so it is not blocked."""
    held = Position(
        symbol="BTC",
        side=Side.BUY,
        size=Decimal("49"),
        entry_price=PRICE,
        mark_price=PRICE,
    )
    run(
        order(side=Side.SELL, size=Decimal("5")),
        account=account(positions=[held]),
        limits=RiskLimits(max_position_value=Decimal("5000")),
    )


def test_gross_exposure_limit():
    positions = [
        Position(
            symbol=sym,
            side=Side.BUY,
            size=Decimal("40"),
            entry_price=PRICE,
            mark_price=PRICE,
        )
        for sym in ("ETH", "SOL")
    ]
    limits = RiskLimits(max_gross_notional=Decimal("8000"), max_position_value=Decimal("9000"))
    assert (
        refusal(order(size=Decimal("5")), account=account(positions=positions), limits=limits)
        == "gross_exposure"
    )


def test_margin_must_be_available():
    assert (
        refusal(order(size=Decimal("5")), account=account(available=Decimal("100")))
        == "insufficient_margin"
    )
    # Leverage reduces the margin required, so the same order fits.
    run(order(size=Decimal("5"), leverage=5), account=account(available=Decimal("100")))


def test_daily_loss_cap_allows_only_reducing_orders():
    limits = RiskLimits(max_daily_loss=Decimal("500"))
    assert (
        refusal(order(), limits=limits, realised_loss_today=Decimal("600"))
        == "daily_loss_cap"
    )
    # Getting smaller is always permitted while the switch is on.
    run(order(reduce_only=True), limits=limits, realised_loss_today=Decimal("600"))


def test_loss_under_the_cap_does_not_block():
    run(order(), limits=RiskLimits(max_daily_loss=Decimal("500")),
        realised_loss_today=Decimal("499"))


def test_zero_cap_disables_the_daily_check():
    run(order(), limits=RiskLimits(max_daily_loss=Decimal(0)),
        realised_loss_today=Decimal("100000"))


def test_reducing_orders_skip_exposure_and_margin():
    """An agent must never be trapped in a position it is trying to exit."""
    held = Position(
        symbol="BTC",
        side=Side.BUY,
        size=Decimal("100"),
        entry_price=PRICE,
        mark_price=PRICE,
    )
    run(
        order(side=Side.SELL, size=Decimal("100"), reduce_only=True),
        account=account(available=Decimal("0"), positions=[held]),
        limits=RiskLimits(max_order_value=Decimal("100000")),
    )


def test_clamp_shrinks_an_oversized_order():
    limits = RiskLimits(max_order_value=Decimal("1000"), max_position_value=Decimal("5000"))
    clamped = clamp_to_limits(
        order(size=Decimal("50")),
        instrument=INSTRUMENT,
        limits=limits,
        reference_price=PRICE,
    )
    assert clamped.size == Decimal("10")
    run(clamped, limits=limits)


def test_clamp_leaves_a_conforming_order_alone():
    request = order(size=Decimal("2"))
    assert clamp_to_limits(
        request, instrument=INSTRUMENT, limits=RiskLimits(), reference_price=PRICE
    ) is request


def test_clamping_does_not_excuse_a_leverage_breach():
    """Clamping only shrinks size; it cannot rescue a categorically bad order."""
    limits = RiskLimits(max_leverage=2)
    clamped = clamp_to_limits(
        order(size=Decimal("50"), leverage=10),
        instrument=INSTRUMENT,
        limits=limits,
        reference_price=PRICE,
    )
    assert refusal(clamped, limits=limits) == "leverage_exceeded"


def test_close_request_reverses_the_position():
    request = close_request(Side.BUY, Decimal("3"), "ETH")
    assert request.side is Side.SELL
    assert request.reduce_only is True
    assert request.size == Decimal("3")
