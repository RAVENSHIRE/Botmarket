"""Simulation events.

Events are world happenings that occur during a tick (news, shocks, social
milestones). They give agents something to react to. A small generator emits
occasional random events; the interface is intentionally open so scripted or
model-generated events can be added later.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class SimEvent:
    """A single simulation event."""

    kind: str
    description: str
    magnitude: float = 0.0


_EVENT_TEMPLATES: list[tuple[str, str, float]] = [
    ("news", "A new agent DAO announces a liquidity program.", 3.0),
    ("shock", "Rumours of a large sell-off ripple through the feed.", -4.0),
    ("social", "A meme goes viral, boosting community sentiment.", 2.0),
    ("regulation", "The simulation council tightens trading rules.", -1.5),
    ("discovery", "Analysts uncover an undervalued agent cohort.", 2.5),
]


def maybe_generate_event(tick: int, probability: float = 0.4) -> SimEvent | None:
    """Return a random event with the given probability, else ``None``.

    Args:
        tick: The current simulation tick (reserved for future scheduling).
        probability: Chance in ``[0, 1]`` that an event fires this tick.
    """
    if random.random() > probability:
        return None
    kind, description, magnitude = random.choice(_EVENT_TEMPLATES)
    return SimEvent(kind=kind, description=description, magnitude=magnitude)
