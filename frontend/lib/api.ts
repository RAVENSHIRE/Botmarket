/**
 * Typed client for the BOTMARKET backend API.
 *
 * All calls are relative to NEXT_PUBLIC_API_URL. Server components fetch with
 * `cache: "no-store"` so the dashboard always reflects live simulation state.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Agent {
  id: number;
  name: string;
  agent_type: string;
  personality: string;
  strategy: string;
  wallet: number;
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

export interface LeaderRow {
  id: number;
  name: string;
  type: string;
  wallet: number;
  reputation: number;
  score: number;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export interface Coin {
  id: number;
  name: string;
  symbol: string;
  creator_id: number;
  creator_name: string | null;
  supply: number;
  reserve: number;
  base_price: number;
  slope: number;
  spot_price: number;
  market_cap: number;
  status: string;
  tick: number;
}

export const api = {
  agents: () => get<Agent[]>("/agents"),
  agent: (id: number) => get<Agent>(`/agents/${id}`),
  feed: () => get<Post[]>("/feed"),
  coins: () => get<Coin[]>("/coins"),
  coin: (id: number) => get<Coin>(`/coins/${id}`),
  leaderboard: () => get<LeaderRow[]>("/leaderboard"),
  state: () => get<Record<string, unknown>>("/simulation/state"),
  tick: async () => {
    const res = await fetch(`${API_URL}/simulation/tick`, { method: "POST" });
    if (!res.ok) throw new Error(`tick failed: ${res.status}`);
    return res.json();
  },
};
