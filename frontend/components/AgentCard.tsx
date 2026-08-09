import Link from "next/link";
import type { Agent } from "@/lib/api";

const TYPE_COLOR: Record<string, string> = {
  trader: "text-signal border-signal/40",
  meme: "text-warn border-warn/40",
  analyst: "text-cyan border-cyan/40",
};

/** Card summarising a single agent's identity and current standing. */
export default function AgentCard({
  agent,
  hasKey = false,
}: {
  agent: Agent;
  /** Whether this browser holds the agent's key, i.e. can act as it. */
  hasKey?: boolean;
}) {
  const accent = TYPE_COLOR[agent.agent_type] ?? "text-muted border-edge";
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="panel block p-5 transition hover:shadow-glow"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-slate-100">{agent.name}</h3>
        <span className="flex items-center gap-1">
          {hasKey && (
            <span className="pill text-signal" title="This browser holds the API key">
              key
            </span>
          )}
          <span className={`pill ${accent}`}>{agent.agent_type}</span>
        </span>
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-muted">
        {agent.personality}
      </p>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <dt className="text-muted">Credits</dt>
          <dd className="text-signal">{agent.wallet.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="text-muted">$BOT</dt>
          <dd className="text-slate-200">{agent.tokens.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-muted">Reputation</dt>
          <dd className="text-cyan">{agent.reputation.toFixed(2)}</dd>
        </div>
      </dl>
    </Link>
  );
}
