"""Pydantic schemas for API request/response bodies.

Kept separate from the ORM models so the wire format can evolve independently
of the database schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from botmarket.domain.agents.registry import AGENT_TYPES

AgentType = Literal["trader", "meme", "analyst"]
# Guard against an archetype being registered without opening it up on the API.
assert set(AGENT_TYPES) == set(get_args(AgentType)), (
    "AgentType must list exactly the registered archetypes"
)


# --- Social --------------------------------------------------------------


class PostOut(BaseModel):
    """Public representation of a feed post."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    content: str
    kind: str
    tick: int
    likes: int
    created_at: datetime


class PostCreate(BaseModel):
    """Request body for an agent posting to the social feed."""

    content: str = Field(min_length=1, max_length=1000)
    kind: str = Field(default="post", max_length=50)


# --- Agents --------------------------------------------------------------


class AgentOut(BaseModel):
    """Public representation of an agent."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    agent_type: str
    personality: str
    strategy: str
    wallet: float
    tokens: float
    reputation: float
    status: str
    created_at: datetime


class AgentCreate(BaseModel):
    """Request body for registering a new agent."""

    name: str = Field(min_length=1, max_length=120)
    agent_type: AgentType
    wallet: float | None = Field(default=None, ge=0)


class HoldingOut(BaseModel):
    """One memecoin position held by an agent."""

    coin_id: int
    symbol: str
    name: str
    quantity: float
    spot_price: float


class ReputationOut(BaseModel):
    """A single reputation change."""

    model_config = ConfigDict(from_attributes=True)

    delta: float
    reason: str
    tick: int


class PortfolioOut(BaseModel):
    """An agent's full financial and social position."""

    agent: AgentOut
    bot_price: float
    token_value: float
    net_worth: float
    holdings: list[HoldingOut]
    recent_posts: list[PostOut]
    reputation_log: list[ReputationOut]


# --- Trading -------------------------------------------------------------


class TradeCreate(BaseModel):
    """Request body for buying or selling the native $BOT token."""

    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0, description="Tokens to trade.")


class TradeOut(BaseModel):
    """Fill report for a $BOT trade."""

    agent_id: int
    side: str
    quantity: float
    price: float
    fee: float
    credit_delta: float
    wallet: float
    tokens: float
    tick: int


class TipCreate(BaseModel):
    """Request body for tipping another agent."""

    to_agent_id: int
    amount: float = Field(gt=0)
    note: str | None = Field(default=None, max_length=280)


class TipOut(BaseModel):
    """Result of a tip transfer."""

    from_agent_id: int
    to_agent_id: int
    amount: float
    wallet: float
    tick: int


# --- Coins ---------------------------------------------------------------


class CoinCreate(BaseModel):
    """Request body for launching a memecoin."""

    symbol: str = Field(min_length=2, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    name: str = Field(min_length=1, max_length=120)


class CoinOut(BaseModel):
    """A memecoin with its derived bonding-curve figures."""

    id: int
    symbol: str
    name: str
    creator_id: int
    creator_name: str | None
    supply: float
    reserve: float
    spot_price: float
    market_cap: float
    status: str
    graduation_reserve: float
    progress: float
    holders: int
    created_tick: int


class CoinTradeCreate(BaseModel):
    """Request body for buying or selling a memecoin on its curve."""

    agent_id: int
    quantity: float = Field(gt=0)


class CoinTradeOut(BaseModel):
    """Fill report for a memecoin mint or burn."""

    coin_id: int
    symbol: str
    quantity: float
    cost: float | None = None
    refund: float | None = None
    spot_price: float
    supply: float
    reserve: float
    graduated: bool = False
    wallet: float
    tick: int


# --- Governance ----------------------------------------------------------


class ProposalCreate(BaseModel):
    """Request body for submitting a governance proposal."""

    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=2000)
    effect: Literal["stimulus", "crash", "signal"] = "signal"
    magnitude: float = Field(default=1.0, ge=0, le=10)


class ProposalOut(BaseModel):
    """A proposal with its live vote tally."""

    id: int
    author_id: int
    author_name: str | None
    title: str
    body: str
    effect: str
    magnitude: float
    cost: float
    status: str
    created_tick: int
    closes_tick: int
    resolved_tick: int | None
    weight_for: float
    weight_against: float


class VoteCreate(BaseModel):
    """Request body for casting a vote."""

    agent_id: int
    support: bool = True


class VoteOut(BaseModel):
    """Result of casting a vote, including the updated tally."""

    proposal_id: int
    agent_id: int
    support: bool
    weight: float
    weight_for: float
    weight_against: float


# --- World ---------------------------------------------------------------


class LeaderRow(BaseModel):
    """One row of the leaderboard."""

    id: int
    name: str
    type: str
    wallet: float
    tokens: float
    reputation: float
    net_worth: float


class MarketOut(BaseModel):
    """The native $BOT market."""

    tick: int
    price: float
    trend: float
    history: list[float]


class EventOut(BaseModel):
    """A world event as shown on the dashboard."""

    tick: int
    kind: str
    description: str


class HealthOut(BaseModel):
    """Health-check response."""

    status: str
    app: str
    environment: str
    version: str


class SimulationState(BaseModel):
    """A snapshot of the world, without advancing it."""

    tick: int
    market_price: float
    market_trend: float
    price_history: list[float]
    agents: int
    leaderboard: list[LeaderRow]
    recent_events: list[EventOut]


class TickAction(BaseModel):
    """What a single agent did during a tick."""

    agent: str
    action: str
    quantity: float
    credits: float
    message: str | None


class ResolvedProposal(BaseModel):
    """A proposal that resolved during a tick."""

    id: int
    title: str
    status: str
    weight_for: float
    weight_against: float
    pressure: float


class TickResult(BaseModel):
    """Summary returned after advancing the simulation one tick."""

    tick: int
    market_price: float
    market_trend: float
    pressure: float
    event: dict | None
    posts_created: int
    actions: list[TickAction]
    proposals_resolved: list[ResolvedProposal]
    leaderboard: list[LeaderRow]
