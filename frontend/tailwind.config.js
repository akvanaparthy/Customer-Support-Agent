/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Bricolage Grotesque"', "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        paper: "#F6F5F2",
        surface: "#FFFFFF",
        ink: "#17171C",
        muted: "#71717A",
        line: "#E7E5E0",
        agent: { DEFAULT: "#5648E0", hover: "#4A3DD0", soft: "#EEECFB" },
        approved: { DEFAULT: "#0F9D6E", soft: "#E6F6EF" },
        denied: { DEFAULT: "#DC2626", soft: "#FCEBEA" },
        escalated: { DEFAULT: "#D97706", soft: "#FBF0E0" },
        guardrail: { DEFAULT: "#7C3AED", soft: "#F1ECFD" },
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        pop: {
          "0%": { opacity: "0", transform: "scale(0.85)" },
          "60%": { transform: "scale(1.04)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.42s cubic-bezier(0.16,1,0.3,1) both",
        "fade-in": "fade-in 0.32s ease both",
        pop: "pop 0.35s cubic-bezier(0.16,1,0.3,1) both",
      },
    },
  },
  plugins: [],
};
