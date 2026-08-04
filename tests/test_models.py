"""Tests for the database models."""

from __future__ import annotations

from app.models import Agent, Event, Post, Reputation, Transaction


def test_agent_defaults(db):
    agent = Agent(name="Defaults", agent_type="trader")
    db.add(agent)
    db.commit()
    db.refresh(agent)
    assert agent.wallet == 1000.0
    assert agent.reputation == 0.0
    assert agent.status == "active"
    assert agent.created_at is not None


def test_post_relationship(db):
    agent = Agent(name="Poster", agent_type="meme")
    db.add(agent)
    db.flush()
    post = Post(author_id=agent.id, content="gm", kind="meme", tick=1)
    db.add(post)
    db.commit()
    db.refresh(agent)
    assert len(agent.posts) == 1
    assert agent.posts[0].author.name == "Poster"


def test_reputation_and_transaction(db):
    agent = Agent(name="Econ", agent_type="trader")
    db.add(agent)
    db.flush()
    db.add(Reputation(agent_id=agent.id, delta=0.5, reason="buy", tick=1))
    db.add(Transaction(agent_id=agent.id, amount=100.0, kind="buy", tick=1))
    db.add(Event(tick=1, kind="news", description="something happened", magnitude=1.0))
    db.commit()
    assert db.query(Reputation).count() == 1
    assert db.query(Transaction).count() == 1
    assert db.query(Event).count() == 1
