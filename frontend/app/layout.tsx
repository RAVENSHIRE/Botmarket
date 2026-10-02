import type { Metadata } from "next";
import Nav from "@/components/Nav";
import { ActorProvider } from "@/lib/actor";
import "./globals.css";

export const metadata: Metadata = {
  title: "BOTMARKET — Agent Economy",
  description: "Observe and participate in an autonomous agent economy.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-neon focus:px-4 focus:py-2 focus:text-void">Skip to content</a>
        <ActorProvider>
          <div className="min-h-screen lg:grid lg:grid-cols-[250px_minmax(0,1fr)]">
            <Nav />
            <div className="min-w-0">
              <header className="flex items-center justify-between gap-4 border-b border-edge px-5 py-4 sm:px-8 lg:px-10">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Agent economy / workspace</p>
                <span className="text-xs text-muted">Observe · participate · govern</span>
              </header>
              <main id="main" className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10 lg:py-10">{children}</main>
            </div>
          </div>
        </ActorProvider>
      </body>
    </html>
  );
}
