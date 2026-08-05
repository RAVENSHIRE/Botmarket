import type { Metadata } from "next";
import Nav from "@/components/Nav";
import { ActorProvider } from "@/lib/actor";
import "./globals.css";

export const metadata: Metadata = {
  title: "BOTMARKET — AI Civilization Dashboard",
  description: "An autonomous agent economy simulation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ActorProvider>
          <Nav />
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </ActorProvider>
      </body>
    </html>
  );
}
