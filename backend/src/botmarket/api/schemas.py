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


class AgentCreated(BaseModel):
    """The response to registering an agent.

    The API key appears here and nowhere else, ever. Store it now.
    """

    agent: AgentOut
    api_key: str = Field(
        description="Shown once. Send as `Authorization: Bearer <key>` or `X-API-Key`."
    )


class ApiKeyOut(BaseModel):
    """A freshly issued API key."""

    agent_id: int
    api_key: str


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
    description: str = Field(default="", max_length=2000)
    image_url: str | None = Field(default=None, max_length=500)


class CoinOut(BaseModel):
    """A memecoin with its derived bonding-curve figures."""

    id: int
    symbol: str
    name: str
    description: str
    image_url: str | None
    creator_id: int
    creator_name: str | None
    supply: float
    curve_supply: float
    total_supply: float
    reserve: float
    spot_price: float
    market_cap: float
    graduation_market_cap: float
    progress: float
    remaining_supply: float
    status: str
    holders: int
    volume: float
    trades: int
    reply_count: int
    creator_fees_earned: float
    fee_bps: float
    created_tick: int
    last_trade_tick: int
    graduated_tick: int | None


class CoinTradeCreate(BaseModel):
    """Request body for buying or selling a memecoin on its curve.

    The buyer is the API key's owner, so there is no ``agent_id`` to spoof.
    """

    quantity: float = Field(gt=0)


class CoinTradeOut(BaseModel):
    """Fill report for a memecoin mint or burn."""

    coin_id: int
    symbol: str
    quantity: float
    cost: float | None = None
    refund: float | None = None
    fee: float = 0.0
    spot_price: float
    market_cap: float
    supply: float
    reserve: float
    graduated: bool = False
    wallet: float
    tick: int


class CoinTradeRow(BaseModel):
    """One entry in a coin's trade feed."""

    agent_id: int
    agent_name: str | None
    side: str
    quantity: float
    credits: float
    tick: int
    symbol: str


class CoinReplyCreate(BaseModel):
    """Request body for commenting on a coin."""

    content: str = Field(min_length=1, max_length=1000)


class CoinReplyOut(BaseModel):
    """A comment on a coin's thread."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    coin_id: int
    agent_id: int
    content: str
    tick: int
    created_at: datetime


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
    """Request body for casting a vote.

    The voter is the API key's owner, so weight cannot be voted on another
    agent's behalf.
    """

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


# --- Live trading --------------------------------------------------------


class VenueInfo(BaseModel):
    """A venue this deployment can use."""

    name: str
    environments: list[str]
    requires_credentials: bool
    available: bool
    mainnet_allowed: bool
    # What this venue calls the two halves of its credential, for the UI.
    public_label: str = ""
    secret_label: str = ""


class RiskLimitsOut(BaseModel):
    """The risk envelope currently in force."""

    trading_enabled: bool
    max_leverage: int
    min_order_value: float
    max_order_value: float
    max_position_value: float
    max_gross_notional: float
    max_daily_loss: float
    allow_mainnet: bool


class VenueAccountCreate(BaseModel):
    """Request body for linking an agent to a venue.

    ``secret`` is write-only: it is encrypted on arrival and no endpoint ever
    returns it.
    """

    venue: Literal["paper", "hyperliquid", "alpaca"]
    environment: Literal["paper", "testnet", "mainnet"]
    label: str = Field(default="", max_length=120)
    wallet_address: str | None = Field(
        default=None,
        max_length=120,
        description="Public half of the credential: a wallet address, or an API key ID.",
    )
    secret: str | None = Field(
        default=None,
        max_length=512,
        description="API secret or wallet private key. Stored encrypted, never returned.",
    )


class PositionOut(BaseModel):
    """One open position."""

    symbol: str
    side: str
    size: float
    entry_price: float
    mark_price: float
    leverage: int
    unrealised_pnl: float
    liquidation_price: float | None = None


class VenueAccountOut(BaseModel):
    """A venue account, with no credential material in it."""

    id: int
    agent_id: int
    venue: str
    environment: str
    label: str
    wallet_address: str | None
    has_credentials: bool
    active: bool
    realised_loss_today: float
    is_real_money: bool
    equity: float | None = None
    available: float | None = None
    gross_notional: float | None = None
    positions: list[PositionOut] = Field(default_factory=list)


class VenueOrderCreate(BaseModel):
    """Request body for placing a live order."""

    symbol: str = Field(min_length=1, max_length=40)
    side: Literal["buy", "sell"]
    size: float = Field(gt=0)
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = Field(default=None, gt=0)
    leverage: int = Field(default=1, ge=1, le=50)
    reduce_only: bool = False
    confirm_real_money: bool = Field(
        default=False,
        description="Required for mainnet orders. Configuration alone is never consent.",
    )


class VenueOrderOut(BaseModel):
    """The outcome of an order attempt."""

    account_id: int
    accepted: bool
    symbol: str
    side: str
    filled_size: float
    average_price: float
    notional: float
    environment: str
    order_id: str | None
    reason: str | None
    is_real_money: bool


class VenueOrderRow(BaseModel):
    """One row of the order audit trail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    side: str
    size: float
    price: float
    leverage: int
    reduce_only: bool
    environment: str
    status: str
    reason: str | None
    venue_order_id: str | None
    created_at: datetime


# --- Factors -------------------------------------------------------------


class FactorInfo(BaseModel):
    """A registered factor."""

    name: str
    category: str
    description: str
    lookback: int


class FactorScoreOut(BaseModel):
    """How well a factor predicted forward returns."""

    name: str
    horizon: int
    samples: int
    ic: float
    rank_ic: float
    icir: float
    hit_rate: float
    significant: bool


class FactorEvaluation(BaseModel):
    """Every factor scored for one symbol, plus the blended signal."""

    symbol: str
    venue: str
    environment: str
    interval: str
    horizon: int
    candles: int
    last_price: float
    values: dict[str, float | None]
    scores: list[FactorScoreOut]
    signal: float


class FactorDetail(BaseModel):
    """One factor's current value and score for a symbol."""

    symbol: str
    factor: FactorInfo
    value: float | None
    score: FactorScoreOut


class MarketRow(BaseModel):
    """A compact per-symbol signal row."""

    symbol: str
    price: float | None = None
    signal: float | None = None
    best_factor: str | None = None
    best_ic: float | None = None
    significant_factors: int | None = None
    error: str | None = None
