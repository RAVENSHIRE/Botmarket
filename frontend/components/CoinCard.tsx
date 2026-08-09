import type { Coin } from "@/lib/api";

/** Card summarising a single memecoin's market state. */
export default function CoinCard({ coin }: { coin: Coin }) {
  const graduated = coin.status === "graduated";
  return (
    <div className="panel p-5 transition hover:shadow-glow">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-100">{coin.name}</h3>
          <p className="text-xs text-muted">${coin.symbol}</p>
        </div>
        <span
          className={`pill ${
            graduated ? "border-signal/50 text-signal" : "border-edge text-muted"
          }`}
        >
          {graduated ? "graduated" : "bonding"}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="text-muted">Price</dt>
          <dd className="text-cyan">{coin.spot_price.toFixed(3)}</dd>
        </div>
        <div>
          <dt className="text-muted">Market cap</dt>
          <dd className="text-signal">{coin.market_cap.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="text-muted">Supply</dt>
          <dd className="text-slate-200">{coin.supply.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="text-muted">Reserve</dt>
          <dd className="text-slate-200">{coin.reserve.toFixed(0)}</dd>
        </div>
      </dl>

      <p className="mt-4 text-xs text-muted">
        by {coin.creator_name ?? `agent #${coin.creator_id}`}
      </p>
    </div>
  );
}
