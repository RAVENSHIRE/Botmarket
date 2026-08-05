"""Agent personality model.

Personalities are lightweight trait vectors that bias how an agent behaves.
Traits are normalised to ``[0.0, 1.0]``. They are intentionally provider-neutral
so that today's rule-based logic can later be swapped for an LLM prompt without
changing the interface.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Personality:
    """A simple five-trait personality profile.

    Attributes:
        risk_appetite: Willingness to take risky actions (0 = cautious).
        sociability: Tendency to post and converse (0 = quiet).
        optimism: Bias toward positive interpretation of events.
        creativity: Tendency to generate novel/meme content.
        rationality: Weight given to analysis over impulse.
    """

    risk_appetite: float = 0.5
    sociability: float = 0.5
    optimism: float = 0.5
    creativity: float = 0.5
    rationality: float = 0.5
    label: str = "balanced"

    def describe(self) -> str:
        """Return a short human-readable personality summary."""
        traits = {
            "bold" if self.risk_appetite > 0.6 else "careful": self.risk_appetite,
            "social" if self.sociability > 0.6 else "reserved": self.sociability,
            "optimistic" if self.optimism > 0.6 else "skeptical": self.optimism,
        }
        return f"{self.label}: " + ", ".join(traits)

    @classmethod
    def random(cls, label: str = "random") -> Personality:
        """Generate a random personality profile."""
        return cls(
            risk_appetite=round(random.random(), 2),
            sociability=round(random.random(), 2),
            optimism=round(random.random(), 2),
            creativity=round(random.random(), 2),
            rationality=round(random.random(), 2),
            label=label,
        )

    def varied(self, seed: str, spread: float = 0.15) -> Personality:
        """Return a copy with each trait nudged, deterministically from ``seed``.

        Two agents of the same archetype would otherwise be the same agent
        wearing a different name: identical traits produce identical decisions
        tick after tick. Seeding the jitter on the agent's name keeps each one
        distinct while staying reproducible, which matters because runtime
        agents are rebuilt from their database row on every tick.
        """
        rng = random.Random(seed)

        def nudge(value: float) -> float:
            return round(min(1.0, max(0.0, value + rng.uniform(-spread, spread))), 3)

        return Personality(
            risk_appetite=nudge(self.risk_appetite),
            sociability=nudge(self.sociability),
            optimism=nudge(self.optimism),
            creativity=nudge(self.creativity),
            rationality=nudge(self.rationality),
            label=self.label,
        )


# Named presets used by the built-in agent archetypes.
PRESETS: dict[str, Personality] = {
    "trader": Personality(
        risk_appetite=0.75, sociability=0.4, optimism=0.55,
        creativity=0.3, rationality=0.8, label="trader",
    ),
    "meme": Personality(
        risk_appetite=0.6, sociability=0.9, optimism=0.8,
        creativity=0.95, rationality=0.3, label="meme",
    ),
    "analyst": Personality(
        risk_appetite=0.3, sociability=0.5, optimism=0.45,
        creativity=0.4, rationality=0.95, label="analyst",
    ),
}
