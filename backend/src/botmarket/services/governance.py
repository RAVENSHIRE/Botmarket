"""Agent governance: funded proposals and token-weighted voting.

Submitting a proposal burns credits, so ideas carry a cost. Voting weight comes
from $BOT holdings and reputation, plus a flat unit so every registered agent
retains a voice. Proposals resolve automatically a fixed number of ticks after
they open, and a passing proposal becomes a world event the whole simulation
reacts to.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.config import get_settings
from botmarket.db.models import Agent, Proposal
from botmarket.domain.errors import Conflict, InsufficientFunds, InvalidAction, NotFound
from botmarket.repositories import agents as agents_repo
from botmarket.repositories import events as events_repo
from botmarket.repositories import governance as governance_repo
from botmarket.repositories import posts as posts_repo
from botmarket.repositories import transactions as tx_repo
from botmarket.services import agents as agents_service
from botmarket.services import market as market_service

# Effects a proposal may apply to the world if it passes, and the sign of the
# market pressure each one creates.
EFFECTS: dict[str, float] = {
    "stimulus": 1.0,
    "crash": -1.0,
    "signal": 0.0,
}


def require(db: Session, proposal_id: int) -> Proposal:
    """Return a proposal or raise :class:`NotFound`."""
    proposal = governance_repo.get(db, proposal_id)
    if proposal is None:
        raise NotFound(f"Proposal {proposal_id} not found")
    return proposal


def voting_weight(agent: Agent) -> float:
    """Return an agent's vote weight.

    The flat unit means a broke agent still counts; tokens and reputation are
    what let a successful one count for more.
    """
    return round(1.0 + agent.tokens + max(agent.reputation, 0.0), 6)


def propose(
    db: Session,
    *,
    agent_id: int,
    title: str,
    body: str = "",
    effect: str = "signal",
    magnitude: float = 1.0,
) -> Proposal:
    """Submit a proposal, burning the proposal fee from the author's wallet.

    Raises:
        InvalidAction: If the effect is unknown.
        InsufficientFunds: If the author cannot pay the fee.
        NotFound: If the author does not exist.
    """
    if effect not in EFFECTS:
        raise InvalidAction(f"Effect must be one of {', '.join(EFFECTS)}")

    agent = agents_service.require(db, agent_id)
    settings = get_settings()
    if agent.wallet < settings.proposal_cost:
        raise InsufficientFunds(
            f"Proposing costs {settings.proposal_cost:.0f} credits "
            f"but the agent holds {agent.wallet:.2f}"
        )

    tick = market_service.next_tick(db)
    agent.wallet = round(agent.wallet - settings.proposal_cost, 6)

    proposal = governance_repo.add(
        db,
        Proposal(
            author_id=agent_id,
            title=title,
            body=body,
            effect=effect,
            magnitude=abs(magnitude),
            cost=settings.proposal_cost,
            status="open",
            created_tick=tick,
            closes_tick=tick + settings.proposal_voting_ticks,
        ),
    )
    tx_repo.add(
        db,
        agent_id=agent_id,
        kind="proposal",
        amount=-settings.proposal_cost,
        tick=tick,
    )
    posts_repo.add(
        db,
        author_id=agent_id,
        content=f"proposal #{proposal.id}: {title}",
        kind="proposal",
        tick=tick,
    )
    db.commit()
    db.refresh(proposal)
    return proposal


def vote(db: Session, *, proposal_id: int, agent_id: int, support: bool) -> dict:
    """Cast a weighted vote on an open proposal.

    Raises:
        InvalidAction: If voting has closed.
        Conflict: If the agent has already voted on this proposal.
        NotFound: If the proposal or agent does not exist.
    """
    proposal = require(db, proposal_id)
    agent = agents_service.require(db, agent_id)
    if proposal.status != "open":
        raise InvalidAction(f"Proposal {proposal_id} is already {proposal.status}")
    if governance_repo.get_vote(db, proposal_id=proposal_id, agent_id=agent_id) is not None:
        raise Conflict(f"Agent {agent_id} has already voted on proposal {proposal_id}")

    weight = voting_weight(agent)
    governance_repo.add_vote(
        db,
        proposal_id=proposal_id,
        agent_id=agent_id,
        support=support,
        weight=weight,
        tick=market_service.next_tick(db),
    )
    db.commit()

    weight_for, weight_against = governance_repo.tally(db, proposal_id)
    return {
        "proposal_id": proposal_id,
        "agent_id": agent_id,
        "support": support,
        "weight": weight,
        "weight_for": weight_for,
        "weight_against": weight_against,
    }


def describe(db: Session, proposal: Proposal) -> dict:
    """Return a proposal with its current tally, for API responses."""
    weight_for, weight_against = governance_repo.tally(db, proposal.id)
    return {
        "id": proposal.id,
        "author_id": proposal.author_id,
        "author_name": proposal.author.name if proposal.author else None,
        "title": proposal.title,
        "body": proposal.body,
        "effect": proposal.effect,
        "magnitude": proposal.magnitude,
        "cost": proposal.cost,
        "status": proposal.status,
        "created_tick": proposal.created_tick,
        "closes_tick": proposal.closes_tick,
        "resolved_tick": proposal.resolved_tick,
        "weight_for": weight_for,
        "weight_against": weight_against,
    }


def resolve_due(db: Session, tick: int) -> list[dict]:
    """Resolve every proposal whose voting window has closed.

    Called from inside a simulation tick, so this does **not** commit — the
    engine owns the transaction. A proposal passes only if it clears quorum and
    support outweighs opposition; passing ones emit a world event whose
    magnitude feeds into the same tick's price move.

    Returns:
        One summary dict per resolved proposal.
    """
    settings = get_settings()
    resolved: list[dict] = []

    for proposal in governance_repo.due_for_resolution(db, tick):
        weight_for, weight_against = governance_repo.tally(db, proposal.id)
        total = weight_for + weight_against
        passed = total >= settings.proposal_quorum and weight_for > weight_against

        proposal.status = "passed" if passed else "rejected"
        proposal.resolved_tick = tick

        pressure = 0.0
        if passed:
            pressure = EFFECTS[proposal.effect] * proposal.magnitude
            events_repo.add(
                db,
                tick=tick,
                kind="governance",
                description=f"Proposal #{proposal.id} passed: {proposal.title}",
                magnitude=pressure,
            )
            agents_repo.record_reputation(
                db,
                agent_id=proposal.author_id,
                delta=0.5,
                reason=f"proposal #{proposal.id} passed",
                tick=tick,
            )

        resolved.append(
            {
                "id": proposal.id,
                "title": proposal.title,
                "status": proposal.status,
                "weight_for": weight_for,
                "weight_against": weight_against,
                "pressure": pressure,
            }
        )

    return resolved
