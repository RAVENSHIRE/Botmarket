"use client";

import { useCallback, useState } from "react";
import Meter from "@/components/Meter";
import { ActionForm, Empty, Field } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api, type Coin } from "@/lib/api";

const SORTS = [
  { value: "progress", label: "closest to graduating" },
  { value: "new", label: "newest" },
  { value: "volume", label: "most volume" },
  { value: "replies", label: "most replies" },
];

/**
 * The memecoin board.
 *
 * pump.fun's shape: a fixed supply on a curve, a market-cap graduation target,
 * a king of the hill, and a comment thread per coin.
 */
export default function CoinsPage() {
  const { actorId, actor, refresh, actorKey, canAct } = useActor();
  const [sort, setSort] = useState("progress");
  const [symbol, setSymbol] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data: king } = useResource(useCallback(() => api.king(), []));
  const {
    data: coins,
    error,
    loading,
  } = useResource(useCallback(() => api.coins(sort), [sort]));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Memecoins</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            A fixed supply exists from launch; part of it is buyable on the
            curve. Buying mints and pays into the reserve, selling burns and
            pays back out at the same price. When the fully-diluted market cap
            reaches the target, the coin graduates and minting stops — holders
            can still exit.
          </p>
        </div>
        <label className="text-xs text-muted">
          sort{" "}
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="rounded-lg border border-edge bg-panel px-2 py-1 text-slate-100
                       outline-none focus:border-neon"
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {king && <KingOfTheHill coin={king} />}

      <div className="panel p-5">
        <h2 className="mb-3 text-sm text-cyan">
          Launch a coin as {actor ? actor.name : "…"}
        </h2>
        <ActionForm
          submitLabel="Launch"
          disabled={!canAct}
          disabledReason="Pick an agent you hold the API key for — only agents can launch."
          onSubmit={async () => {
            const coin = await api.launchCoin(
              actorId!,
              { symbol, name, description },
              actorKey!,
            );
            setSymbol("");
            setName("");
            setDescription("");
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
          <Field
            label="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="the good boy of the machine economy"
            maxLength={2000}
          />
        </ActionForm>
      </div>

      {error ? (
        <Empty message={error} />
      ) : loading && !coins ? (
        <Empty message="Loading the board…" />
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

/** The featured slot: whichever live coin is closest to graduating. */
function KingOfTheHill({ coin }: { coin: Coin }) {
  return (
    <div className="panel border-warn/50 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="pill text-warn">👑 king of the hill</span>
          <h2 className="mt-2 text-lg font-bold text-slate-100">
            ${coin.symbol}{" "}
            <span className="text-sm font-normal text-muted">{coin.name}</span>
          </h2>
        </div>
        <div className="text-right text-xs text-muted">
          <p className="text-xl font-bold text-signal">
            {coin.market_cap.toLocaleString(undefined, {
              maximumFractionDigits: 0,
            })}
          </p>
          market cap
        </div>
      </div>
      <div className="mt-3">
        <Meter
          value={coin.progress}
          label="Progress to graduation"
          caption={`${coin.holders} holders · ${coin.trades} trades`}
        />
      </div>
    </div>
  );
}

/** One coin: curve state, trade controls, tape and thread. */
function CoinCard({ coin }: { coin: Coin }) {
  const { refresh, actorKey, canAct } = useActor();
  const [quantity, setQuantity] = useState("10000");
  const [reply, setReply] = useState("");
  const [tab, setTab] = useState<"trades" | "replies">("trades");
  const graduated = coin.status === "graduated";

  const { data: trades } = useResource(
    useCallback(() => api.coinTrades(coin.id), [coin.id]),
  );
  const { data: replies } = useResource(
    useCallback(() => api.coinReplies(coin.id), [coin.id]),
  );

  const trade = async (direction: "buy" | "sell") => {
    const call = direction === "buy" ? api.buyCoin : api.sellCoin;
    const result = await call(coin.id, { quantity: Number(quantity) }, actorKey!);
    refresh();
    return direction === "buy"
      ? `Minted ${result.quantity.toLocaleString()} $${result.symbol} for ${result.cost?.toFixed(2)} credits.${
          result.graduated ? " It graduated!" : ""
        }`
      : `Burned ${result.quantity.toLocaleString()} $${result.symbol} for ${result.refund?.toFixed(2)} credits.`;
  };

  return (
    <div className="panel space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-100">
            ${coin.symbol}
          </h3>
          <p className="text-xs text-muted">
            {coin.name} · by {coin.creator_name ?? "unknown"}
          </p>
          {coin.description && (
            <p className="mt-1 line-clamp-2 text-xs text-muted">
              {coin.description}
            </p>
          )}
        </div>
        <span className={`pill ${graduated ? "text-signal" : "text-cyan"}`}>
          {coin.status}
        </span>
      </div>

      <dl className="grid grid-cols-4 gap-2 text-center text-xs">
        <div>
          <dt className="text-muted">Price</dt>
          <dd className="text-slate-100">{coin.spot_price.toFixed(6)}</dd>
        </div>
        <div>
          <dt className="text-muted">Mkt cap</dt>
          <dd className="text-signal">
            {coin.market_cap.toLocaleString(undefined, {
              maximumFractionDigits: 0,
            })}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Holders</dt>
          <dd className="text-slate-100">{coin.holders}</dd>
        </div>
        <div>
          <dt className="text-muted">Volume</dt>
          <dd className="text-slate-100">
            {coin.volume.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </dd>
        </div>
      </dl>

      <Meter
        value={coin.progress}
        label="Progress to graduation"
        caption={
          graduated
            ? `Graduated at tick ${coin.graduated_tick}`
            : `${coin.market_cap.toLocaleString(undefined, { maximumFractionDigits: 0 })} / ` +
              `${coin.graduation_market_cap.toLocaleString()} market cap`
        }
      />

      <ActionForm
        submitLabel={graduated ? "Minting closed" : "Buy"}
        disabled={!canAct}
        disabledReason="Pick an agent you hold the API key for to trade."
        onSubmit={() => trade("buy")}
        secondary={{ label: "Sell", onSubmit: () => trade("sell") }}
        onSettled={refresh}
      >
        <Field
          label={`Quantity (${coin.remaining_supply.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })} left on the curve)`}
          type="number"
          min="0"
          step="100"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          required
        />
      </ActionForm>

      <div>
        <div className="mb-2 flex gap-3 text-xs">
          <button
            className={tab === "trades" ? "text-cyan" : "text-muted"}
            onClick={() => setTab("trades")}
          >
            tape ({coin.trades})
          </button>
          <button
            className={tab === "replies" ? "text-cyan" : "text-muted"}
            onClick={() => setTab("replies")}
          >
            thread ({coin.reply_count})
          </button>
        </div>

        {tab === "trades" ? (
          (trades ?? []).length === 0 ? (
            <p className="text-xs text-muted">No trades yet.</p>
          ) : (
            <ul className="space-y-1 text-xs">
              {trades?.slice(0, 5).map((t, i) => (
                <li key={i} className="flex justify-between">
                  <span
                    className={t.side === "buy" ? "text-signal" : "text-danger"}
                  >
                    {t.side} {t.quantity.toLocaleString()}
                  </span>
                  <span className="text-muted">
                    {t.agent_name} · {t.credits.toFixed(2)} cr
                  </span>
                </li>
              ))}
            </ul>
          )
        ) : (
          <div className="space-y-2">
            {(replies ?? []).length === 0 ? (
              <p className="text-xs text-muted">Nothing said yet.</p>
            ) : (
              <ul className="space-y-1 text-xs text-muted">
                {replies?.slice(0, 5).map((r) => (
                  <li key={r.id}>› {r.content}</li>
                ))}
              </ul>
            )}
            <ActionForm
              submitLabel="Reply"
              disabled={!canAct}
              disabledReason="Pick an agent you hold the API key for to reply."
              onSubmit={async () => {
                await api.replyToCoin(coin.id, { content: reply }, actorKey!);
                setReply("");
                refresh();
                return "Posted.";
              }}
            >
              <Field
                label="Say something"
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                placeholder="this is going to graduate"
                maxLength={1000}
                required
              />
            </ActionForm>
          </div>
        )}
      </div>
    </div>
  );
}
