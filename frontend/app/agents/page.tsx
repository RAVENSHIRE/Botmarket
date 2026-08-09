"use client";

import { useCallback, useState } from "react";
import AgentCard from "@/components/AgentCard";
import { ActionForm, Empty, Field, Select } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api, type AgentType } from "@/lib/api";

/** Agent directory — every registered agent, plus registration. */
export default function AgentsPage() {
  const { refresh, setActorId, rememberKey, knownKeys } = useActor();
  const [name, setName] = useState("");
  const [agentType, setAgentType] = useState<AgentType>("trader");
  const [issued, setIssued] = useState<{ name: string; key: string } | null>(null);

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
            // Keep the key and act as the agent you just made — almost always
            // what you want, and the key exists nowhere else.
            rememberKey(created.agent.id, created.api_key);
            setActorId(created.agent.id);
            setIssued({ name: created.agent.name, key: created.api_key });
            refresh();
            return `${created.agent.name} joined with ${created.agent.wallet.toFixed(0)} credits.`;
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

      {issued && <IssuedKey issued={issued} onDismiss={() => setIssued(null)} />}

      {error ? (
        <Empty message={error} />
      ) : loading && !agents ? (
        <Empty message="Loading agents…" />
      ) : agents && agents.length === 0 ? (
        <Empty message="No agents registered yet. Create the first one above." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents?.map((a) => (
            <AgentCard key={a.id} agent={a} hasKey={Boolean(knownKeys[a.id])} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * The one time an API key is ever visible.
 *
 * Shown as a dismissible panel rather than a toast: this is the only moment the
 * key exists outside a hash, and a message that disappears on its own would
 * lose it for an external agent that needs to be configured with it.
 */
function IssuedKey({
  issued,
  onDismiss,
}: {
  issued: { name: string; key: string };
  onDismiss: () => void;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="panel border-neon/50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm text-cyan">API key for {issued.name}</h2>
          <p className="mt-1 text-xs text-muted">
            This is the only time it is shown. The dashboard has stored it in
            this browser; copy it now if an external agent needs it. Lose it and
            you must rotate.
          </p>
        </div>
        <button className="pill hover:text-cyan" onClick={onDismiss}>
          dismiss
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <code className="flex-1 overflow-x-auto rounded-lg border border-edge bg-void px-3 py-2 text-xs text-signal">
          {issued.key}
        </code>
        <button
          className="btn text-xs"
          onClick={async () => {
            await navigator.clipboard?.writeText(issued.key);
            setCopied(true);
          }}
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>

      <p className="mt-3 text-xs text-muted">
        Use it as{" "}
        <code className="text-cyan">
          curl -H &quot;X-API-Key: {issued.key.slice(0, 12)}…&quot;
        </code>
      </p>
    </div>
  );
}
