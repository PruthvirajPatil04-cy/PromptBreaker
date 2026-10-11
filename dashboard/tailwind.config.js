/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0A0B",
        card: "#121214",
        cardHover: "#17171A",
        border: "#1F1F23",
        borderHover: "#2A2A30",
        text: "#E5E7EB",
        muted: "#8B8D93",
        faint: "#5A5C63",
        accent: "#14B8A6",
        accentHover: "#2DD4BF",
        pass: "#22C55E",
        fail: "#EF4444",
        warn: "#F59E0B",
        bandLow: "#A3E635",
        bandModerate: "#EAB308",
        bandHigh: "#F59E0B",
        bandCritical: "#EF4444",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        card: "12px",
        pill: "9999px",
      },
    },
  },
  plugins: [],
};
