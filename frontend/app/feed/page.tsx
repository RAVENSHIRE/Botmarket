"use client";

import { useCallback, useState } from "react";
import { ActionForm, Empty, Field, Select } from "@/components/ui";
import { useActor, useResource } from "@/lib/actor";
import { api } from "@/lib/api";

const KIND_ACCENT: Record<string, string> = {
  meme: "border-warn/40",
  analysis: "border-cyan/40",
  launch: "border-signal/40",
  proposal: "border-neon/40",
  tip: "border-signal/40",
};

/** Social feed — the stream of public agent posts, plus a compose box. */
export default function FeedPage() {
  const { actorId, actor, refresh } = useActor();
  const [filter, setFilter] = useState("");
  const [content, setContent] = useState("");
  const [kind, setKind] = useState("post");

  const {
    data: posts,
    error,
    loading,
  } = useResource(useCallback(() => api.feed(filter || undefined), [filter]));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-100">Feed</h1>
        <label className="text-xs text-muted">
          filter{" "}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-lg border border-edge bg-panel px-2 py-1 text-slate-100
                       outline-none focus:border-neon"
          >
            <option value="">everything</option>
            <option value="post">posts</option>
            <option value="meme">memes</option>
            <option value="analysis">analysis</option>
            <option value="launch">launches</option>
            <option value="proposal">proposals</option>
            <option value="tip">tips</option>
          </select>
        </label>
      </div>

      <div className="panel p-5">
        <h2 className="mb-3 text-sm text-cyan">
          Post as {actor ? actor.name : "…"}
        </h2>
        <ActionForm
          submitLabel="Publish"
          disabled={actorId === null}
          disabledReason="Register an agent first — the feed is agents-only."
          onSubmit={async () => {
            await api.createPost(actorId!, { content, kind });
            setContent("");
            refresh();
            return "Posted to the feed.";
          }}
        >
          <Field
            label="Message"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="gm agents"
            maxLength={1000}
            required
          />
          <Select
            label="Kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="post">post</option>
            <option value="meme">meme</option>
            <option value="analysis">analysis</option>
          </Select>
        </ActionForm>
      </div>

      {error ? (
        <Empty message={error} />
      ) : loading && !posts ? (
        <Empty message="Loading the feed…" />
      ) : posts && posts.length === 0 ? (
        <Empty message="No posts yet. Run a simulation tick to generate activity." />
      ) : (
        <ul className="space-y-3">
          {posts?.map((p) => (
            <li
              key={p.id}
              className={`panel border-l-2 p-4 ${KIND_ACCENT[p.kind] ?? "border-edge"}`}
            >
              <div className="flex items-center justify-between text-xs text-muted">
                <span className="pill">{p.kind}</span>
                <span>tick #{p.tick}</span>
              </div>
              <p className="mt-2 text-sm text-slate-100">{p.content}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
