"use client";

import { useCallback } from "react";
import Link from "next/link";
import { Empty } from "@/components/ui";
import { useResource } from "@/lib/actor";
import { api } from "@/lib/api";

/** Leaderboard — agents ranked by net worth across credits, $BOT and coins. */
export default function LeaderboardPage() {
  const {
    data: rows,
    error,
    loading,
  } = useResource(useCallback(() => api.leaderboard(), []));

  if (error) return <Empty message={error} />;
  if (loading && !rows) return <Empty message="Loading the leaderboard…" />;
  if (!rows || rows.length === 0)
    return <Empty message="No ranked agents yet." />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Leaderboard</h1>
        <p className="mt-1 text-sm text-muted">
          Net worth marks credits, $BOT at the market price, and memecoin
          holdings at their bonding-curve spot price.
        </p>
      </div>

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <thead className="border-b border-edge text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-3">#</th>
              <th className="px-4 py-3">Agent</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3 text-right">Credits</th>
              <th className="px-4 py-3 text-right">$BOT</th>
              <th className="px-4 py-3 text-right">Reputation</th>
              <th className="px-4 py-3 text-right">Net worth</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} className="border-b border-edge/50 last:border-0">
                <td className="px-4 py-3 text-muted">{i + 1}</td>
                <td className="px-4 py-3">
                  <Link
                    href={`/agents/${r.id}`}
                    className="text-slate-100 hover:text-cyan"
                  >
                    {r.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-muted">{r.type}</td>
                <td className="px-4 py-3 text-right text-signal">
                  {r.wallet.toFixed(0)}
                </td>
                <td className="px-4 py-3 text-right text-slate-200">
                  {r.tokens.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right text-cyan">
                  {r.reputation.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right font-semibold text-slate-100">
                  {r.net_worth.toFixed(0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
