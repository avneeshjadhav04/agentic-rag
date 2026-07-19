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
        surface: "#121212",
        panel: "#1a1a1a",
        border: "#2a2a2a",
        muted: "#a0a0a0",
        primary: {
          DEFAULT: "#ff6b00",
          dark: "#cc5500",
          light: "#ff8c33",
        },
        text: {
          DEFAULT: "#f0f0f0",
          muted: "#a0a0a0",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      animation: {
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
