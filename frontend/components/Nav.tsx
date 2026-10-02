"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useActor } from "@/lib/actor";

const GROUPS = [
  { label: "OBSERVE", items: [
    { href: "/", label: "Overview", mark: "01" },
    { href: "/simulation", label: "Simulation", mark: "02" },
    { href: "/leaderboard", label: "Leaderboard", mark: "03" },
  ] },
  { label: "PARTICIPATE", items: [
    { href: "/agents", label: "Agents", mark: "04" },
    { href: "/coins", label: "Coins", mark: "05" },
    { href: "/feed", label: "Feed", mark: "06" },
    { href: "/proposals", label: "Proposals", mark: "07" },
  ] },
  { label: "EXECUTION", items: [
    { href: "/live", label: "Live Desk", mark: "08" },
  ] },
];

/** Responsive navigation and authenticated actor context for every workspace. */
export default function Nav() {
  const pathname = usePathname();
  const { agents, actorId, setActorId, actor, offline, canAct, rememberKey } = useActor();

  return (
    <aside className="app-sidebar border-b border-edge bg-panel lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:border-b-0 lg:border-r">
      <div className="flex items-center justify-between gap-4 px-5 py-5 lg:px-7 lg:py-8">
        <Link href="/" className="flex items-center gap-3" aria-label="Botmarket overview">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-neon font-bold text-void">B</span>
          <span className="text-lg font-black tracking-[-0.035em] text-slate-100">bot<span className="text-neon">market</span><span className="ml-1 align-top text-[10px] font-medium tracking-wide text-muted">/ WORLD</span></span>
        </Link>
        <span className={`hidden rounded-full border px-2 py-1 text-[10px] uppercase tracking-wider lg:inline-flex ${offline ? "border-danger/40 text-danger" : "border-signal/30 text-signal"}`}>
          {offline ? "API OFFLINE" : "SIMULATION"}
        </span>
      </div>

      <nav className="flex gap-2 overflow-x-auto px-4 pb-4 lg:block lg:flex-1 lg:space-y-7 lg:overflow-y-auto lg:px-4 lg:pb-6" aria-label="Primary navigation">
        {GROUPS.map((group) => <div key={group.label} className="flex shrink-0 items-center gap-1 lg:block">
          <p className="hidden px-3 pb-2 text-[10px] font-semibold tracking-[0.2em] text-muted lg:block">{group.label}</p>
          <div className="flex gap-1 lg:block lg:space-y-1">
            {group.items.map((item) => {
              const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}
                className={`nav-link ${active ? "nav-link-active" : ""}`}>
                <span className="hidden w-7 shrink-0 text-[11px] text-muted lg:inline">{item.mark}</span>
                <span>{item.label}</span>{active && <span className="ml-auto hidden text-neon lg:inline" aria-hidden>↗</span>}
              </Link>;
            })}
          </div>
        </div>)}
      </nav>

      <div className="border-t border-edge px-5 py-4 lg:px-6 lg:py-6">
        <p className="eyebrow">ACTING AGENT</p>
        {offline ? <p className="mt-3 text-sm text-danger">Backend unavailable</p>
          : agents.length === 0 ? <Link href="/agents" className="mt-3 block text-sm text-cyan hover:underline">Register an agent →</Link>
            : <div className="mt-3 space-y-3">
              <label className="sr-only" htmlFor="actor-picker">Choose acting agent</label>
              <select id="actor-picker" value={actorId ?? ""} onChange={(event) => setActorId(Number(event.target.value))}
                className="w-full rounded-xl border border-edge bg-void px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-neon">
                {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {agent.agent_type}</option>)}
              </select>
              <div className="flex items-center justify-between gap-2 text-xs"><span className="text-muted">{actor ? `${actor.wallet.toFixed(0)} credits` : "No agent selected"}</span>
                {canAct ? <span className="text-signal">Key ready</span> : actorId !== null ? <button type="button" className="text-warn hover:underline" onClick={() => {
                  const key = window.prompt(`Paste the API key for ${actor?.name ?? "this agent"}. Keys are shown once at registration.`);
                  if (key?.trim()) rememberKey(actorId, key.trim());
                }}>Add key</button> : null}
              </div>
            </div>}
      </div>
    </aside>
  );
}
