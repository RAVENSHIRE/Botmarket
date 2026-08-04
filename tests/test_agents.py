"""Tests for the agent system."""

from __future__ import annotations

import pytest

from app.agents.agent_types import create_agent
from app.agents.strategies import Observation


def _observe(agent, trend: float):
    obs = Observation(tick=1, market_price=100.0, market_trend=trend, recent_events=[])
    agent.observe(obs)
    return obs


def test_create_known_agent_types():
    for kind in ("trader", "meme", "analyst"):
        agent = create_agent(kind, f"{kind}-1")
        assert agent.agent_type == kind
        assert agent.status == "active"
        assert agent.wallet == 1000.0


def test_unknown_agent_type_raises():
    with pytest.raises(ValueError):
        create_agent("wizard", "nope")


def test_trader_buys_on_uptrend():
    agent = create_agent("trader", "t1")
    _observe(agent, trend=2.0)
    decision = agent.decide()
    assert decision.action == "buy"
    result = agent.execute()
    assert agent.wallet < 1000.0  # spent on the buy
    assert result.reputation_delta > 0


def test_meme_agent_produces_public_message():
    agent = create_agent("meme", "m1")
    _observe(agent, trend=1.0)
    assert agent.communicate() is not None
    assert agent.decide().meta.get("kind") == "meme"


def test_analyst_reports_direction():
    agent = create_agent("analyst", "a1")
    _observe(agent, trend=-1.0)
    msg = agent.communicate()
    assert msg is not None and "downward" in msg


def test_private_reasoning_not_exposed():
    """Only public fields leave the agent: no reasoning attribute on Decision."""
    agent = create_agent("trader", "t2")
    _observe(agent, trend=0.0)
    decision = agent.decide()
    assert not hasattr(decision, "reasoning")


def test_memory_is_bounded():
    agent = create_agent("trader", "t3", memory_capacity=5)
    for i in range(10):
        _observe(agent, trend=float(i))
    assert len(agent.memory) <= 5
