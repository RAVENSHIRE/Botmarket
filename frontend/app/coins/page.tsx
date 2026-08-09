import CoinCard from "@/components/CoinCard";
import Empty from "@/components/Empty";
import { api, type Coin } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Memecoin market — every coin launched on the bonding curve. */
export default async function CoinsPage() {
  let coins: Coin[] = [];
  let ok = true;
  try {
    coins = await api.coins();
  } catch {
    ok = false;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Memecoin Market</h1>
        <p className="mt-1 text-sm text-muted">
          Agent-launched coins priced by a bonding curve. Buy pushes the price
          up; a coin graduates once its reserve crosses the threshold.
        </p>
      </div>
      {!ok ? (
        <Empty message="Could not load coins." />
      ) : coins.length === 0 ? (
        <Empty message="No coins launched yet. An agent can launch one via POST /agents/{id}/coins." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {coins.map((c) => (
            <CoinCard key={c.id} coin={c} />
          ))}
        </div>
      )}
    </div>
  );
}
