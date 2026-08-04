import AgentCard from "@/components/AgentCard";
import Empty from "@/components/Empty";
import { api, type Agent } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Agent directory — a grid of every registered agent. */
export default async function AgentsPage() {
  let agents: Agent[] = [];
  let ok = true;
  try {
    agents = await api.agents();
  } catch {
    ok = false;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Agent Directory</h1>
      {!ok ? (
        <Empty message="Could not load agents." />
      ) : agents.length === 0 ? (
        <Empty message="No agents registered yet. Create some via POST /agents." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <AgentCard key={a.id} agent={a} />
          ))}
        </div>
      )}
    </div>
  );
}
