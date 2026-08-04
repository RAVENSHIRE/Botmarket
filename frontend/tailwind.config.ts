import type { Config } from "tailwindcss";

/**
 * BOTMARKET design tokens — an "AI civilization dashboard" palette:
 * deep space background, neon accents, terminal-green data highlights.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: "#05070d",
        panel: "#0d1220",
        panelHi: "#141b2e",
        edge: "#1f2a44",
        neon: "#4f8cff",
        cyan: "#38e1ff",
        signal: "#3ddc97",
        warn: "#ffb020",
        danger: "#ff5c72",
        muted: "#8090b0",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        glow: "0 0 20px rgba(79,140,255,0.25)",
      },
    },
  },
  plugins: [],
};

export default config;
