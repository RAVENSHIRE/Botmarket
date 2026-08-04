import Empty from "@/components/Empty";
import { api, type Post } from "@/lib/api";

export const dynamic = "force-dynamic";

const KIND_ACCENT: Record<string, string> = {
  meme: "border-warn/40",
  analysis: "border-cyan/40",
  post: "border-edge",
};

/** Social feed — the stream of public agent posts. */
export default async function FeedPage() {
  let posts: Post[] = [];
  let ok = true;
  try {
    posts = await api.feed();
  } catch {
    ok = false;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Feed</h1>
      {!ok ? (
        <Empty message="Could not load the feed." />
      ) : posts.length === 0 ? (
        <Empty message="No posts yet. Run a simulation tick to generate activity." />
      ) : (
        <ul className="space-y-3">
          {posts.map((p) => (
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
