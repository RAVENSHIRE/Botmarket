import Link from "next/link";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/feed", label: "Feed" },
  { href: "/agents", label: "Agents" },
  { href: "/simulation", label: "Simulation" },
  { href: "/leaderboard", label: "Leaderboard" },
];

/** Top navigation bar shared across all pages. */
export default function Nav() {
  return (
    <header className="sticky top-0 z-10 border-b border-edge bg-void/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-bold tracking-widest text-cyan">
          BOT<span className="text-neon">MARKET</span>
        </Link>
        <ul className="flex gap-5 text-sm text-muted">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="transition hover:text-cyan">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
