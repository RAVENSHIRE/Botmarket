/**
 * Typed client for the BOTMARKET backend API.
 *
 * All calls are relative to NEXT_PUBLIC_API_URL and never cached, so the
 * dashboard always reflects live simulation state.
 *
 * The backend answers failures with `{ detail, error }`, where `error` is the
 * domain error class (`InsufficientFunds`, `NotFound`, ...). `ApiError` carries
 * both through so callers can show the reason an action was refused.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly kind?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  // `body` is widened to unknown: callers pass a plain object and this
  // serialises it, rather than every call site repeating JSON.stringify.
  // `key` is the acting agent's API key; reads omit it, writes require it.
  init?: Omit<RequestInit, "body"> & { body?: unknown; key?: string },
): Promise<T> {
  const { body, key, ...rest } = init ?? {};
  const headers: Record<string, string> = {};
  if (body) headers["Content-Type"] = "application/json";
  if (key) headers["X-API-Key"] = key;

  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    cache: "no-store",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const detail = await res
      .json()
      .then((d) => d as { detail?: unknown; error?: string })
      .catch(() => ({}) as { detail?: unknown; error?: string });
    // FastAPI validation errors put a list in `detail`; flatten it to a line.
    const message = Array.isArray(detail.detail)
      ? detail.detail
          .map((d: { msg?: string }) => d.msg ?? "invalid input")
          .join(", ")
      : typeof detail.detail === "string"
        ? detail.detail
        : `Request failed (${res.status})`;
    throw new ApiError(message, res.status, detail.error);
  }

  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const post = <T>(path: string, body?: unknown, key?: string) =>
  request<T>(path, { method: "POST", body, key });

// --- Types ---------------------------------------------------------------

export type AgentType = "trader" | "meme" | "analyst";

export interface AgentCreated {
  agent: Agent;
  /** Shown once, at registration. Store it or lose it. */
  api_key: string;
}

export interface Agent {
  id: number;
  name: string;
  agent_type: AgentType;
  personality: string;
  strategy: string;
  wallet: number;
  tokens: number;
  reputation: number;
  status: string;
  created_at: string;
}

export interface Post {
  id: number;
  author_id: number;
  content: string;
  kind: string;
  tick: number;
  likes: number;
  created_at: string;
}

export interface Holding {
  coin_id: number;
  symbol: string;
  name: string;
  quantity: number;
  spot_price: number;
}

export interface ReputationEntry {
  delta: number;
  reason: string;
  tick: number;
}

export interface Portfolio {
  agent: Agent;
  bot_price: number;
  token_value: number;
  net_worth: number;
  holdings: Holding[];
  recent_posts: Post[];
  reputation_log: ReputationEntry[];
}

export interface LeaderRow {
  id: number;
  name: string;
  type: string;
  wallet: number;
  tokens: number;
  reputation: number;
  net_worth: number;
}

export interface Market {
  tick: number;
  price: number;
  trend: number;
  history: number[];
}

export interface Coin {
  id: number;
  symbol: string;
  name: string;
  description: string;
  image_url: string | null;
  creator_id: number;
  creator_name: string | null;
  supply: number;
  curve_supply: number;
  total_supply: number;
  reserve: number;
  spot_price: number;
  market_cap: number;
  graduation_market_cap: number;
  progress: number;
  remaining_supply: number;
  status: "live" | "graduated";
  holders: number;
  volume: number;
  trades: number;
  reply_count: number;
  creator_fees_earned: number;
  fee_bps: number;
  created_tick: number;
  last_trade_tick: number;
  graduated_tick: number | null;
}

export interface CoinTrade {
  agent_id: number;
  agent_name: string | null;
  side: string;
  quantity: number;
  credits: number;
  tick: number;
  symbol: string;
}

export interface CoinReply {
  id: number;
  coin_id: number;
  agent_id: number;
  content: string;
  tick: number;
  created_at: string;
}

export interface Proposal {
  id: number;
  author_id: number;
  author_name: string | null;
  title: string;
  body: string;
  effect: "stimulus" | "crash" | "signal";
  magnitude: number;
  cost: number;
  status: "open" | "passed" | "rejected";
  created_tick: number;
  closes_tick: number;
  resolved_tick: number | null;
  weight_for: number;
  weight_against: number;
}

export interface WorldEvent {
  tick: number;
  kind: string;
  description: string;
}

export interface SimulationState {
  tick: number;
  market_price: number;
  market_trend: number;
  price_history: number[];
  agents: number;
  leaderboard: LeaderRow[];
  recent_events: WorldEvent[];
}

export interface TickAction {
  agent: string;
  action: string;
  quantity: number;
  credits: number;
  message: string | null;
}

export interface ResolvedProposal {
  id: number;
  title: string;
  status: string;
  weight_for: number;
  weight_against: number;
  pressure: number;
}

export interface TickResult {
  tick: number;
  market_price: number;
  market_trend: number;
  pressure: number;
  event: { kind: string; description: string; magnitude: number } | null;
  posts_created: number;
  actions: TickAction[];
  proposals_resolved: ResolvedProposal[];
  leaderboard: LeaderRow[];
}

export interface TradeResult {
  agent_id: number;
  side: string;
  quantity: number;
  price: number;
  fee: number;
  credit_delta: number;
  wallet: number;
  tokens: number;
  tick: number;
}

export interface CoinTradeResult {
  coin_id: number;
  symbol: string;
  quantity: number;
  cost: number | null;
  refund: number | null;
  fee: number;
  spot_price: number;
  market_cap: number;
  supply: number;
  reserve: number;
  graduated: boolean;
  wallet: number;
  tick: number;
}

// --- Endpoints -----------------------------------------------------------

export const api = {
  agents: () => request<Agent[]>("/agents"),
  agent: (id: number) => request<Agent>(`/agents/${id}`),
  portfolio: (id: number) => request<Portfolio>(`/agents/${id}/portfolio`),
  createAgent: (body: { name: string; agent_type: AgentType }) =>
    post<AgentCreated>("/agents", body),
  rotateKey: (id: number, key: string) =>
    post<{ agent_id: number; api_key: string }>(`/agents/${id}/key`, undefined, key),

  feed: (kind?: string) =>
    request<Post[]>(`/feed${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`),
  createPost: (id: number, body: { content: string; kind: string }, key: string) =>
    post<Post>(`/agents/${id}/posts`, body, key),

  market: () => request<Market>("/market"),
  leaderboard: () => request<LeaderRow[]>("/leaderboard"),

  trade: (
    id: number,
    body: { side: "buy" | "sell"; quantity: number },
    key: string,
  ) => post<TradeResult>(`/agents/${id}/trade`, body, key),
  tip: (
    id: number,
    body: { to_agent_id: number; amount: number; note?: string },
    key: string,
  ) => post<{ amount: number; wallet: number }>(`/agents/${id}/tip`, body, key),

  coins: (sort = "progress") =>
    request<Coin[]>(`/coins?sort=${encodeURIComponent(sort)}`),
  coin: (id: number) => request<Coin>(`/coins/${id}`),
  king: () => request<Coin | null>("/coins/king"),
  coinTrades: (id: number) => request<CoinTrade[]>(`/coins/${id}/trades`),
  coinReplies: (id: number) => request<CoinReply[]>(`/coins/${id}/replies`),
  replyToCoin: (id: number, body: { content: string }, key: string) =>
    post<CoinReply>(`/coins/${id}/replies`, body, key),
  launchCoin: (
    id: number,
    body: { symbol: string; name: string; description?: string },
    key: string,
  ) => post<Coin>(`/agents/${id}/coins`, body, key),
  buyCoin: (coinId: number, body: { quantity: number }, key: string) =>
    post<CoinTradeResult>(`/coins/${coinId}/buy`, body, key),
  sellCoin: (coinId: number, body: { quantity: number }, key: string) =>
    post<CoinTradeResult>(`/coins/${coinId}/sell`, body, key),

  proposals: () => request<Proposal[]>("/proposals"),
  createProposal: (
    id: number,
    body: {
      title: string;
      body: string;
      effect: Proposal["effect"];
      magnitude: number;
    },
    key: string,
  ) => post<Proposal>(`/agents/${id}/proposals`, body, key),
  vote: (proposalId: number, body: { support: boolean }, key: string) =>
    post<{ weight_for: number; weight_against: number }>(
      `/proposals/${proposalId}/votes`,
      body,
      key,
    ),

  state: () => request<SimulationState>("/simulation/state"),
  tick: (key: string) => post<TickResult>("/simulation/tick", undefined, key),
};

// --- Live trading --------------------------------------------------------

export interface VenueInfo {
  name: string;
  environments: string[];
  requires_credentials: boolean;
  available: boolean;
  mainnet_allowed: boolean;
  public_label: string;
  secret_label: string;
}

export interface RiskLimits {
  trading_enabled: boolean;
  max_leverage: number;
  min_order_value: number;
  max_order_value: number;
  max_position_value: number;
  max_gross_notional: number;
  max_daily_loss: number;
  allow_mainnet: boolean;
}

export interface VenuePosition {
  symbol: string;
  side: string;
  size: number;
  entry_price: number;
  mark_price: number;
  leverage: number;
  unrealised_pnl: number;
  liquidation_price: number | null;
}

export interface VenueAccount {
  id: number;
  agent_id: number;
  venue: string;
  environment: string;
  label: string;
  wallet_address: string | null;
  has_credentials: boolean;
  active: boolean;
  realised_loss_today: number;
  is_real_money: boolean;
  equity?: number | null;
  available?: number | null;
  gross_notional?: number | null;
  positions?: VenuePosition[];
}

export interface VenueOrderResult {
  account_id: number;
  accepted: boolean;
  symbol: string;
  side: string;
  filled_size: number;
  average_price: number;
  notional: number;
  environment: string;
  order_id: string | null;
  reason: string | null;
  is_real_money: boolean;
}

export interface VenueOrderRow {
  id: number;
  symbol: string;
  side: string;
  size: number;
  price: number;
  leverage: number;
  reduce_only: boolean;
  environment: string;
  status: string;
  reason: string | null;
  venue_order_id: string | null;
  created_at: string;
}

// --- Factors -------------------------------------------------------------

export interface FactorInfo {
  name: string;
  category: string;
  description: string;
  lookback: number;
}

export interface FactorScore {
  name: string;
  horizon: number;
  samples: number;
  ic: number;
  rank_ic: number;
  icir: number;
  hit_rate: number;
  significant: boolean;
}

export interface FactorEvaluation {
  symbol: string;
  venue: string;
  environment: string;
  interval: string;
  horizon: number;
  candles: number;
  last_price: number;
  values: Record<string, number | null>;
  scores: FactorScore[];
  signal: number;
}

export interface MarketRow {
  symbol: string;
  price?: number | null;
  signal?: number | null;
  best_factor?: string | null;
  best_ic?: number | null;
  significant_factors?: number | null;
  error?: string | null;
}

export const live = {
  venues: () => request<VenueInfo[]>("/venues"),
  limits: () => request<RiskLimits>("/venues/limits"),
  accounts: (agentId: number) =>
    request<VenueAccount[]>(`/agents/${agentId}/venues`),
  account: (accountId: number) =>
    request<VenueAccount>(`/venue-accounts/${accountId}`),
  link: (
    agentId: number,
    body: {
      venue: string;
      environment: string;
      label?: string;
      wallet_address?: string;
      secret?: string;
    },
    key: string,
  ) => post<VenueAccount>(`/agents/${agentId}/venues`, body, key),
  unlink: (accountId: number, key: string) =>
    request<void>(`/venue-accounts/${accountId}`, { method: "DELETE", key }),
  setActive: (accountId: number, active: boolean, key: string) =>
    post<VenueAccount>(
      `/venue-accounts/${accountId}/active?active=${active}`,
      undefined,
      key,
    ),
  order: (
    accountId: number,
    body: {
      symbol: string;
      side: "buy" | "sell";
      size: number;
      order_type?: "market" | "limit";
      limit_price?: number;
      leverage?: number;
      reduce_only?: boolean;
      confirm_real_money?: boolean;
    },
    key: string,
  ) => post<VenueOrderResult>(`/venue-accounts/${accountId}/orders`, body, key),
  close: (accountId: number, symbol: string, key: string) =>
    post<VenueOrderResult>(
      `/venue-accounts/${accountId}/close/${symbol}`,
      undefined,
      key,
    ),
  orders: (accountId: number) =>
    request<VenueOrderRow[]>(`/venue-accounts/${accountId}/orders`),
};

export const factors = {
  library: () => request<FactorInfo[]>("/factors"),
  market: (symbols: string[], venue = "paper", environment = "paper") =>
    request<MarketRow[]>(
      `/factors/market?symbols=${encodeURIComponent(symbols.join(","))}` +
        `&venue=${venue}&environment=${environment}`,
    ),
  evaluate: (symbol: string, venue = "paper", environment = "paper") =>
    request<FactorEvaluation>(
      `/factors/${encodeURIComponent(symbol)}?venue=${venue}&environment=${environment}`,
    ),
};
