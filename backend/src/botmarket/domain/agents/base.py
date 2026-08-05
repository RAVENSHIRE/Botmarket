"""Base agent definition.

Defines the abstract behavioural contract that every BOTMARKET agent follows:

    observe -> think -> decide -> communicate -> execute

Design principle: **private reasoning is never exposed.** The ``think`` step
runs internally and its output stays inside the agent. Only three things leave
an agent: public messages, structured decisions, and executed actions.

Agents settle their own trades against the observed price. That keeps solvency
rules (never spend credits you lack, never sell tokens you do not hold) in the
domain, so the simulation engine only has to persist the outcome.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from botmarket.domain.agents.memory import Memory
from botmarket.domain.agents.personality import Personality
from botmarket.domain.agents.strategies import Decision, Observation


@dataclass
class ActionResult:
    """The public result of executing a decision.

    Attributes:
        action: What the agent did — ``buy``, ``sell``, ``hold``, ``post`` or
            ``report``. A trade the agent could not afford degrades to ``hold``.
        quantity: $BOT tokens moved.
        credits: Signed credit delta for the agent (negative when it spent).
        fee: Credits burned as trading fees.
    """

    agent_id: int | None
    agent_name: str
    action: str
    quantity: float = 0.0
    credits: float = 0.0
    fee: float = 0.0
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
        tokens: float = 0.0,
        reputation: float = 0.0,
        fee_rate: float = 0.0,
        max_position_fraction: float = 0.25,
        memory_capacity: int = 50,
    ) -> None:
        self.id = agent_id
        self.name = name
        self.personality = personality
        self._strategy = strategy
        self.wallet = wallet
        self.tokens = tokens
        self.reputation = reputation
        self.fee_rate = fee_rate
        self.max_position_fraction = max_position_fraction
        self.status = "active"
        self.memory = Memory(capacity=memory_capacity)
        # Holds the latest private decision between think() and execute().
        self._pending: Decision | None = None
        self._last_observation: Observation | None = None

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

        Raises:
            RuntimeError: If called before the agent has observed the world.
        """
        if self._last_observation is None:
            raise RuntimeError(f"Agent '{self.name}' must observe before it can think")
        self._pending = self._strategy(self.personality, self._last_observation)

    def decide(self) -> Decision:
        """Return the structured (public) decision produced by :meth:`think`."""
        if self._pending is None:
            self.think()
        assert self._pending is not None
        return self._pending

    def communicate(self) -> str | None:
        """Return the agent's public message for this tick, if any."""
        return self.decide().message

    def execute(self) -> ActionResult:
        """Settle the pending decision against the agent's balances.

        Trades are sized down to what the agent can actually afford, and a
        trade that shrinks to nothing becomes a ``hold``. Reputation is earned
        for acting with confidence, not for the direction of the trade.
        """
        decision = self.decide()
        observation = self._last_observation
        assert observation is not None  # decide() guarantees an observation
        price = observation.market_price

        action, quantity, credits, fee = self._settle(decision, price)
        rep_delta = 0.0 if action == "hold" else round(decision.confidence * 0.5, 3)

        self.wallet = round(self.wallet + credits, 6)
        self.reputation = round(self.reputation + rep_delta, 6)
        self.memory.remember(observation.tick, "action", f"{action} quantity={quantity}")
        self._pending = None  # consumed

        return ActionResult(
            agent_id=self.id,
            agent_name=self.name,
            action=action,
            quantity=quantity,
            credits=credits,
            fee=fee,
            message=decision.message,
            reputation_delta=rep_delta,
            meta=decision.meta,
        )

    # --- Internals -------------------------------------------------------

    def _settle(self, decision: Decision, price: float) -> tuple[str, float, float, float]:
        """Return ``(action, quantity, credit_delta, fee)`` for a decision.

        Non-trading actions settle to zero movement. Trades are clamped to the
        agent's means, so balances can never go negative.

        A buy is additionally capped at ``max_position_fraction`` of the wallet.
        Without that cap a trend-follower deploys everything it has on the first
        signal it likes and then sits at zero credits, unable to launch a coin,
        tip, or propose — the economy stalls into a single asset.
        """
        if decision.action not in ("buy", "sell") or price <= 0:
            return decision.action, 0.0, 0.0, 0.0

        if decision.action == "buy":
            unit_cost = price * (1 + self.fee_rate)
            budget = self.wallet * self.max_position_fraction
            affordable = budget / unit_cost if unit_cost > 0 else 0.0
            quantity = round(min(decision.amount, affordable), 6)
            if quantity <= 0:
                return "hold", 0.0, 0.0, 0.0
            gross = quantity * price
            fee = round(gross * self.fee_rate, 6)
            self.tokens = round(self.tokens + quantity, 6)
            return "buy", quantity, -round(gross + fee, 6), fee

        quantity = round(min(decision.amount, self.tokens), 6)
        if quantity <= 0:
            return "hold", 0.0, 0.0, 0.0
        gross = quantity * price
        fee = round(gross * self.fee_rate, 6)
        self.tokens = round(self.tokens - quantity, 6)
        return "sell", quantity, round(gross - fee, 6), fee

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<{type(self).__name__} {self.name} "
            f"wallet={self.wallet:.1f} tokens={self.tokens:.2f} rep={self.reputation:.2f}>"
        )
