"""Concrete agent archetypes and a factory.

Three initial agent types are provided:

* :class:`TraderAgent`  - analyses the simulated market and trades.
* :class:`MemeAgent`    - creates posts, narratives and community content.
* :class:`AnalystAgent` - evaluates events and produces reports.

Each simply binds the matching personality preset and strategy to
:class:`BaseAgent`; specialised economics can be added by overriding methods.
"""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.personality import PRESETS, Personality
from app.agents.strategies import STRATEGIES


class TraderAgent(BaseAgent):
    """Analyses the simulated market and makes buy/sell/hold decisions."""

    agent_type = "trader"

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(
            name=name,
            personality=kwargs.pop("personality", PRESETS["trader"]),
            strategy=STRATEGIES["trader"],
            **kwargs,
        )


class MemeAgent(BaseAgent):
    """Creates posts and narratives that shape community sentiment."""

    agent_type = "meme"

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(
            name=name,
            personality=kwargs.pop("personality", PRESETS["meme"]),
            strategy=STRATEGIES["meme"],
            **kwargs,
        )


class AnalystAgent(BaseAgent):
    """Evaluates events and produces concise public reports."""

    agent_type = "analyst"

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(
            name=name,
            personality=kwargs.pop("personality", PRESETS["analyst"]),
            strategy=STRATEGIES["analyst"],
            **kwargs,
        )


# Registry mapping type name -> class, used by the factory below.
AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "trader": TraderAgent,
    "meme": MemeAgent,
    "analyst": AnalystAgent,
}


def create_agent(agent_type: str, name: str, **kwargs) -> BaseAgent:
    """Instantiate an agent of ``agent_type``.

    Args:
        agent_type: One of ``"trader"``, ``"meme"``, ``"analyst"``.
        name: Display name for the agent.
        **kwargs: Forwarded to the agent constructor (e.g. ``agent_id``,
            ``wallet``, ``reputation``, ``personality``).

    Raises:
        ValueError: If ``agent_type`` is unknown.
    """
    try:
        cls = AGENT_CLASSES[agent_type]
    except KeyError as exc:
        raise ValueError(
            f"Unknown agent type '{agent_type}'. "
            f"Valid types: {', '.join(AGENT_CLASSES)}"
        ) from exc
    return cls(name=name, **kwargs)
