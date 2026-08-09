"""Linear bonding-curve math.

A memecoin's spot price is a pure, deterministic function of its circulating
supply:

    price(s) = base + slope * s

Buying moves the price up along the curve; selling moves it back down. All
functions here are provider-neutral and free of any database or framework
dependency, so they can be unit-tested in isolation and reused by the service
layer, the simulation engine, or a future on-chain settlement layer.

Cost to buy ``q`` tokens starting from supply ``s`` is the integral of the
price function over ``[s, s + q]``::

    cost = ∫ (base + slope * x) dx  from s to s+q
         = base * q + slope * q * (2s + q) / 2

Symmetrically, selling ``q`` tokens from supply ``s`` (down to ``s - q``) pays
out the integral over ``[s - q, s]``.
"""

from __future__ import annotations

# Default curve parameters for a freshly launched coin.
DEFAULT_BASE_PRICE = 1.0
DEFAULT_SLOPE = 0.01

# Native-token reserve at which a coin "graduates".
GRADUATION_RESERVE = 10_000.0


def spot_price(base: float, slope: float, supply: float) -> float:
    """Return the instantaneous price at the given supply."""
    return base + slope * supply


def buy_cost(base: float, slope: float, supply: float, qty: float) -> float:
    """Native-token cost to buy ``qty`` tokens starting from ``supply``."""
    if qty < 0:
        raise ValueError("qty must be non-negative")
    return base * qty + slope * qty * (2 * supply + qty) / 2


def sell_proceeds(base: float, slope: float, supply: float, qty: float) -> float:
    """Native-token proceeds from selling ``qty`` tokens down from ``supply``."""
    if qty < 0:
        raise ValueError("qty must be non-negative")
    if qty > supply:
        raise ValueError("cannot sell more than the circulating supply")
    return base * qty + slope * qty * (2 * supply - qty) / 2


def reserve_at(base: float, slope: float, supply: float) -> float:
    """Total native token held by the curve at a given supply.

    Equivalent to ``buy_cost(base, slope, 0, supply)`` — the area under the
    price curve from 0 to ``supply``.
    """
    return base * supply + slope * supply * supply / 2


def market_cap(base: float, slope: float, supply: float) -> float:
    """Circulating supply valued at the current spot price."""
    return spot_price(base, slope, supply) * supply
