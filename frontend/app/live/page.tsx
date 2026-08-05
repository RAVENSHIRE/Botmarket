"use client";

import { useCallback, useState } from "react";
import { ActionForm, Empty, Field, Select, Stat } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import {
  factors as factorsApi,
  live,
  type MarketRow,
  type VenueAccount,
} from "@/lib/api";

const WATCHLIST = ["BTC", "ETH", "SOL"];

/**
 * The live trading desk.
 *
 * Real money is treated as a distinct mode throughout, not a setting: a mainnet
 * account is badged everywhere it appears, and its order form makes you tick a
 * confirmation the backend independently requires.
 */
export default function LivePage() {
  const { actorId, actor } = useActor();

  const { data: venues } = useResource(useCallback(() => live.venues(), []));
  const { data: limits } = useResource(useCallback(() => live.limits(), []));
  const { data: signals } = useResource(
    useCallback(() => factorsApi.market(WATCHLIST), []),
  );
  const { data: accounts, error } = useResource(
    useCallback(
      () => (actorId ? live.accounts(actorId) : Promise.resolve([])),
      [actorId],
    ),
  );

  if (!actorId) {
    return (
      <Empty
        message="Pick an acting agent in the header."
        hint="Venue accounts belong to an agent, so the desk needs to know who is trading."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Live Desk</h1>
        <p className="mt-1 text-sm text-muted">
          The same agents, trading real perpetuals. Paper is the default and
          needs no credentials; Hyperliquid testnet and mainnet need a wallet.
          Every order passes the risk checks below before it is sent.
        </p>
      </div>

      {limits && <RiskBanner limits={limits} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">
            Link a venue for {actor?.name ?? "…"}
          </h2>
          <LinkForm agentId={actorId} venues={venues ?? []} />
        </div>

        <div className="panel p-5">
          <h2 className="mb-3 text-sm text-cyan">Factor signals</h2>
          <SignalTable rows={signals ?? []} />
        </div>
      </div>

      {error ? (
        <Empty message={error} />
      ) : (accounts ?? []).length === 0 ? (
        <Empty message="No venue accounts yet. Link a paper account above to start." />
      ) : (
        <div className="space-y-4">
          {accounts?.map((account) => (
            <AccountPanel key={account.id} account={account} />
          ))}
        </div>
      )}
    </div>
  );
}

/** The risk envelope, shown before anything can be traded. */
function RiskBanner({ limits }: { limits: NonNullable<Awaited<ReturnType<typeof live.limits>>> }) {
  return (
    <div
      className={`panel p-4 ${
        limits.trading_enabled ? "border-edge" : "border-danger/50"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`pill ${limits.trading_enabled ? "text-signal" : "text-danger"}`}>
            {limits.trading_enabled ? "trading enabled" : "KILL SWITCH ON"}
          </span>
          <span className={`pill ${limits.allow_mainnet ? "text-warn" : "text-muted"}`}>
            {limits.allow_mainnet ? "mainnet allowed" : "mainnet disabled"}
          </span>
        </div>
        <dl className="flex flex-wrap gap-4 text-xs text-muted">
          <span>max leverage {limits.max_leverage}×</span>
          <span>order ≤ {limits.max_order_value.toLocaleString()}</span>
          <span>position ≤ {limits.max_position_value.toLocaleString()}</span>
          <span>daily loss ≤ {limits.max_daily_loss.toLocaleString()}</span>
        </dl>
      </div>
    </div>
  );
}

/** Form for linking an agent to a venue. */
function LinkForm({
  agentId,
  venues,
}: {
  agentId: number;
  venues: Awaited<ReturnType<typeof live.venues>>;
}) {
  const { refresh } = useActor();
  const [venue, setVenue] = useState("paper");
  const [environment, setEnvironment] = useState("paper");
  const [address, setAddress] = useState("");
  const [secret, setSecret] = useState("");

  const selected = venues.find((v) => v.name === venue);
  const isLive = venue !== "paper";
  const isMainnet = environment === "mainnet";

  return (
    <ActionForm
      submitLabel={isMainnet ? "Link REAL-MONEY account" : "Link account"}
      onSubmit={async () => {
        const account = await live.link(agentId, {
          venue,
          environment,
          wallet_address: address || undefined,
          secret: secret || undefined,
        });
        setSecret("");
        setAddress("");
        refresh();
        return `Linked ${account.venue}/${account.environment}.`;
      }}
    >
      <Select
        label="Venue"
        value={venue}
        onChange={(e) => {
          setVenue(e.target.value);
          setEnvironment(e.target.value === "paper" ? "paper" : "testnet");
        }}
      >
        {venues.map((v) => (
          <option key={v.name} value={v.name}>
            {v.name}
            {v.requires_credentials ? " (needs credentials)" : ""}
          </option>
        ))}
      </Select>

      <Select
        label="Environment"
        value={environment}
        onChange={(e) => setEnvironment(e.target.value)}
      >
        {(selected?.environments ?? ["paper"]).map((env) => (
          <option key={env} value={env}>
            {env}
          </option>
        ))}
      </Select>

      {isLive && (
        <>
          <Field
            label="Wallet address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="0x…"
            required
          />
          <Field
            label="Private key (encrypted at rest, never shown again)"
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="leave blank to link read-only"
          />
        </>
      )}

      {isMainnet && (
        <p className="text-xs text-danger">
          Mainnet moves real funds. Orders will also require a per-order
          confirmation, and the backend refuses them without it.
        </p>
      )}
    </ActionForm>
  );
}

/** Per-symbol blended factor signal. */
function SignalTable({ rows }: { rows: MarketRow[] }) {
  if (rows.length === 0) {
    return <p className="text-xs text-muted">Loading signals…</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="border-b border-edge text-left text-xs text-muted">
        <tr>
          <th className="py-2">Symbol</th>
          <th className="py-2 text-right">Price</th>
          <th className="py-2 text-right">Signal</th>
          <th className="py-2 text-right">Best factor</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.symbol} className="border-b border-edge/50 last:border-0">
            <td className="py-2 text-slate-100">{row.symbol}</td>
            <td className="py-2 text-right text-muted">
              {row.price ? row.price.toFixed(2) : "—"}
            </td>
            <td
              className={`py-2 text-right ${
                (row.signal ?? 0) > 0
                  ? "text-signal"
                  : (row.signal ?? 0) < 0
                    ? "text-danger"
                    : "text-muted"
              }`}
            >
              {row.error ? "—" : (row.signal ?? 0).toFixed(3)}
            </td>
            <td className="py-2 text-right text-xs text-muted">
              {row.error ? row.error.slice(0, 28) : (row.best_factor ?? "none")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** One venue account: balances, positions and the order ticket. */
function AccountPanel({ account }: { account: VenueAccount }) {
  const { refresh } = useActor();
  const [symbol, setSymbol] = useState("BTC");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [size, setSize] = useState("0.01");
  const [leverage, setLeverage] = useState("1");
  const [confirm, setConfirm] = useState(false);

  const { data: detail } = useResource(
    useCallback(() => live.account(account.id), [account.id]),
  );
  const { data: history } = useResource(
    useCallback(() => live.orders(account.id), [account.id]),
  );

  const positions = detail?.positions ?? [];

  return (
    <div
      className={`panel space-y-4 p-5 ${
        account.is_real_money ? "border-danger/50" : ""
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-100">
            {account.venue}
            <span className="ml-2 text-xs text-muted">{account.label}</span>
          </h3>
          {account.wallet_address && (
            <p className="text-xs text-muted">{account.wallet_address}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`pill ${
              account.is_real_money ? "text-danger" : "text-cyan"
            }`}
          >
            {account.is_real_money ? "REAL MONEY" : account.environment}
          </span>
          <span className={`pill ${account.active ? "text-signal" : "text-warn"}`}>
            {account.active ? "active" : "paused"}
          </span>
          <button
            className="pill hover:text-cyan"
            onClick={async () => {
              await live.setActive(account.id, !account.active);
              refresh();
            }}
          >
            {account.active ? "pause" : "resume"}
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Equity" value={detail?.equity?.toFixed(2) ?? "—"} accent="text-signal" />
        <Stat label="Available" value={detail?.available?.toFixed(2) ?? "—"} />
        <Stat label="Exposure" value={detail?.gross_notional?.toFixed(2) ?? "—"} />
        <Stat
          label="Loss today"
          value={account.realised_loss_today.toFixed(2)}
          accent={account.realised_loss_today > 0 ? "text-danger" : "text-slate-100"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h4 className="mb-2 text-xs text-cyan">Order ticket</h4>
          <ActionForm
            submitLabel={account.is_real_money ? "Send REAL order" : "Send order"}
            disabled={!account.active}
            disabledReason="This account is paused."
            // A refused order still writes an audit row, so refresh either way.
            onSettled={refresh}
            onSubmit={async () => {
              const result = await live.order(account.id, {
                symbol,
                side,
                size: Number(size),
                leverage: Number(leverage),
                confirm_real_money: confirm,
              });
              refresh();
              return result.accepted
                ? `${result.side} ${result.filled_size} ${result.symbol} @ ${result.average_price.toFixed(2)}`
                : `Rejected: ${result.reason}`;
            }}
            secondary={{
              label: "Close position",
              onSubmit: async () => {
                const result = await live.close(account.id, symbol);
                refresh();
                return result.accepted
                  ? `Closed ${result.symbol}.`
                  : `Nothing to close: ${result.reason}`;
              },
            }}
          >
            <Field
              label="Symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              required
            />
            <Select
              label="Side"
              value={side}
              onChange={(e) => setSide(e.target.value as "buy" | "sell")}
            >
              <option value="buy">buy</option>
              <option value="sell">sell</option>
            </Select>
            <Field
              label="Size"
              type="number"
              min="0"
              step="0.0001"
              value={size}
              onChange={(e) => setSize(e.target.value)}
              required
            />
            <Field
              label="Leverage"
              type="number"
              min="1"
              step="1"
              value={leverage}
              onChange={(e) => setLeverage(e.target.value)}
              required
            />
            {account.is_real_money && (
              <label className="flex items-center gap-2 text-xs text-danger">
                <input
                  type="checkbox"
                  checked={confirm}
                  onChange={(e) => setConfirm(e.target.checked)}
                />
                I understand this spends real money
              </label>
            )}
          </ActionForm>
        </div>

        <div className="space-y-4">
          <div>
            <h4 className="mb-2 text-xs text-cyan">Positions</h4>
            {positions.length === 0 ? (
              <p className="text-xs text-muted">Flat.</p>
            ) : (
              <ul className="space-y-1 text-xs">
                {positions.map((p) => (
                  <li key={p.symbol} className="flex justify-between">
                    <span className="text-slate-200">
                      {p.side} {p.size} {p.symbol} @ {p.entry_price.toFixed(2)}
                    </span>
                    <span
                      className={
                        p.unrealised_pnl >= 0 ? "text-signal" : "text-danger"
                      }
                    >
                      {p.unrealised_pnl >= 0 ? "+" : ""}
                      {p.unrealised_pnl.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h4 className="mb-2 text-xs text-cyan">Order log</h4>
            {(history ?? []).length === 0 ? (
              <p className="text-xs text-muted">No orders yet.</p>
            ) : (
              <ul className="space-y-1 text-xs text-muted">
                {history?.slice(0, 6).map((row) => (
                  <li key={row.id} className="flex justify-between gap-2">
                    <span>
                      <span
                        className={
                          row.status === "filled"
                            ? "text-signal"
                            : row.status === "refused"
                              ? "text-warn"
                              : "text-danger"
                        }
                      >
                        {row.status}
                      </span>{" "}
                      {row.side} {row.size} {row.symbol}
                    </span>
                    {row.reason && (
                      <span className="truncate text-right">{row.reason}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
