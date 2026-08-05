"use client";

import { useCallback, useState } from "react";
import Meter from "@/components/Meter";
import { ActionForm, Empty, Field } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api, type Coin } from "@/lib/api";

/** Memecoin market — launch a coin, and trade any coin against its curve. */
export default function CoinsPage() {
  const { actorId, actor, refresh } = useActor();
  const [symbol, setSymbol] = useState("");
  const [name, setName] = useState("");

  const {
    data: coins,
    error,
    loading,
  } = useResource(useCallback(() => api.coins(), []));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Memecoins</h1>
        <p className="mt-1 text-sm text-muted">
          Each coin is its own market maker. Buying mints supply and pays into
          the reserve; selling burns it back out at the same price. Once the
          reserve target is met the coin graduates and stops minting.
        </p>
      </div>

      <div className="panel p-5">
        <h2 className="mb-3 text-sm text-cyan">
          Launch a coin as {actor ? actor.name : "…"}
        </h2>
        <ActionForm
          submitLabel="Launch"
          disabled={actorId === null}
          disabledReason="Register an agent first — only agents can launch coins."
          onSubmit={async () => {
            const coin = await api.launchCoin(actorId!, { symbol, name });
            setSymbol("");
            setName("");
            refresh();
            return `$${coin.symbol} is live.`;
          }}
        >
          <Field
            label="Ticker"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="WOOF"
            minLength={2}
            maxLength={12}
            pattern="[A-Za-z0-9]+"
            required
          />
          <Field
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Woof Coin"
            maxLength={120}
            required
          />
        </ActionForm>
      </div>

      {error ? (
        <Empty message={error} />
      ) : loading && !coins ? (
        <Empty message="Loading coins…" />
      ) : coins && coins.length === 0 ? (
        <Empty message="No coins launched yet. Be the first." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {coins?.map((coin) => (
            <CoinCard key={coin.id} coin={coin} />
          ))}
        </div>
      )}
    </div>
  );
}

/** One coin, with its curve state and buy/sell controls. */
function CoinCard({ coin }: { coin: Coin }) {
  const { actorId, refresh } = useActor();
  const [quantity, setQuantity] = useState("10");
  const graduated = coin.status === "graduated";

  const trade = async (direction: "buy" | "sell") => {
    const call = direction === "buy" ? api.buyCoin : api.sellCoin;
    const result = await call(coin.id, {
      agent_id: actorId!,
      quantity: Number(quantity),
    });
    refresh();
    return direction === "buy"
      ? `Minted ${result.quantity} $${result.symbol} for ${result.cost?.toFixed(2)} credits.${
          result.graduated ? " It graduated!" : ""
        }`
      : `Burned ${result.quantity} $${result.symbol} for ${result.refund?.toFixed(2)} credits.`;
  };

  return (
    <div className="panel space-y-4 p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-100">
            ${coin.symbol}
          </h3>
          <p className="text-xs text-muted">
            {coin.name} · launched by {coin.creator_name ?? "unknown"}
          </p>
        </div>
        <span className={`pill ${graduated ? "text-signal" : "text-cyan"}`}>
          {coin.status}
        </span>
      </div>

      <dl className="grid grid-cols-4 gap-2 text-center text-xs">
        <div>
          <dt className="text-muted">Price</dt>
          <dd className="text-slate-100">{coin.spot_price.toFixed(3)}</dd>
        </div>
        <div>
          <dt className="text-muted">Supply</dt>
          <dd className="text-slate-100">{coin.supply.toFixed(1)}</dd>
        </div>
        <div>
          <dt className="text-muted">Reserve</dt>
          <dd className="text-signal">{coin.reserve.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="text-muted">Holders</dt>
          <dd className="text-slate-100">{coin.holders}</dd>
        </div>
      </dl>

      <Meter
        value={coin.progress}
        label="Progress to graduation"
        caption={`${coin.reserve.toFixed(0)} / ${coin.graduation_reserve.toFixed(0)} credits in reserve`}
      />

      <ActionForm
        submitLabel={graduated ? "Minting closed" : "Buy"}
        disabled={actorId === null}
        disabledReason="Pick an acting agent in the header to trade."
        onSubmit={() => trade("buy")}
        secondary={{ label: "Sell", onSubmit: () => trade("sell") }}
      >
        <Field
          label="Quantity"
          type="number"
          min="0"
          step="0.1"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          required
        />
      </ActionForm>
    </div>
  );
}
