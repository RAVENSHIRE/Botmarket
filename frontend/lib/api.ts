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
  init?: Omit<RequestInit, "body"> & { body?: unknown },
): Promise<T> {
  const { body, ...rest } = init ?? {};
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
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

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body });

// --- Types ---------------------------------------------------------------

export type AgentType = "trader" | "meme" | "analyst";

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
  creator_id: number;
  creator_name: string | null;
  supply: number;
  reserve: number;
  spot_price: number;
  market_cap: number;
  status: "live" | "graduated";
  graduation_reserve: number;
  progress: number;
  holders: number;
  created_tick: number;
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
  spot_price: number;
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
    post<Agent>("/agents", body),

  feed: (kind?: string) =>
    request<Post[]>(`/feed${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`),
  createPost: (id: number, body: { content: string; kind: string }) =>
    post<Post>(`/agents/${id}/posts`, body),

  market: () => request<Market>("/market"),
  leaderboard: () => request<LeaderRow[]>("/leaderboard"),

  trade: (id: number, body: { side: "buy" | "sell"; quantity: number }) =>
    post<TradeResult>(`/agents/${id}/trade`, body),
  tip: (
    id: number,
    body: { to_agent_id: number; amount: number; note?: string },
  ) => post<{ amount: number; wallet: number }>(`/agents/${id}/tip`, body),

  coins: () => request<Coin[]>("/coins"),
  coin: (id: number) => request<Coin>(`/coins/${id}`),
  launchCoin: (id: number, body: { symbol: string; name: string }) =>
    post<Coin>(`/agents/${id}/coins`, body),
  buyCoin: (coinId: number, body: { agent_id: number; quantity: number }) =>
    post<CoinTradeResult>(`/coins/${coinId}/buy`, body),
  sellCoin: (coinId: number, body: { agent_id: number; quantity: number }) =>
    post<CoinTradeResult>(`/coins/${coinId}/sell`, body),

  proposals: () => request<Proposal[]>("/proposals"),
  createProposal: (
    id: number,
    body: {
      title: string;
      body: string;
      effect: Proposal["effect"];
      magnitude: number;
    },
  ) => post<Proposal>(`/agents/${id}/proposals`, body),
  vote: (proposalId: number, body: { agent_id: number; support: boolean }) =>
    post<{ weight_for: number; weight_against: number }>(
      `/proposals/${proposalId}/votes`,
      body,
    ),

  state: () => request<SimulationState>("/simulation/state"),
  tick: () => post<TickResult>("/simulation/tick"),
};
