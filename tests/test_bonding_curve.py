"""Unit tests for the pure bonding-curve math."""

from __future__ import annotations

import pytest

from app.economy import bonding_curve as bc

BASE, SLOPE = 1.0, 0.01


def test_spot_price_rises_with_supply():
    assert bc.spot_price(BASE, SLOPE, 0) == 1.0
    assert bc.spot_price(BASE, SLOPE, 100) == pytest.approx(2.0)


def test_buy_cost_increases_with_supply():
    """Buying the same quantity costs more when supply is higher."""
    low = bc.buy_cost(BASE, SLOPE, 0, 10)
    high = bc.buy_cost(BASE, SLOPE, 500, 10)
    assert high > low


def test_buy_cost_increases_with_quantity():
    assert bc.buy_cost(BASE, SLOPE, 0, 20) > bc.buy_cost(BASE, SLOPE, 0, 10)


def test_buy_costs_more_than_sell_at_same_supply():
    """At a given supply, a buy of q costs more than a sell of q pays out."""
    s, q = 100, 10
    assert bc.buy_cost(BASE, SLOPE, s, q) > bc.sell_proceeds(BASE, SLOPE, s, q)


def test_round_trip_is_lossless_on_linear_curve():
    """Buy q from s, then sell q from s+q: proceeds equal the original cost."""
    s, q = 40, 25
    cost = bc.buy_cost(BASE, SLOPE, s, q)
    proceeds = bc.sell_proceeds(BASE, SLOPE, s + q, q)
    assert proceeds == pytest.approx(cost)


def test_reserve_equals_buy_from_zero():
    supply = 300
    assert bc.reserve_at(BASE, SLOPE, supply) == pytest.approx(
        bc.buy_cost(BASE, SLOPE, 0, supply)
    )


def test_sell_more_than_supply_raises():
    with pytest.raises(ValueError):
        bc.sell_proceeds(BASE, SLOPE, 10, 20)
