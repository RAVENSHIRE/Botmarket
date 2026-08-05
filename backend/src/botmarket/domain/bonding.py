"""Bonding-curve maths for agent-launched memecoins.

Every memecoin prices its next unit on a linear curve::

    price(s) = base + slope * s

where ``s`` is the current supply. Minting ``q`` units from supply ``s`` costs
the integral of that curve, which has a closed form::

    cost(s, q) = base * q + slope / 2 * ((s + q)^2 - s^2)

Because minting and burning use the same integral, a coin's reserve always
equals the cost of its outstanding supply — the curve can never pay out more
credits than were paid in. These are pure functions with no I/O so the
economics can be tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass

from botmarket.domain.errors import InvalidAction


@dataclass(frozen=True)
class Curve:
    """A linear bonding curve.

    Attributes:
        base_price: Price of the very first unit (supply 0).
        slope: Amount the unit price rises per unit of supply.
    """

    base_price: float = 1.0
    slope: float = 0.01

    def spot_price(self, supply: float) -> float:
        """Return the marginal price of the next unit at ``supply``."""
        return self.base_price + self.slope * supply

    def cost_to_mint(self, supply: float, quantity: float) -> float:
        """Return the credits required to mint ``quantity`` units.

        Args:
            supply: Current outstanding supply.
            quantity: Units to mint; must be positive.

        Raises:
            InvalidAction: If ``quantity`` is not positive.
        """
        if quantity <= 0:
            raise InvalidAction("Quantity must be greater than zero")
        return self._integral(supply, supply + quantity)

    def refund_for_burn(self, supply: float, quantity: float) -> float:
        """Return the credits released by burning ``quantity`` units.

        Args:
            supply: Current outstanding supply.
            quantity: Units to burn; must be positive and at most ``supply``.

        Raises:
            InvalidAction: If ``quantity`` is not positive or exceeds supply.
        """
        if quantity <= 0:
            raise InvalidAction("Quantity must be greater than zero")
        if quantity > supply:
            raise InvalidAction("Cannot burn more than the outstanding supply")
        return self._integral(supply - quantity, supply)

    def market_cap(self, supply: float) -> float:
        """Return the value of the outstanding supply at the current spot price."""
        return round(self.spot_price(supply) * supply, 4)

    def _integral(self, lo: float, hi: float) -> float:
        """Return the area under the curve between supplies ``lo`` and ``hi``."""
        area = self.base_price * (hi - lo) + self.slope / 2 * (hi**2 - lo**2)
        return round(area, 6)
