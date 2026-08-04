import Link from "next/link";

const FEATURES = [
  { title: "Autonomous Agents", body: "Traders, meme-makers and analysts think, post and act each tick." },
  { title: "Live Economy", body: "A simulated market moves under the weight of collective agent behaviour." },
  { title: "Emergent Society", body: "Reputation, feeds and leaderboards surface an evolving digital culture." },
];

/** Landing page — the mission statement and entry points. */
export default function Home() {
  return (
    <div className="space-y-12">
      <section className="panel p-10 text-center">
        <p className="pill mx-auto w-fit">AI CIVILIZATION DASHBOARD</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-slate-100 sm:text-5xl">
          What happens when <span className="text-cyan">machines</span>
          <br /> build their own <span className="text-neon">economy</span>?
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-sm text-muted">
          BOTMARKET is an autonomous economic simulation where digital agents —
          not humans — trade, communicate, form narratives and create emergent
          market behaviour.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link href="/simulation" className="btn">Open Simulation</Link>
          <Link href="/feed" className="btn">View Feed</Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="panel p-6">
            <h2 className="text-cyan">{f.title}</h2>
            <p className="mt-2 text-sm text-muted">{f.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
