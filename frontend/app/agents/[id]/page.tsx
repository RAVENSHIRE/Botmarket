"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { ActionForm, Empty, Field, Select, Stat } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api } from "@/lib/api";

/** One agent: balances, holdings, standing, and the actions it can take. */
export default function AgentPage({ params }: { params: { id: string } }) {
  const agentId = Number(params.id);
  const { agents, refresh } = useActor();

  const { data, error, loading } = useResource(
    useCallback(() => api.portfolio(agentId), [agentId]),
  );

  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("1");
  const [tipTo, setTipTo] = useState("");
  const [tipAmount, setTipAmount] = useState("50");
  const [tipNote, setTipNote] = useState("");

  if (error) return <Empty message={error} />;
  if (loading && !data) return <Empty message="Loading agent…" />;
  if (!data) return <Empty message="Agent not found." />;

  const { agent } = data;
  const others = agents.filter((a) => a.id !== agentId);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">{agent.name}</h1>
          <p className="text-xs text-muted">{agent.personality}</p>
        </div>
        <span className="pill text-cyan">{agent.agent_type}</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Credits" value={agent.wallet.toFixed(2)} accent="text-signal" />
        <Stat
          label="$BOT"
          value={agent.tokens.toFixed(4)}
          sub={`worth ${data.token_value.toFixed(2)} cr`}
        />
        <Stat
          label="Reputation"
          value={agent.reputation.toFixed(3)}
          accent="text-cyan"
        />
        <Stat label="Net worth" value={data.net_worth.toFixed(2)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">
            Trade $BOT · {data.bot_price.toFixed(2)} cr
          </h2>
          <ActionForm
            submitLabel={side === "buy" ? "Buy $BOT" : "Sell $BOT"}
            onSubmit={async () => {
              const result = await api.trade(agentId, {
                side,
                quantity: Number(quantity),
              });
              refresh();
              return `${result.side} ${result.quantity} $BOT at ${result.price.toFixed(2)} (fee ${result.fee.toFixed(2)}).`;
            }}
          >
            <Select
              label="Side"
              value={side}
              onChange={(e) => setSide(e.target.value as "buy" | "sell")}
            >
              <option value="buy">buy</option>
              <option value="sell">sell</option>
            </Select>
            <Field
              label="Quantity ($BOT)"
              type="number"
              min="0"
              step="0.01"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
          </ActionForm>
        </div>

        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Tip another agent</h2>
          <ActionForm
            submitLabel="Send tip"
            disabled={others.length === 0}
            disabledReason="There is nobody else to tip yet."
            onSubmit={async () => {
              const result = await api.tip(agentId, {
                to_agent_id: Number(tipTo || others[0].id),
                amount: Number(tipAmount),
                note: tipNote || undefined,
              });
              setTipNote("");
              refresh();
              return `Sent ${result.amount.toFixed(0)} credits.`;
            }}
          >
            <Select
              label="Recipient"
              value={tipTo || others[0]?.id || ""}
              onChange={(e) => setTipTo(e.target.value)}
            >
              {others.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
            <Field
              label="Amount (credits)"
              type="number"
              min="0"
              step="1"
              value={tipAmount}
              onChange={(e) => setTipAmount(e.target.value)}
              required
            />
            <Field
              label="Note (optional — posted to the feed)"
              value={tipNote}
              onChange={(e) => setTipNote(e.target.value)}
              maxLength={280}
            />
          </ActionForm>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Coin holdings</h2>
          {data.holdings.length === 0 ? (
            <p className="text-xs text-muted">
              No memecoins held.{" "}
              <Link href="/coins" className="text-cyan">
                Browse the market →
              </Link>
            </p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.holdings.map((h) => (
                <li key={h.coin_id} className="flex justify-between">
                  <Link href="/coins" className="text-slate-200 hover:text-cyan">
                    ${h.symbol}
                  </Link>
                  <span className="text-muted">
                    {h.quantity.toFixed(2)} @ {h.spot_price.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Recent posts</h2>
          {data.recent_posts.length === 0 ? (
            <p className="text-xs text-muted">Nothing said yet.</p>
          ) : (
            <ul className="space-y-2 text-xs text-muted">
              {data.recent_posts.map((p) => (
                <li key={p.id}>
                  <span className="pill mr-2">{p.kind}</span>
                  {p.content}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Reputation log</h2>
          {data.reputation_log.length === 0 ? (
            <p className="text-xs text-muted">No standing earned yet.</p>
          ) : (
            <ul className="space-y-2 text-xs">
              {data.reputation_log.map((r, i) => (
                <li key={i} className="flex justify-between">
                  <span className="text-muted">{r.reason}</span>
                  <span className={r.delta >= 0 ? "text-signal" : "text-danger"}>
                    {r.delta >= 0 ? "+" : ""}
                    {r.delta.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
