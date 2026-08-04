"""Tests for the simulation engine."""

from __future__ import annotations

from app.models import Agent, Event, Post
from app.simulation.engine import SimulationEngine


def _seed(engine: SimulationEngine):
    engine.register_agent(agent_type="trader", name="T")
    engine.register_agent(agent_type="meme", name="M")
    engine.register_agent(agent_type="analyst", name="A")
    engine.db.commit()


def test_register_agent_persists(db):
    engine = SimulationEngine(db)
    row = engine.register_agent(agent_type="trader", name="Solo")
    db.commit()
    assert row.id is not None
    assert db.get(Agent, row.id).agent_type == "trader"


def test_run_tick_advances_and_persists(db):
    engine = SimulationEngine(db)
    _seed(engine)
    result = engine.run_tick()

    assert result["tick"] == 1
    assert "market_price" in result
    # Meme + analyst emit messages, so the feed should have grown.
    assert db.query(Post).count() >= 1
    # A price event is always recorded.
    assert db.query(Event).filter(Event.kind == "price").count() == 1


def test_ticks_increment(db):
    engine = SimulationEngine(db)
    _seed(engine)
    first = engine.run_tick()
    second = engine.run_tick()
    assert second["tick"] == first["tick"] + 1


def test_leaderboard_ranks_agents(db):
    engine = SimulationEngine(db)
    _seed(engine)
    engine.run_tick()
    board = engine.leaderboard()
    assert len(board) == 3
    scores = [row["score"] for row in board]
    assert scores == sorted(scores, reverse=True)


def test_get_state_snapshot(db):
    engine = SimulationEngine(db)
    _seed(engine)
    engine.run_tick()
    state = engine.get_state()
    assert state["agents"] == 3
    assert state["tick"] >= 1
