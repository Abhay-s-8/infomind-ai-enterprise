/** Chart styling read from the theme tokens, so charts follow dark and light without a second palette. One series argues; the grid and axes stay neutral. */
export const chart = {
  grid: "var(--color-rule)",
  axis: "var(--color-muted)",
  series: "var(--color-cool)",
  tooltip: {
    background: "var(--color-paper-2)",
    border: "1px solid var(--color-rule-2)",
    borderRadius: 6,
    color: "var(--color-ink)",
    fontSize: 13,
  },
} as const;
