import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Statistics Sierra Leone / SLPHC 2026 dark-blue operational branding (brief §20).
        brand: {
          50: "#eef3fb",
          100: "#d6e2f5",
          200: "#adc5eb",
          300: "#7fa3de",
          400: "#4f7fce",
          500: "#2f5fb3",
          600: "#1f4791",
          700: "#183a76",
          800: "#132c5c",
          900: "#0c1c3d",
          950: "#070f22",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
