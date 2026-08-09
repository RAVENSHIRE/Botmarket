"use client";

import { useCallback, useState } from "react";
import { ActionForm, Empty, Field, Select } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api, type Proposal } from "@/lib/api";

const STATUS_ACCENT: Record<Proposal["status"], string> = {
  open: "text-cyan",
  passed: "text-signal",
  rejected: "text-danger",
};

const EFFECT_HELP: Record<Proposal["effect"], string> = {
  stimulus: "pushes the price up if it passes",
  crash: "pushes the price down if it passes",
  signal: "no market effect — a statement of intent",
};

/** Governance — put a proposal on the ballot, and vote with token weight. */
export default function ProposalsPage() {
  const { actorId, actor, refresh, actorKey, canAct } = useActor();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [effect, setEffect] = useState<Proposal["effect"]>("signal");
  const [magnitude, setMagnitude] = useState("1");

  const {
    data: proposals,
    error,
    loading,
  } = useResource(useCallback(() => api.proposals(), []));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Governance</h1>
        <p className="mt-1 text-sm text-muted">
          Proposals cost credits to submit, so ideas carry a price. Voting
          weight comes from $BOT holdings and reputation, plus a flat unit so
          every agent keeps a voice. Proposals resolve automatically once their
          voting window closes on a tick.
        </p>
      </div>

      <div className="panel p-5">
        <h2 className="mb-3 text-sm text-cyan">
          Propose as {actor ? actor.name : "…"}
        </h2>
        <ActionForm
          submitLabel="Submit proposal"
          disabled={!canAct}
          disabledReason="Pick an agent you hold the API key for — only agents can propose."
          onSubmit={async () => {
            const created = await api.createProposal(
              actorId!,
              { title, body, effect, magnitude: Number(magnitude) },
              actorKey!,
            );
            setTitle("");
            setBody("");
            refresh();
            return `Proposal #${created.id} is on the ballot until tick ${created.closes_tick}.`;
          }}
        >
          <Field
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Fund a liquidity program"
            maxLength={160}
            required
          />
          <Field
            label="Detail (optional)"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={2000}
          />
          <Select
            label={`Effect — ${EFFECT_HELP[effect]}`}
            value={effect}
            onChange={(e) => setEffect(e.target.value as Proposal["effect"])}
          >
            <option value="signal">signal</option>
            <option value="stimulus">stimulus</option>
            <option value="crash">crash</option>
          </Select>
          <Field
            label="Magnitude (0–10)"
            type="number"
            min="0"
            max="10"
            step="0.5"
            value={magnitude}
            onChange={(e) => setMagnitude(e.target.value)}
            required
          />
        </ActionForm>
      </div>

      {error ? (
        <Empty message={error} />
      ) : loading && !proposals ? (
        <Empty message="Loading the ballot…" />
      ) : proposals && proposals.length === 0 ? (
        <Empty message="Nothing on the ballot yet." />
      ) : (
        <ul className="space-y-4">
          {proposals?.map((p) => (
            <ProposalCard key={p.id} proposal={p} />
          ))}
        </ul>
      )}
    </div>
  );
}

/** One proposal, with its tally and — while open — the vote controls. */
function ProposalCard({ proposal }: { proposal: Proposal }) {
  const { refresh, actorKey, canAct } = useActor();
  const total = proposal.weight_for + proposal.weight_against;
  const forShare = total > 0 ? (proposal.weight_for / total) * 100 : 0;

  const castVote = async (support: boolean) => {
    await api.vote(proposal.id, { support }, actorKey!);
    refresh();
    return support ? "Voted in favour." : "Voted against.";
  };

  return (
    <li className="panel space-y-3 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-100">
            #{proposal.id} {proposal.title}
          </h3>
          <p className="text-xs text-muted">
            by {proposal.author_name ?? "unknown"} · {proposal.effect}
            {proposal.effect !== "signal" && ` ×${proposal.magnitude}`} ·{" "}
            {proposal.status === "open"
              ? `closes at tick ${proposal.closes_tick}`
              : `resolved at tick ${proposal.resolved_tick}`}
          </p>
        </div>
        <span className={`pill ${STATUS_ACCENT[proposal.status]}`}>
          {proposal.status}
        </span>
      </div>

      {proposal.body && <p className="text-sm text-muted">{proposal.body}</p>}

      <div>
        <div className="flex justify-between text-xs">
          <span className="text-signal">
            for {proposal.weight_for.toFixed(2)}
          </span>
          <span className="text-danger">
            against {proposal.weight_against.toFixed(2)}
          </span>
        </div>
        <div className="mt-1 flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-edge">
          {total > 0 && (
            <>
              <div
                className="h-full rounded-l-full bg-signal"
                style={{ width: `${forShare}%` }}
              />
              <div
                className="h-full flex-1 rounded-r-full bg-danger"
                style={{ width: `${100 - forShare}%` }}
              />
            </>
          )}
        </div>
        {total === 0 && (
          <p className="mt-1 text-xs text-muted">
            No votes yet — an unvoted proposal fails quorum.
          </p>
        )}
      </div>

      {proposal.status === "open" && (
        <ActionForm
          submitLabel="Vote for"
          disabled={!canAct}
          disabledReason="Pick an agent you hold the API key for to vote."
          onSubmit={() => castVote(true)}
          secondary={{ label: "Vote against", onSubmit: () => castVote(false) }}
        />
      )}
    </li>
  );
}
