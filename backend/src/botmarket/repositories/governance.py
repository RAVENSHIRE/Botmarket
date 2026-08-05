"""Proposal and vote persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from botmarket.db.models import Proposal, Vote


def get(db: Session, proposal_id: int) -> Proposal | None:
    """Return a proposal by id, or ``None``."""
    return db.get(Proposal, proposal_id)


def list_all(db: Session, *, status: str | None = None, limit: int = 50) -> list[Proposal]:
    """Return proposals, newest first, optionally filtered by status."""
    stmt = select(Proposal).order_by(Proposal.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Proposal.status == status)
    return list(db.scalars(stmt))


def add(db: Session, proposal: Proposal) -> Proposal:
    """Persist a new proposal and assign its primary key."""
    db.add(proposal)
    db.flush()
    return proposal


def due_for_resolution(db: Session, tick: int) -> list[Proposal]:
    """Return open proposals whose voting window has closed by ``tick``."""
    stmt = select(Proposal).where(Proposal.status == "open", Proposal.closes_tick <= tick)
    return list(db.scalars(stmt))


def get_vote(db: Session, *, proposal_id: int, agent_id: int) -> Vote | None:
    """Return an agent's vote on a proposal, or ``None``."""
    return db.scalar(
        select(Vote).where(Vote.proposal_id == proposal_id, Vote.agent_id == agent_id)
    )


def add_vote(
    db: Session, *, proposal_id: int, agent_id: int, support: bool, weight: float, tick: int
) -> Vote:
    """Record a weighted vote on a proposal."""
    vote = Vote(
        proposal_id=proposal_id,
        agent_id=agent_id,
        support=support,
        weight=weight,
        tick=tick,
    )
    db.add(vote)
    db.flush()
    return vote


def tally(db: Session, proposal_id: int) -> tuple[float, float]:
    """Return ``(weight_for, weight_against)`` for a proposal."""

    def _sum(support: bool) -> float:
        total = db.scalar(
            select(func.coalesce(func.sum(Vote.weight), 0.0)).where(
                Vote.proposal_id == proposal_id, Vote.support == support
            )
        )
        return float(total or 0.0)

    return round(_sum(True), 6), round(_sum(False), 6)
