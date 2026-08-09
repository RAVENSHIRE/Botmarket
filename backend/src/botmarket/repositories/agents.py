"""Agent persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from botmarket.db.models import Agent, Reputation


def get(db: Session, agent_id: int) -> Agent | None:
    """Return an agent by id, or ``None``."""
    return db.get(Agent, agent_id)


def get_by_name(db: Session, name: str) -> Agent | None:
    """Return an agent by its unique name, or ``None``."""
    return db.scalar(select(Agent).where(Agent.name == name))


def get_by_key_hash(db: Session, key_hash: str) -> Agent | None:
    """Return the agent owning an API key hash, or ``None``."""
    return db.scalar(select(Agent).where(Agent.api_key_hash == key_hash))


def list_all(db: Session) -> list[Agent]:
    """Return every agent ordered by id."""
    return list(db.scalars(select(Agent).order_by(Agent.id)))


def list_active(db: Session) -> list[Agent]:
    """Return agents currently participating in the simulation."""
    return list(db.scalars(select(Agent).where(Agent.status == "active").order_by(Agent.id)))


def count(db: Session) -> int:
    """Return the total number of agents."""
    return db.scalar(select(func.count(Agent.id))) or 0


def add(db: Session, agent: Agent) -> Agent:
    """Persist a new agent and assign its primary key."""
    db.add(agent)
    db.flush()
    return agent


def record_reputation(
    db: Session, *, agent_id: int, delta: float, reason: str, tick: int
) -> Reputation:
    """Append a reputation change for an agent and apply it to the row.

    The running total on :class:`~botmarket.db.models.Agent` stays in step with
    the log, so callers never have to update both.
    """
    entry = Reputation(agent_id=agent_id, delta=delta, reason=reason, tick=tick)
    db.add(entry)
    agent = db.get(Agent, agent_id)
    if agent is not None:
        agent.reputation = round(agent.reputation + delta, 6)
    db.flush()
    return entry


def reputation_log(db: Session, agent_id: int, *, limit: int = 20) -> list[Reputation]:
    """Return an agent's most recent reputation changes, newest first."""
    stmt = (
        select(Reputation)
        .where(Reputation.agent_id == agent_id)
        .order_by(Reputation.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
