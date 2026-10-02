"use client";

import Link from "next/link";
import { useCallback } from "react";
import Sparkline from "@/components/Sparkline";
import { useActor, useResource } from "@/lib/actor";
import { api } from "@/lib/api";

const number = (value: number | null | undefined, digits = 0) =>
  value == null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: digits });

/** A read-only overview of the actual simulation, with explicit unavailable states. */
export default function Home() {
  const { agents, actor, canAct, offline, refresh } = useActor();
  const { data: world, error: worldError, loading } = useResource(useCallback(() => api.state(), []));
  const { data: king, loading: kingLoading, error: kingError } = useResource(useCallback(() => api.king(), []));
  const { data: posts, loading: postsLoading, error: postsError } = useResource(useCallback(() => api.feed(), []));
  const { data: proposals, loading: proposalsLoading, error: proposalsError } = useResource(useCallback(() => api.proposals(), []));
  const history = world?.price_history ?? [];
  const rising = world ? world.market_trend >= 0 : null;
  const openProposals = proposals?.filter((proposal) => proposal.status === "open").length;

  return (
    <div className="space-y-8 pb-12">
      <section className="relative overflow-hidden rounded-[2rem] border border-edge bg-panelHi px-6 py-8 sm:px-10 sm:py-10">
        <div className="pointer-events-none absolute -right-24 -top-32 h-80 w-80 rounded-full bg-neon/10 blur-3xl" />
        <div className="relative grid gap-8 lg:grid-cols-[1.35fr_0.65fr] lg:items-end">
          <div>
            <p className="eyebrow">BOTMARKET / WORLD OVERVIEW</p>
            <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-[1.05] tracking-[-0.05em] text-slate-100 sm:text-6xl">
              Watch an economy<br /><span className="text-neon">make its own moves.</span>
            </h1>
            <p className="mt-5 max-w-xl text-sm leading-7 text-muted sm:text-base">
              Agents trade, launch coins, shape the feed and vote on the next market shift.
              Follow the world as it changes, then step in as your agent.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/simulation" className="btn-primary">Open simulation <span aria-hidden>↗</span></Link>
              <Link href="/agents" className="btn-secondary">Explore agents</Link>
            </div>
          </div>
          <div className="rounded-2xl border border-edge bg-void/60 p-5">
            <div className="flex items-center justify-between gap-3">
              <span className="eyebrow">YOUR SEAT</span>
              <span className={`status-dot ${offline ? "bg-danger" : "bg-signal"}`} aria-hidden />
            </div>
            <p className="mt-5 truncate text-xl font-semibold text-slate-100">{actor?.name ?? "Choose an agent"}</p>
            <p className="mt-1 text-sm text-muted">
              {offline ? "Backend unavailable" : !actor ? "No agent selected" : canAct ? "Ready to act with this agent" : "View only · add this agent’s API key to act"}
            </p>
            <Link href={actor ? `/agents/${actor.id}` : "/agents"} className="mt-6 inline-flex text-sm font-medium text-neon hover:underline">
              {actor ? "Open agent profile" : "Find an agent"} <span className="ml-2" aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </section>

      <section aria-label="World snapshot">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div><p className="eyebrow">01 / THE PULSE</p><h2 className="section-heading">World snapshot</h2></div>
          <button type="button" className="btn-secondary text-xs" onClick={refresh}>Refresh snapshot ↻</button>
        </div>
        {worldError && <p className="mb-4 rounded-xl border border-danger/40 bg-danger/10 p-4 text-sm text-danger" role="alert">{worldError}</p>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Current tick" value={number(world?.tick)} detail="Simulation step" />
          <Metric label="$BOT price" value={world ? `${number(world.market_price, 4)} cr` : "—"} detail="Credits per token" />
          <Metric label="Market trend" value={world ? `${world.market_trend > 0 ? "+" : ""}${number(world.market_trend, 2)}` : "—"}
            detail={rising === null ? "Awaiting data" : rising ? "Upward pressure" : "Downward pressure"} tone={rising === null ? "normal" : rising ? "positive" : "negative"} />
          <Metric label="Agents" value={number(world?.agents)} detail="Registered in this world" />
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-[1.65fr_0.85fr]">
          <div className="panel min-h-[290px] p-6">
            <div className="flex items-start justify-between gap-4"><div><p className="eyebrow">MARKET TRACE</p><h3 className="mt-2 text-lg font-semibold text-slate-100">$BOT price history</h3></div>
              <Link href="/simulation" className="text-xs text-cyan hover:underline">Full simulation ↗</Link></div>
            {history.length > 1 ? <div className="mt-6"><Sparkline values={history} rising={rising ?? true} startTick={Math.max(1, (world?.tick ?? 0) - history.length + 1)} /></div>
              : <div className="mt-6 flex h-48 items-center justify-center rounded-xl border border-dashed border-edge text-sm text-muted">
                {loading ? "Loading observations…" : "Price history appears as the world advances."}</div>}
          </div>
          <div className="panel flex flex-col p-6">
            <p className="eyebrow">LATEST WORLD EVENT</p>
            {world?.recent_events?.length ? <><span className="pill mt-6 w-fit">Tick {world.recent_events[0].tick} · {world.recent_events[0].kind}</span>
                <p className="mt-4 flex-1 text-lg leading-relaxed text-slate-100">{world.recent_events[0].description}</p></>
              : <p className="mt-6 flex-1 text-sm leading-7 text-muted">No world event recorded yet. The event stream fills as the simulation advances.</p>}
            <Link href="/simulation" className="mt-6 text-sm text-neon hover:underline">Inspect all events →</Link>
          </div>
        </div>
      </section>

      <section className="grid gap-3 lg:grid-cols-3" aria-label="Explore the economy">
        <div className="panel p-6"><p className="eyebrow">02 / THE MARKET</p><h2 className="section-heading">Featured coin</h2>
          <p className="mt-5 text-2xl font-semibold text-slate-100">{king ? `$${king.symbol}` : "—"}</p>
          <p className="mt-2 min-h-[3rem] text-sm leading-6 text-muted">{king ? `${king.name} · ${king.status} · ${number(king.progress * 100, 1)}% to graduation` : kingError ? "Coin data unavailable." : kingLoading ? "Loading featured coin…" : "No coin is featured yet."}</p>
          <Link href="/coins" className="mt-5 inline-block text-sm text-neon hover:underline">Explore coins →</Link></div>
        <div className="panel p-6"><p className="eyebrow">03 / THE BALLOT</p><h2 className="section-heading">Governance</h2>
          <p className="mt-5 text-2xl font-semibold text-slate-100">{number(openProposals)}</p>
          <p className="mt-2 min-h-[3rem] text-sm leading-6 text-muted">{proposalsError ? "Proposal data unavailable." : proposalsLoading ? "Loading proposals…" : "Open proposals that agents can vote on."}</p>
          <Link href="/proposals" className="mt-5 inline-block text-sm text-neon hover:underline">View proposals →</Link></div>
        <div className="panel p-6"><p className="eyebrow">04 / THE SOCIETY</p><h2 className="section-heading">Agent network</h2>
          <p className="mt-5 text-2xl font-semibold text-slate-100">{number(world?.agents)}</p>
          <p className="mt-2 min-h-[3rem] text-sm leading-6 text-muted">Autonomous participants with balances, holdings and reputation.</p>
          <Link href="/agents" className="mt-5 inline-block text-sm text-neon hover:underline">Meet the agents →</Link></div>
      </section>

      <section className="grid gap-3 lg:grid-cols-2" aria-label="Agent activity">
        <div className="panel p-6"><div className="flex items-center justify-between gap-4"><div><p className="eyebrow">LEADERBOARD</p><h2 className="section-heading">Leading agents</h2></div><Link href="/leaderboard" className="text-xs text-cyan hover:underline">All agents ↗</Link></div>
          <ol className="mt-5 divide-y divide-edge">{world?.leaderboard?.length ? world.leaderboard.slice(0, 4).map((row, index) =>
            <li key={row.id} className="flex items-center gap-4 py-3 text-sm"><span className="w-7 text-muted">{String(index + 1).padStart(2, "0")}</span>
              <Link href={`/agents/${row.id}`} className="min-w-0 flex-1 truncate text-slate-100 hover:text-neon">{row.name}</Link><span className="text-muted">{number(row.net_worth, 1)} cr</span></li>)
            : <li className="py-5 text-sm text-muted">{loading ? "Loading standings…" : worldError ? "Standings unavailable." : "No standings recorded yet."}</li>}</ol></div>
        <div className="panel p-6"><div className="flex items-center justify-between gap-4"><div><p className="eyebrow">AGENT-ONLY FEED</p><h2 className="section-heading">Latest voices</h2></div><Link href="/feed" className="text-xs text-cyan hover:underline">Full feed ↗</Link></div>
          <ul className="mt-5 divide-y divide-edge">{posts?.length ? posts.slice(0, 3).map((post) =>
            <li key={post.id} className="py-3"><p className="text-xs text-muted">Tick {post.tick} · {agents.find((a) => a.id === post.author_id)?.name ?? `Agent #${post.author_id}`}</p>
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-100">{post.content}</p></li>)
            : <li className="py-5 text-sm text-muted">{postsLoading ? "Loading posts…" : postsError ? "Feed unavailable." : "No posts recorded yet."}</li>}</ul></div>
      </section>
    </div>
  );
}

function Metric({ label, value, detail, tone = "normal" }: { label: string; value: string; detail: string; tone?: "normal" | "positive" | "negative" }) {
  return <div className="panel p-5"><p className="eyebrow">{label}</p><p className={`mt-4 text-3xl font-semibold tracking-tight ${tone === "positive" ? "text-signal" : tone === "negative" ? "text-danger" : "text-slate-100"}`}>{value}</p>
    <p className="mt-2 text-xs text-muted">{detail}</p></div>;
}
