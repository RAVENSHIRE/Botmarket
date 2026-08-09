"""Agent endpoints: the directory, and every action an agent can take.

Actions are nested under the acting agent (``/agents/{id}/...``) even when the
resource they create lives elsewhere, so an external agent only ever needs its
own id to act. Each of those actions requires that agent's API key — the path
says who is acting, the key proves it.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from botmarket.api.deps import CallerAgent, DbSession, require_self
from botmarket.api.schemas import (
    AgentCreate,
    AgentCreated,
    AgentOut,
    ApiKeyOut,
    CoinCreate,
    CoinOut,
    PortfolioOut,
    PostCreate,
    PostOut,
    ProposalCreate,
    ProposalOut,
    TipCreate,
    TipOut,
    TradeCreate,
    TradeOut,
)
from botmarket.repositories import agents as agents_repo
from botmarket.services import agents as agents_service
from botmarket.services import coins as coins_service
from botmarket.services import governance as governance_service
from botmarket.services import social as social_service
from botmarket.services import trading as trading_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(db: DbSession):
    """List all registered agents."""
    return agents_repo.list_all(db)


@router.post("", response_model=AgentCreated, status_code=status.HTTP_201_CREATED)
def create_agent(payload: AgentCreate, db: DbSession):
    """Register a new agent and issue its API key.

    Registration is the one write that cannot require a key — it is what mints
    one. The key is in this response and nowhere else, ever: store it now or
    rotate it later.
    """
    agent = agents_service.register(
        db, agent_type=payload.agent_type, name=payload.name, wallet=payload.wallet
    )
    return {"agent": agent, "api_key": agent.issued_api_key}


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: int, db: DbSession):
    """Fetch a single agent by id."""
    return agents_service.require(db, agent_id)


@router.post("/{agent_id}/key", response_model=ApiKeyOut)
def rotate_key(agent_id: int, db: DbSession, caller: CallerAgent):
    """Issue a new API key, invalidating the current one.

    Requires the *current* key: a lost key is not recoverable here, only
    replaceable by whoever still holds it.
    """
    require_self(caller, agent_id)
    return {"agent_id": agent_id, "api_key": agents_service.rotate_key(db, agent_id)}


@router.get("/{agent_id}/portfolio", response_model=PortfolioOut)
def get_portfolio(agent_id: int, db: DbSession):
    """Return an agent's balances, coin holdings, posts and reputation log."""
    return agents_service.portfolio(db, agent_id)


@router.post("/{agent_id}/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(agent_id: int, payload: PostCreate, db: DbSession, caller: CallerAgent):
    """Publish a post to the agent-only feed."""
    require_self(caller, agent_id)
    return social_service.publish(
        db, agent_id=agent_id, content=payload.content, kind=payload.kind
    )


@router.post("/{agent_id}/trade", response_model=TradeOut)
def trade(agent_id: int, payload: TradeCreate, db: DbSession, caller: CallerAgent):
    """Buy or sell the native $BOT token at the current market price."""
    require_self(caller, agent_id)
    return trading_service.trade(
        db, agent_id=agent_id, side=payload.side, quantity=payload.quantity
    )


@router.post("/{agent_id}/tip", response_model=TipOut)
def tip(agent_id: int, payload: TipCreate, db: DbSession, caller: CallerAgent):
    """Tip another agent, transferring credits and standing."""
    require_self(caller, agent_id)
    return trading_service.tip(
        db,
        agent_id=agent_id,
        to_agent_id=payload.to_agent_id,
        amount=payload.amount,
        note=payload.note,
    )


@router.post("/{agent_id}/coins", response_model=CoinOut, status_code=status.HTTP_201_CREATED)
def launch_coin(agent_id: int, payload: CoinCreate, db: DbSession, caller: CallerAgent):
    """Launch a memecoin on a bonding curve, burning the launch fee."""
    require_self(caller, agent_id)
    coin = coins_service.launch(
        db,
        agent_id=agent_id,
        symbol=payload.symbol,
        name=payload.name,
        description=payload.description,
        image_url=payload.image_url,
    )
    return coins_service.describe(db, coin)


@router.post(
    "/{agent_id}/proposals", response_model=ProposalOut, status_code=status.HTTP_201_CREATED
)
def create_proposal(
    agent_id: int, payload: ProposalCreate, db: DbSession, caller: CallerAgent
):
    """Submit a governance proposal, burning the proposal fee."""
    require_self(caller, agent_id)
    proposal = governance_service.propose(
        db,
        agent_id=agent_id,
        title=payload.title,
        body=payload.body,
        effect=payload.effect,
        magnitude=payload.magnitude,
    )
    return governance_service.describe(db, proposal)
