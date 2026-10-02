import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#080d12",
        panel: "#111a21",
        panelHi: "#19252b",
        edge: "#293840",
        neon: "#c3f04f",
        cyan: "#a5e3dd",
        signal: "#b6eb5e",
        warn: "#ffca7a",
        danger: "#ff8c91",
        muted: "#9aadb6",
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
      boxShadow: { glow: "0 0 28px rgba(195, 240, 79, .12)" },
    },
  },
  plugins: [],
};

export default config;
