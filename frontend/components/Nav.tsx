"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useActor } from "@/lib/actor";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/simulation", label: "Simulation" },
  { href: "/feed", label: "Feed" },
  { href: "/agents", label: "Agents" },
  { href: "/coins", label: "Coins" },
  { href: "/proposals", label: "Proposals" },
  { href: "/live", label: "Live Desk" },
  { href: "/leaderboard", label: "Leaderboard" },
];

/**
 * Top navigation, plus the picker for the agent the dashboard acts as.
 *
 * Every write endpoint is scoped to an agent, so the picker is part of the
 * chrome rather than something each page repeats.
 */
export default function Nav() {
  const pathname = usePathname();
  const { agents, actorId, setActorId, actor, offline } = useActor();

  return (
    <header className="sticky top-0 z-10 border-b border-edge bg-void/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-6 py-4">
        <Link href="/" className="text-lg font-bold tracking-widest text-cyan">
          BOT<span className="text-neon">MARKET</span>
        </Link>

        <ul className="flex flex-1 flex-wrap gap-4 text-sm text-muted">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className={`transition hover:text-cyan ${
                  pathname === l.href ? "text-cyan" : ""
                }`}
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>

        {offline ? (
          <span className="pill text-danger">API offline</span>
        ) : agents.length === 0 ? (
          <span className="pill">no agents yet</span>
        ) : (
          <label className="flex items-center gap-2 text-xs text-muted">
            acting as
            <select
              value={actorId ?? ""}
              onChange={(e) => setActorId(Number(e.target.value))}
              className="rounded-lg border border-edge bg-panel px-2 py-1 text-slate-100
                         outline-none focus:border-neon"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.agent_type})
                </option>
              ))}
            </select>
            {actor && (
              <span className="text-signal">{actor.wallet.toFixed(0)} cr</span>
            )}
          </label>
        )}
      </nav>
    </header>
  );
}
