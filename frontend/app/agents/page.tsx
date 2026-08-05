"use client";

import { useCallback, useState } from "react";
import AgentCard from "@/components/AgentCard";
import { ActionForm, Empty, Field, Select } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api, type AgentType } from "@/lib/api";

/** Agent directory — every registered agent, plus registration. */
export default function AgentsPage() {
  const { refresh, setActorId } = useActor();
  const [name, setName] = useState("");
  const [agentType, setAgentType] = useState<AgentType>("trader");

  const {
    data: agents,
    error,
    loading,
  } = useResource(useCallback(() => api.agents(), []));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Agent Directory</h1>

      <div className="panel p-5">
        <h2 className="mb-3 text-sm text-cyan">Register an agent</h2>
        <ActionForm
          submitLabel="Register"
          onSubmit={async () => {
            const created = await api.createAgent({
              name,
              agent_type: agentType,
            });
            setName("");
            // Act as the agent you just made — it is almost always what you want.
            setActorId(created.id);
            refresh();
            return `${created.name} joined the economy with ${created.wallet.toFixed(0)} credits.`;
          }}
        >
          <Field
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nova"
            maxLength={120}
            required
          />
          <Select
            label="Archetype"
            value={agentType}
            onChange={(e) => setAgentType(e.target.value as AgentType)}
          >
            <option value="trader">trader — trades the market</option>
            <option value="meme">meme — shapes sentiment</option>
            <option value="analyst">analyst — reports conditions</option>
          </Select>
        </ActionForm>
      </div>

      {error ? (
        <Empty message={error} />
      ) : loading && !agents ? (
        <Empty message="Loading agents…" />
      ) : agents && agents.length === 0 ? (
        <Empty message="No agents registered yet. Create the first one above." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents?.map((a) => (
            <AgentCard key={a.id} agent={a} />
          ))}
        </div>
      )}
    </div>
  );
}
