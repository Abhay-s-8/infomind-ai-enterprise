/** Colours come from src/styles/tokens.css (arcade night and cream cartridge); a name here only points at a token. The alpha slot keeps utilities like bg-accent/15 working. */
const token = (name) => `color-mix(in oklab, var(--color-${name}) calc(<alpha-value> * 100%), transparent)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // the three lightness steps: ground, panel, deepest (inputs, code, hovers)
        bg: token("paper"), surface: token("paper-2"), sunk: token("paper-3"), raised: token("paper-3"),
        border: token("rule"), "border-strong": token("rule-2"), edge: token("edge"), pixel: token("pixel"), shadow: token("shadow"),
        fg: token("ink"), "fg-2": token("ink-2"), muted: token("muted"),
        // yellow (red-orange in light) is a person: the one primary action, the current page, work waiting on someone; cool is the system
        accent: token("accent"), "accent-fg": token("accent-ink"), "accent-soft": token("accent-soft"),
        cool: token("cool"), "cool-soft": token("cool-soft"),
        ok: token("ok"), "ok-soft": token("ok-soft"), danger: token("bad"), "danger-soft": token("bad-soft"),
        warn: token("accent"), info: token("cool"),
      },
      fontFamily: { sans: ["var(--font-body)"], display: ["var(--font-display)"], mono: ["var(--font-outlier)"] },
      // a pixel look has no rounded corners
      borderRadius: { none: "0", sm: "0", DEFAULT: "0", md: "0", lg: "0", xl: "0", full: "0" },
      transitionTimingFunction: { out: "var(--ease-out)" },
      transitionDuration: { micro: "var(--dur-micro)", short: "var(--dur-short)" },
    },
  },
  plugins: [],
};
