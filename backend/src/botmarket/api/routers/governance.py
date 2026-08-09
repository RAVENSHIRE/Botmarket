"""Governance endpoints.

Submitting lives on the authoring agent (``POST /agents/{id}/proposals``);
reading the ballot and voting happen here. Proposals resolve automatically
during a simulation tick once their voting window closes.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from botmarket.api.deps import CallerAgent, DbSession
from botmarket.api.schemas import ProposalOut, VoteCreate, VoteOut
from botmarket.repositories import governance as governance_repo
from botmarket.services import governance as governance_service

router = APIRouter(prefix="/proposals", tags=["governance"])


@router.get("", response_model=list[ProposalOut])
def list_proposals(
    db: DbSession,
    status: str | None = Query(default=None, description="Filter: open, passed or rejected."),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List proposals with their live vote tallies, newest first."""
    return [
        governance_service.describe(db, p)
        for p in governance_repo.list_all(db, status=status, limit=limit)
    ]


@router.get("/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: int, db: DbSession):
    """Fetch one proposal with its tally."""
    return governance_service.describe(db, governance_service.require(db, proposal_id))


@router.post("/{proposal_id}/votes", response_model=VoteOut)
def cast_vote(
    proposal_id: int, payload: VoteCreate, db: DbSession, caller: CallerAgent
):
    """Cast a token-weighted vote on an open proposal.

    The vote is cast as the key's owner, so an agent cannot vote another
    agent's weight by naming it in the body.
    """
    return governance_service.vote(
        db, proposal_id=proposal_id, agent_id=caller.id, support=payload.support
    )
