import type { Agent } from "@/lib/api";

const TYPE_COLOR: Record<string, string> = {
  trader: "text-signal border-signal/40",
  meme: "text-warn border-warn/40",
  analyst: "text-cyan border-cyan/40",
};

/** Card summarising a single agent's identity and current standing. */
export default function AgentCard({ agent }: { agent: Agent }) {
  const accent = TYPE_COLOR[agent.agent_type] ?? "text-muted border-edge";
  return (
    <div className="panel p-5 transition hover:shadow-glow">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-100">{agent.name}</h3>
        <span className={`pill ${accent}`}>{agent.agent_type}</span>
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-muted">{agent.personality}</p>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <dt className="text-muted">Wallet</dt>
          <dd className="text-signal">{agent.wallet.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="text-muted">Reputation</dt>
          <dd className="text-cyan">{agent.reputation.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-muted">Status</dt>
          <dd className="text-slate-200">{agent.status}</dd>
        </div>
      </dl>
    </div>
  );
}
