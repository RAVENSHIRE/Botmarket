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

    def cost_to_mint(
        self, supply: float, quantity: float, *, max_supply: float | None = None
    ) -> float:
        """Return the credits required to mint ``quantity`` units.

        Args:
            supply: Current outstanding supply.
            quantity: Units to mint; must be positive.
            max_supply: Optional allocation ceiling. Minting past it is refused
                rather than silently clamped — a buyer who asked for more than
                exists should be told, not quietly given less.

        Raises:
            InvalidAction: If ``quantity`` is not positive, or the mint would
                exceed ``max_supply``.
        """
        if quantity <= 0:
            raise InvalidAction("Quantity must be greater than zero")
        if max_supply is not None and supply + quantity > max_supply:
            available = self.remaining(supply, max_supply)
            raise InvalidAction(
                f"Only {available:,.4f} units remain on the curve; "
                f"{quantity:,.4f} were requested"
            )
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

    def market_cap(self, supply: float, total_supply: float | None = None) -> float:
        """Return the coin's market cap at the current spot price.

        Defaults to the circulating cap (what has actually been minted). Pass
        ``total_supply`` for the fully-diluted figure, which is the one a
        pump.fun-style graduation threshold is measured against — the whole
        supply exists from launch, so pricing only the minted part would
        understate the coin by the size of its unsold allocation.
        """
        return round(self.spot_price(supply) * (total_supply or supply), 4)

    def supply_at_price(self, price: float) -> float:
        """Return the supply at which the curve reaches ``price``.

        The inverse of :meth:`spot_price`. Used to work out how much of the
        allocation has to sell before a market-cap target is met.
        """
        if self.slope <= 0:
            return 0.0
        return max(0.0, (price - self.base_price) / self.slope)

    def remaining(self, supply: float, max_supply: float) -> float:
        """Return how much of the allocation is still mintable."""
        return max(0.0, max_supply - supply)

    def _integral(self, lo: float, hi: float) -> float:
        """Return the area under the curve between supplies ``lo`` and ``hi``."""
        area = self.base_price * (hi - lo) + self.slope / 2 * (hi**2 - lo**2)
        return round(area, 6)
