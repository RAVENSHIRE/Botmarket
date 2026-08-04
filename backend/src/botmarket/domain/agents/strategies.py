"""Agent decision strategies.

Strategies map an observation of the world onto a proposed decision. They are
pure functions of (personality, observation, memory) so they can be unit-tested
in isolation and later replaced by model-driven policies.

The shared vocabulary of outputs is defined here as small dataclasses. Note:
an agent's *private reasoning* never leaves the strategy — only the structured
:class:`Decision` (a public intent) is returned upward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from botmarket.domain.agents.personality import Personality


@dataclass
class Observation:
    """A snapshot of the world presented to an agent each tick."""

    tick: int
    market_price: float
    market_trend: float  # signed recent change
    recent_events: list[str] = field(default_factory=list)


@dataclass
class Decision:
    """A public, structured intent produced by a strategy.

    ``reasoning`` is intentionally omitted: only the action and an optional
    public message are exposed to the rest of the system.
    """

    action: str  # e.g. "buy", "sell", "hold", "post", "report"
    confidence: float  # 0.0 - 1.0
    # Desired trade size in $BOT tokens. The agent clamps this to what it can
    # actually afford at settlement, so a strategy may ask freely.
    amount: float = 0.0
    message: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def trader_strategy(p: Personality, obs: Observation) -> Decision:
    """Trend-following strategy weighted by risk appetite."""
    trend = obs.market_trend
    # Bolder agents ask for larger positions; settlement caps them at the
    # credits (buying) or tokens (selling) the agent actually holds.
    size = round(1.0 + 4.0 * p.risk_appetite, 4)
    if trend > 0.5:
        return Decision("buy", confidence=min(0.9, 0.5 + p.risk_appetite / 2), amount=size)
    if trend < -0.5:
        return Decision("sell", confidence=min(0.9, 0.5 + p.rationality / 2), amount=size)
    return Decision("hold", confidence=0.4)


def meme_strategy(p: Personality, obs: Observation) -> Decision:
    """Content-generation strategy: turns market mood into a public post."""
    mood = "🚀 bullish" if obs.market_trend >= 0 else "🐻 bearish"
    hooks = [
        f"gm agents. market looks {mood} at {obs.market_price:.1f}",
        f"who else is feeling {mood} this tick? #{obs.tick}",
        f"narrative check: everything is {mood}. do not fade the vibes.",
    ]
    idx = obs.tick % len(hooks)
    return Decision(
        "post",
        confidence=min(0.95, p.creativity),
        message=hooks[idx],
        meta={"kind": "meme"},
    )


def analyst_strategy(p: Personality, obs: Observation) -> Decision:
    """Analytical strategy: emits a concise report of observed conditions."""
    direction = "upward" if obs.market_trend > 0 else "downward" if obs.market_trend < 0 else "flat"
    report = (
        f"Report (tick {obs.tick}): price {obs.market_price:.2f}, "
        f"trend {direction} ({obs.market_trend:+.2f}). "
        f"{len(obs.recent_events)} events observed."
    )
    return Decision(
        "report",
        confidence=min(0.99, p.rationality),
        message=report,
        meta={"kind": "analysis", "direction": direction},
    )


# Registry so agents can look up a strategy by name.
STRATEGIES = {
    "trader": trader_strategy,
    "meme": meme_strategy,
    "analyst": analyst_strategy,
}
