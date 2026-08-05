"""Tests for the agent domain: archetypes, decisions and trade settlement."""

from __future__ import annotations

import pytest

from botmarket.domain.agents.registry import create_agent
from botmarket.domain.agents.strategies import Observation


def _observe(agent, trend: float, price: float = 100.0):
    agent.observe(Observation(tick=1, market_price=price, market_trend=trend, recent_events=[]))
    return agent


def test_create_known_agent_types():
    for kind in ("trader", "meme", "analyst"):
        agent = create_agent(kind, f"{kind}-1")
        assert agent.agent_type == kind
        assert agent.status == "active"
        assert agent.wallet == 1000.0
        assert agent.tokens == 0.0


def test_unknown_agent_type_raises():
    with pytest.raises(ValueError):
        create_agent("wizard", "nope")


def test_thinking_before_observing_is_an_error():
    with pytest.raises(RuntimeError):
        create_agent("trader", "t0").think()


def test_trader_buys_on_uptrend():
    agent = _observe(create_agent("trader", "t1"), trend=2.0)
    assert agent.decide().action == "buy"

    result = agent.execute()
    assert result.action == "buy"
    assert agent.tokens == pytest.approx(result.quantity)
    assert agent.wallet == pytest.approx(1000.0 - result.quantity * 100.0)
    assert result.reputation_delta > 0


def test_trader_selling_without_tokens_degrades_to_hold():
    """An agent holding nothing cannot sell, so the decision settles as a hold."""
    agent = _observe(create_agent("trader", "t2"), trend=-2.0)
    assert agent.decide().action == "sell"

    result = agent.execute()
    assert result.action == "hold"
    assert result.quantity == 0
    assert agent.wallet == 1000.0


def test_sell_returns_credits_for_tokens_held():
    agent = create_agent("trader", "t3", wallet=0.0, tokens=3.0)
    _observe(agent, trend=-2.0)
    result = agent.execute()
    assert result.action == "sell"
    assert agent.tokens == pytest.approx(3.0 - result.quantity)
    assert agent.wallet == pytest.approx(result.quantity * 100.0)


def test_buy_never_exceeds_the_position_cap():
    """A trader deploys a slice of its wallet per signal, not the whole thing."""
    agent = create_agent("trader", "t4", wallet=1000.0, max_position_fraction=0.25)
    _observe(agent, trend=2.0)
    result = agent.execute()
    assert result.action == "buy"
    assert -result.credits == pytest.approx(250.0)
    assert agent.wallet == pytest.approx(750.0)


def test_repeated_buying_never_drains_the_wallet():
    """Successive signals shrink the position rather than reaching zero credits."""
    agent = create_agent("trader", "t5", wallet=1000.0)
    for tick in range(20):
        agent.observe(
            Observation(tick=tick, market_price=100.0, market_trend=2.0, recent_events=[])
        )
        agent.execute()
    assert agent.wallet > 0
    assert agent.tokens > 0


def test_buy_is_capped_by_the_wallet():
    """A near-broke agent buys only what it can afford and never goes negative."""
    agent = create_agent("trader", "t6", wallet=50.0, max_position_fraction=1.0)
    _observe(agent, trend=2.0)
    result = agent.execute()
    assert result.action == "buy"
    assert agent.wallet >= 0
    assert result.quantity == pytest.approx(0.5)


def test_same_archetype_agents_get_different_personalities():
    """Otherwise two traders are one agent wearing two names."""
    a = create_agent("trader", "Satoshi")
    b = create_agent("trader", "Ada")
    assert a.personality != b.personality


def test_personality_is_reproducible_from_the_name():
    """Runtime agents are rebuilt every tick, so traits must not drift."""
    first = create_agent("trader", "Satoshi").personality
    second = create_agent("trader", "Satoshi").personality
    assert first == second


def test_trading_fee_is_charged_on_both_sides():
    buyer = create_agent("trader", "fee-buy", wallet=1000.0, fee_rate=0.01)
    _observe(buyer, trend=2.0)
    bought = buyer.execute()
    assert bought.fee == pytest.approx(bought.quantity * 100.0 * 0.01)

    seller = create_agent("trader", "fee-sell", wallet=0.0, tokens=2.0, fee_rate=0.01)
    _observe(seller, trend=-2.0)
    sold = seller.execute()
    assert sold.fee == pytest.approx(sold.quantity * 100.0 * 0.01)
    assert seller.wallet == pytest.approx(sold.quantity * 100.0 - sold.fee)


def test_meme_agent_produces_public_message():
    agent = _observe(create_agent("meme", "m1"), trend=1.0)
    assert agent.communicate() is not None
    assert agent.decide().meta.get("kind") == "meme"


def test_analyst_reports_direction():
    agent = _observe(create_agent("analyst", "a1"), trend=-1.0)
    message = agent.communicate()
    assert message is not None and "downward" in message


def test_private_reasoning_not_exposed():
    """Only public fields leave the agent: no reasoning attribute on Decision."""
    agent = _observe(create_agent("trader", "t5"), trend=0.0)
    assert not hasattr(agent.decide(), "reasoning")


def test_memory_is_bounded():
    agent = create_agent("trader", "t6", memory_capacity=5)
    for i in range(10):
        _observe(agent, trend=float(i))
    assert len(agent.memory) <= 5
