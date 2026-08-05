"""Tests for the memecoin bonding curve.

The invariant that matters: a coin's reserve must always cover its outstanding
supply, so the curve can never fail to honour a sell.
"""

from __future__ import annotations

import pytest

from botmarket.domain.bonding import Curve
from botmarket.domain.errors import InvalidAction


def test_spot_price_rises_with_supply():
    curve = Curve(base_price=1.0, slope=0.01)
    assert curve.spot_price(0) == 1.0
    assert curve.spot_price(100) == pytest.approx(2.0)


def test_cost_matches_the_curve_integral():
    curve = Curve(base_price=1.0, slope=0.01)
    # base * q + slope / 2 * (q^2) for a mint starting from zero supply.
    assert curve.cost_to_mint(0, 100) == pytest.approx(1 * 100 + 0.005 * 100**2)


def test_minting_later_costs_more():
    curve = Curve(base_price=1.0, slope=0.01)
    assert curve.cost_to_mint(500, 10) > curve.cost_to_mint(0, 10)


def test_burn_refunds_exactly_what_the_mint_paid():
    """Round-tripping a position returns the buyer to where they started."""
    curve = Curve(base_price=1.0, slope=0.01)
    cost = curve.cost_to_mint(250, 40)
    refund = curve.refund_for_burn(290, 40)
    assert refund == pytest.approx(cost)


def test_reserve_always_covers_outstanding_supply():
    """Sequential buys and sells never let payouts exceed the reserve."""
    curve = Curve(base_price=1.0, slope=0.01)
    supply = 0.0
    reserve = 0.0
    for quantity in (10, 25, 5, 60):
        reserve += curve.cost_to_mint(supply, quantity)
        supply += quantity
    for quantity in (30, 20):
        reserve -= curve.refund_for_burn(supply, quantity)
        supply -= quantity
        assert reserve >= curve.refund_for_burn(supply, supply) - 1e-6

    # Burning everything drains the reserve to zero, never below it.
    assert reserve == pytest.approx(curve.refund_for_burn(supply, supply))


@pytest.mark.parametrize("quantity", [0, -1])
def test_non_positive_quantities_rejected(quantity):
    curve = Curve()
    with pytest.raises(InvalidAction):
        curve.cost_to_mint(0, quantity)
    with pytest.raises(InvalidAction):
        curve.refund_for_burn(10, quantity)


def test_cannot_burn_more_than_supply():
    with pytest.raises(InvalidAction):
        Curve().refund_for_burn(5, 10)
