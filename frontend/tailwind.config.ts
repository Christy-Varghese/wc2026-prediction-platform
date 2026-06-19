import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── FIFA 2026 Match Control Center palette ──────────────────────────
        ink:     "#071226",           // primary bg
        "ink-2": "#0F1D3D",           // secondary bg
        "ink-3": "#15284A",           // card surface
        cyan:    "#00D4FF",           // primary accent
        teal:    "#00FFB2",           // secondary accent
        gold:    "#FFD700",           // gold accent
        danger:  "#FF4D4D",           // danger / live
        success: "#00E676",           // success / grass
        stadium: "#FFFFFF",           // text primary
        muted:   "#C8D3E8",           // text secondary
        line:    "rgba(0,212,255,0.12)",
        // legacy aliases kept for backward compat
        navy:    "#0F1D3D",
        "navy-2": "#15284A",
        "navy-3": "#1C3260",
        live:    "#FF4D4D",
        grass:   "#00E676",
        silver:  "#C8D3E8",
        red:     "#FF4D4D",
        acc:     "#00E676",
        acc2:    "#00D4FF",
        warn:    "#FFD700",
        bg:      "#071226",
        card:    "#0F1D3D",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans:    ["var(--font-body)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow:    "0 0 50px -8px rgba(0,212,255,0.40)",
        "glow-gold": "0 0 50px -8px rgba(255,215,0,0.35)",
        card:    "0 8px 48px -12px rgba(0,0,0,0.75)",
        ring:    "0 0 0 1px rgba(0,212,255,0.18), 0 12px 50px -16px rgba(0,0,0,0.7)",
        inner:   "inset 0 1px 0 rgba(255,255,255,0.06)",
      },
      backgroundImage: {
        // stadium floodlight hero gradient
        floodlight:
          "radial-gradient(ellipse 140% 80% at 50% -20%, rgba(0,212,255,0.22) 0%, transparent 55%), " +
          "radial-gradient(ellipse 100% 60% at 100% 0%, rgba(0,255,178,0.12) 0%, transparent 50%), " +
          "radial-gradient(ellipse 80% 50% at 0% 50%, rgba(255,215,0,0.08) 0%, transparent 50%), " +
          "linear-gradient(180deg, #0F1D3D 0%, #071226 100%)",
        "gold-sheen":
          "linear-gradient(105deg, #FFD700 0%, #FFF6B0 40%, #C8A600 60%, #FFD700 100%)",
        "cyan-sheen":
          "linear-gradient(105deg, #00D4FF 0%, #80EFFF 40%, #0088AA 60%, #00D4FF 100%)",
        "card-surface":
          "linear-gradient(135deg, rgba(21,40,74,0.9) 0%, rgba(15,29,61,0.95) 100%)",
        "hero-overlay":
          "linear-gradient(180deg, transparent 0%, rgba(7,18,38,0.8) 100%)",
      },
      keyframes: {
        pulseLive: {
          "0%,100%": { opacity: "1", transform: "scale(1)" },
          "50%":     { opacity: "0.4", transform: "scale(0.78)" },
        },
        sheen: {
          "0%":   { backgroundPosition: "200% center" },
          "100%": { backgroundPosition: "-200% center" },
        },
        rise: {
          from: { opacity: "0", transform: "translateY(14px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%,100%": { transform: "translateY(0px)" },
          "50%":     { transform: "translateY(-6px)" },
        },
        scanline: {
          "0%":   { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        ticker: {
          "0%":   { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        particleFade: {
          "0%":   { opacity: "0", transform: "scale(0)" },
          "50%":  { opacity: "1" },
          "100%": { opacity: "0", transform: "scale(1.5)" },
        },
        glowPulse: {
          "0%,100%": { boxShadow: "0 0 20px rgba(0,212,255,0.3)" },
          "50%":     { boxShadow: "0 0 60px rgba(0,212,255,0.7), 0 0 120px rgba(0,212,255,0.2)" },
        },
      },
      animation: {
        live:      "pulseLive 1.4s ease-in-out infinite",
        sheen:     "sheen 5s linear infinite",
        rise:      "rise 0.55s ease-out both",
        float:     "float 3s ease-in-out infinite",
        ticker:    "ticker 30s linear infinite",
        particle:  "particleFade 3s ease-in-out infinite",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
