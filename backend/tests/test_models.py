"""Tests for the database models."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from botmarket.db.models import (
    Agent,
    Coin,
    Event,
    Holding,
    Post,
    Proposal,
    Reputation,
    Transaction,
    Vote,
)


def _agent(db, name: str = "A", agent_type: str = "trader") -> Agent:
    agent = Agent(name=name, agent_type=agent_type)
    db.add(agent)
    db.flush()
    return agent


def test_agent_defaults(db):
    agent = _agent(db, "Defaults")
    db.commit()
    db.refresh(agent)
    assert agent.wallet == 1000.0
    assert agent.tokens == 0.0
    assert agent.reputation == 0.0
    assert agent.status == "active"
    assert agent.created_at is not None


def test_post_relationship(db):
    agent = _agent(db, "Poster", "meme")
    db.add(Post(author_id=agent.id, content="gm", kind="meme", tick=1))
    db.commit()
    db.refresh(agent)
    assert len(agent.posts) == 1
    assert agent.posts[0].author.name == "Poster"


def test_reputation_and_transaction(db):
    agent = _agent(db, "Econ")
    db.add(Reputation(agent_id=agent.id, delta=0.5, reason="buy", tick=1))
    db.add(Transaction(agent_id=agent.id, amount=-100.0, quantity=1.0, kind="buy", tick=1))
    db.add(Event(tick=1, kind="news", description="something happened", magnitude=1.0))
    db.commit()
    assert db.query(Reputation).count() == 1
    assert db.query(Transaction).count() == 1
    assert db.query(Event).count() == 1


def test_coin_and_holding_relationships(db):
    creator = _agent(db, "Launcher", "meme")
    coin = Coin(symbol="WOOF", name="Woof", creator_id=creator.id)
    db.add(coin)
    db.flush()
    db.add(Holding(agent_id=creator.id, coin_id=coin.id, quantity=10.0))
    db.commit()
    db.refresh(coin)
    assert coin.status == "live"
    assert coin.creator.name == "Launcher"
    assert coin.holdings[0].quantity == 10.0


def test_one_holding_row_per_agent_and_coin(db):
    agent = _agent(db, "Holder")
    coin = Coin(symbol="DUP", name="Dup", creator_id=agent.id)
    db.add(coin)
    db.flush()
    db.add_all(
        [
            Holding(agent_id=agent.id, coin_id=coin.id, quantity=1.0),
            Holding(agent_id=agent.id, coin_id=coin.id, quantity=2.0),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_an_agent_votes_once_per_proposal(db):
    author = _agent(db, "Author", "analyst")
    proposal = Proposal(author_id=author.id, title="Ship it", closes_tick=3)
    db.add(proposal)
    db.flush()
    db.add_all(
        [
            Vote(proposal_id=proposal.id, agent_id=author.id, support=True, weight=1.0),
            Vote(proposal_id=proposal.id, agent_id=author.id, support=False, weight=1.0),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()
