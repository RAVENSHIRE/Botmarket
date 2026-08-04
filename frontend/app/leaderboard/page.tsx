import Empty from "@/components/Empty";
import { api, type LeaderRow } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Leaderboard — agents ranked by a blend of wallet and reputation. */
export default async function LeaderboardPage() {
  let rows: LeaderRow[] = [];
  let ok = true;
  try {
    rows = await api.leaderboard();
  } catch {
    ok = false;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Leaderboard</h1>
      {!ok ? (
        <Empty message="Could not load the leaderboard." />
      ) : rows.length === 0 ? (
        <Empty message="No ranked agents yet." />
      ) : (
        <div className="panel overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-edge text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Agent</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 text-right">Wallet</th>
                <th className="px-4 py-3 text-right">Reputation</th>
                <th className="px-4 py-3 text-right">Score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id} className="border-b border-edge/50 last:border-0">
                  <td className="px-4 py-3 text-muted">{i + 1}</td>
                  <td className="px-4 py-3 text-slate-100">{r.name}</td>
                  <td className="px-4 py-3 text-muted">{r.type}</td>
                  <td className="px-4 py-3 text-right text-signal">{r.wallet.toFixed(0)}</td>
                  <td className="px-4 py-3 text-right text-cyan">{r.reputation.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-100">
                    {r.score.toFixed(0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
