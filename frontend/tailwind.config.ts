import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0a",
        surface: "#111111",
        panel: "#161616",
        line: "#242424",
        muted: "#6e6e6e",
        accent: "#ff5a1f",
        success: "#22c55e",
        text: {
          DEFAULT: "#e8e8e8",
          muted: "#6e6e6e",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter-tight)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.04em",
        tighter: "-0.02em",
        wider: "0.05em",
        widest: "0.12em",
      },
      animation: {
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
  ],
};

export default config;