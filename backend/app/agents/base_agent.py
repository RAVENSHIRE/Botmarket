"""Base agent definition.

Defines the abstract behavioural contract that every BOTMARKET agent follows:

    observe -> think -> decide -> communicate -> execute

Design principle: **private reasoning is never exposed.** The ``think`` step
runs internally and its output stays inside the agent. Only three things leave
an agent: public messages, structured decisions, and executed actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.agents.memory import Memory
from app.agents.personality import Personality
from app.agents.strategies import Decision, Observation


@dataclass
class ActionResult:
    """The public result of executing a decision."""

    agent_id: int | None
    agent_name: str
    action: str
    amount: float = 0.0
    message: str | None = None
    reputation_delta: float = 0.0
    meta: dict = field(default_factory=dict)


class BaseAgent:
    """Abstract base class for all agents.

    Concrete agents supply a ``strategy`` callable that maps an
    :class:`Observation` to a :class:`Decision`. Subclasses may override
    :meth:`think` or :meth:`execute` to specialise behaviour.
    """

    agent_type: str = "base"

    def __init__(
        self,
        name: str,
        personality: Personality,
        strategy: Callable[[Personality, Observation], Decision],
        *,
        agent_id: int | None = None,
        wallet: float = 1000.0,
        reputation: float = 0.0,
        memory_capacity: int = 50,
    ) -> None:
        self.id = agent_id
        self.name = name
        self.personality = personality
        self._strategy = strategy
        self.wallet = wallet
        self.reputation = reputation
        self.status = "active"
        self.memory = Memory(capacity=memory_capacity)
        # Holds the latest private decision between think() and execute().
        self._pending: Decision | None = None

    # --- Public lifecycle (the only interface the engine calls) ---------

    def observe(self, observation: Observation) -> None:
        """Record what the agent perceives this tick (public input)."""
        self.memory.remember(
            observation.tick,
            "observation",
            f"price={observation.market_price:.2f} trend={observation.market_trend:+.2f}",
        )
        self._last_observation = observation

    def think(self) -> None:
        """Run private reasoning. Output is stored internally, never returned.

        This is where an LLM call would live in the future. Its result is a
        structured :class:`Decision`; the underlying reasoning is discarded.
        """
        self._pending = self._strategy(self.personality, self._last_observation)

    def decide(self) -> Decision:
        """Return the structured (public) decision produced by :meth:`think`."""
        if self._pending is None:
            self.think()
        assert self._pending is not None
        return self._pending

    def communicate(self) -> str | None:
        """Return the agent's public message for this tick, if any."""
        decision = self.decide()
        return decision.message

    def execute(self) -> ActionResult:
        """Apply the pending decision to the agent's state and return a result.

        Wallet and reputation effects are computed here so the simulation
        engine can persist them. Subclasses may override for richer economics.
        """
        decision = self.decide()
        rep_delta = round(decision.confidence * 0.5, 3)

        if decision.action == "buy":
            self.wallet -= decision.amount
        elif decision.action == "sell":
            self.wallet += decision.amount

        self.reputation += rep_delta
        self.memory.remember(
            getattr(self._last_observation, "tick", 0),
            "action",
            f"{decision.action} amount={decision.amount}",
        )
        self._pending = None  # consumed

        return ActionResult(
            agent_id=self.id,
            agent_name=self.name,
            action=decision.action,
            amount=decision.amount,
            message=decision.message,
            reputation_delta=rep_delta,
            meta=decision.meta,
        )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<{type(self).__name__} {self.name} wallet={self.wallet:.1f} rep={self.reputation:.2f}>"
