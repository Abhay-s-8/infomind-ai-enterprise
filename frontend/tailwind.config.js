/** Colors are CSS variables (see src/styles/index.css) so dark/light themes share one token set. */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: token("bg"), surface: token("surface"), raised: token("raised"), border: token("border"),
        fg: token("fg"), muted: token("muted"), accent: token("accent"), "accent-fg": token("accent-fg"),
        ok: token("ok"), warn: token("warn"), danger: token("danger"), info: token("info"),
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"] },
    },
  },
  plugins: [],
};
