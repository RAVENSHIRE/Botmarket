"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

interface State {
  tick: number;
  market_price: number;
  market_trend: number;
  agents: number;
  leaderboard: { name: string; score: number }[];
}

/** Live simulation dashboard — advance ticks and watch the world react. */
export default function SimulationPage() {
  const [state, setState] = useState<State | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setState((await api.state()) as unknown as State);
      setError(null);
    } catch {
      setError("Backend unreachable. Start the API and reload.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runTick = async () => {
    setBusy(true);
    try {
      const result = await api.tick();
      setLog((prev) =>
        [
          `tick #${result.tick} · price ${result.market_price} · ${result.posts_created} posts`,
          ...prev,
        ].slice(0, 8),
      );
      await refresh();
    } catch {
      setError("Tick failed. Is the backend running?");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Simulation Control</h1>
        <button className="btn disabled:opacity-50" onClick={runTick} disabled={busy}>
          {busy ? "Ticking…" : "▶ Run Tick"}
        </button>
      </div>

      {error && <div className="panel border-danger/40 p-4 text-sm text-danger">{error}</div>}

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Tick" value={state?.tick ?? "—"} />
        <Stat label="Market" value={state ? state.market_price.toFixed(2) : "—"} />
        <Stat
          label="Trend"
          value={state ? `${state.market_trend >= 0 ? "+" : ""}${state.market_trend}` : "—"}
          accent={state && state.market_trend >= 0 ? "text-signal" : "text-danger"}
        />
        <Stat label="Agents" value={state?.agents ?? "—"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Top Agents</h2>
          <ul className="space-y-2 text-sm">
            {(state?.leaderboard ?? []).map((r, i) => (
              <li key={r.name} className="flex justify-between">
                <span className="text-muted">
                  {i + 1}. {r.name}
                </span>
                <span className="text-signal">{r.score.toFixed(0)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Tick Log</h2>
          <ul className="space-y-1 text-xs text-muted">
            {log.length === 0 ? (
              <li>No ticks run this session.</li>
            ) : (
              log.map((line, i) => <li key={i}>› {line}</li>)
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = "text-slate-100",
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="panel p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
    </div>
  );
}
