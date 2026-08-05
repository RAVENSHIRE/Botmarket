"use client";

import { useCallback, useState } from "react";
import Sparkline from "@/components/Sparkline";
import { Empty, Stat } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api, ApiError, type TickResult } from "@/lib/api";

/** Live simulation dashboard — advance ticks and watch the world react. */
export default function SimulationPage() {
  const { refresh } = useActor();
  const { data: state, error } = useResource(useCallback(() => api.state(), []));
  const [log, setLog] = useState<TickResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [tickError, setTickError] = useState<string | null>(null);

  const runTick = async () => {
    setBusy(true);
    setTickError(null);
    try {
      const result = await api.tick();
      setLog((prev) => [result, ...prev].slice(0, 6));
      refresh();
    } catch (err) {
      setTickError(
        err instanceof ApiError ? err.message : "Tick failed. Is the API up?",
      );
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <Empty
        message={error}
        hint="Check that NEXT_PUBLIC_API_URL points at a running backend."
      />
    );
  }

  const history = state?.price_history ?? [];
  const rising = (state?.market_trend ?? 0) >= 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Simulation Control</h1>
        <button
          className="btn disabled:opacity-50"
          onClick={runTick}
          disabled={busy}
        >
          {busy ? "Ticking…" : "▶ Run Tick"}
        </button>
      </div>

      {tickError && (
        <div className="panel border-danger/40 p-4 text-sm text-danger">
          {tickError}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Tick" value={state?.tick ?? "—"} />
        <Stat
          label="$BOT"
          value={state ? state.market_price.toFixed(2) : "—"}
        />
        <Stat
          label="Trend"
          value={
            state
              ? `${state.market_trend >= 0 ? "+" : ""}${state.market_trend.toFixed(2)}`
              : "—"
          }
          accent={rising ? "text-signal" : "text-danger"}
          sub={rising ? "rising" : "falling"}
        />
        <Stat label="Agents" value={state?.agents ?? "—"} />
      </div>

      <div className="panel p-5">
        <h2 className="mb-2 text-sm text-cyan">$BOT price</h2>
        <Sparkline
          values={history}
          rising={rising}
          startTick={Math.max(1, (state?.tick ?? 0) - history.length + 1)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Top Agents</h2>
          <ul className="space-y-2 text-sm">
            {(state?.leaderboard ?? []).length === 0 ? (
              <li className="text-muted">No agents registered yet.</li>
            ) : (
              state?.leaderboard.map((r, i) => (
                <li key={r.id} className="flex justify-between">
                  <span className="text-muted">
                    {i + 1}. {r.name}
                  </span>
                  <span className="text-signal">{r.net_worth.toFixed(0)}</span>
                </li>
              ))
            )}
          </ul>
        </div>

        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">World Events</h2>
          <ul className="space-y-2 text-xs text-muted">
            {(state?.recent_events ?? []).length === 0 ? (
              <li>Nothing has happened yet.</li>
            ) : (
              state?.recent_events.map((e, i) => (
                <li key={i}>
                  <span className="pill mr-2">{e.kind}</span>
                  {e.description}
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      <div className="panel p-5">
        <h2 className="mb-3 text-sm text-cyan">Tick Log</h2>
        {log.length === 0 ? (
          <p className="text-xs text-muted">No ticks run this session.</p>
        ) : (
          <ul className="space-y-3 text-xs">
            {log.map((t) => (
              <li key={t.tick} className="border-l-2 border-edge pl-3">
                <p className="text-slate-200">
                  tick #{t.tick} · $BOT {t.market_price.toFixed(2)} · pressure{" "}
                  <span
                    className={t.pressure >= 0 ? "text-signal" : "text-danger"}
                  >
                    {t.pressure >= 0 ? "+" : ""}
                    {t.pressure.toFixed(2)}
                  </span>{" "}
                  · {t.posts_created} posts
                </p>
                {t.event && (
                  <p className="mt-1 text-muted">↳ {t.event.description}</p>
                )}
                {t.proposals_resolved.map((p) => (
                  <p key={p.id} className="mt-1 text-muted">
                    ↳ proposal #{p.id} {p.status}: {p.title}
                  </p>
                ))}
                <p className="mt-1 text-muted">
                  {t.actions
                    .filter((a) => a.action !== "hold")
                    .map(
                      (a) =>
                        `${a.agent} ${a.action}${
                          a.quantity ? ` ${a.quantity.toFixed(2)}` : ""
                        }`,
                    )
                    .join(" · ") || "all agents held"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
