"""Tests for the simulation engine."""

from __future__ import annotations

import pytest

from botmarket.db.models import Agent, Event, Post
from botmarket.services import agents as agents_service
from botmarket.services import market as market_service
from botmarket.services import simulation as simulation_service
from botmarket.services import trading as trading_service


def _seed(db) -> None:
    for agent_type, name in (("trader", "T"), ("meme", "M"), ("analyst", "A")):
        agents_service.register(db, agent_type=agent_type, name=name)


def test_register_agent_persists(db):
    row = agents_service.register(db, agent_type="trader", name="Solo")
    assert row.id is not None
    assert db.get(Agent, row.id).agent_type == "trader"


def test_duplicate_names_are_rejected(db):
    from botmarket.domain.errors import Conflict

    agents_service.register(db, agent_type="trader", name="Twin")
    with pytest.raises(Conflict):
        agents_service.register(db, agent_type="meme", name="Twin")


def test_run_tick_advances_and_persists(db):
    _seed(db)
    result = simulation_service.run_tick(db)

    assert result["tick"] == 1
    assert "market_price" in result
    # Meme + analyst emit messages, so the feed should have grown.
    assert db.query(Post).count() >= 1
    # A price event is always recorded.
    assert db.query(Event).filter(Event.kind == "price").count() == 1


def test_ticks_increment(db):
    _seed(db)
    first = simulation_service.run_tick(db)
    second = simulation_service.run_tick(db)
    assert second["tick"] == first["tick"] + 1


def test_agents_never_overdraw_across_many_ticks(db):
    """The invariant that keeps the economy honest: no negative balances."""
    _seed(db)
    for _ in range(25):
        simulation_service.run_tick(db)
    for agent in db.query(Agent).all():
        assert agent.wallet >= 0
        assert agent.tokens >= 0


def test_leaderboard_ranks_by_net_worth(db):
    _seed(db)
    simulation_service.run_tick(db)
    board = agents_service.leaderboard(db)
    assert len(board) == 3
    net_worths = [row["net_worth"] for row in board]
    assert net_worths == sorted(net_worths, reverse=True)


def test_state_snapshot(db):
    _seed(db)
    simulation_service.run_tick(db)
    state = simulation_service.state(db)
    assert state["agents"] == 3
    assert state["tick"] >= 1
    assert len(state["price_history"]) == 1


def test_external_trades_feed_into_the_next_tick(db):
    """A trade placed between ticks becomes buying pressure on the next one."""
    agent = agents_service.register(db, agent_type="analyst", name="Whale", wallet=1_000_000)
    trading_service.trade(db, agent_id=agent.id, side="buy", quantity=500)

    tick = market_service.next_tick(db)
    from botmarket.repositories import transactions as tx_repo

    assert tx_repo.net_market_pressure(db, tick) == pytest.approx(500)

    result = simulation_service.run_tick(db)
    # The analyst neither buys nor sells, so the pressure is the external trade
    # plus whatever world event fired.
    event_magnitude = result["event"]["magnitude"] if result["event"] else 0.0
    assert result["pressure"] == pytest.approx(500 + event_magnitude)
