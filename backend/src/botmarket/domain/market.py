"""Simulated market.

A minimal price process the agents observe and act upon. The market keeps a
short price history and exposes the recent trend. It is deliberately simple —
a random walk nudged by aggregate agent activity — but isolated behind a clean
interface so it can grow into a full order book later.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Market:
    """A single-asset simulated market with a random-walk price.

    Attributes:
        price: Current asset price.
        history: Recent price history (most recent last).
        volatility: Standard deviation of per-tick random moves.
    """

    price: float = 100.0
    volatility: float = 2.5
    history: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history = [self.price]

    @property
    def trend(self) -> float:
        """Signed price change over the last few ticks (recent momentum)."""
        if len(self.history) < 2:
            return 0.0
        window = self.history[-4:]
        return round(window[-1] - window[0], 3)

    def step(self, net_pressure: float = 0.0) -> float:
        """Advance the market one tick.

        Args:
            net_pressure: Aggregate buy(+)/sell(-) pressure from agents, which
                biases the random move.

        Returns:
            The new price.
        """
        shock = random.gauss(0, self.volatility)
        drift = 0.01 * net_pressure
        self.price = round(max(1.0, self.price + shock + drift), 2)
        self.history.append(self.price)
        # Bound the retained history to keep memory flat.
        if len(self.history) > 200:
            self.history = self.history[-200:]
        return self.price
