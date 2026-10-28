/** Rows = true class, columns = predicted class. Cell shading is proportional to the row total. */
export function ConfusionMatrix({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const short = (s: string) => s.split(/\s+/).map((w) => w[0]).join("").toUpperCase();
  return (
    <div className="overflow-x-auto">
      <table className="text-center text-xs" aria-label="Confusion matrix">
        <thead>
          <tr><th className="p-1 text-muted">true ↓ / pred →</th>{labels.map((l) => <th key={l} scope="col" title={l} className="p-1 font-medium text-muted">{short(l)}</th>)}</tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => {
            const total = row.reduce((a, b) => a + b, 0) || 1;
            return (
              <tr key={labels[i]}>
                <th scope="row" title={labels[i]} className="p-1 text-left font-medium text-muted">{labels[i]}</th>
                {row.map((v, j) => (
                  <td key={j} className="h-8 w-10 border border-border tabular-nums" style={{ background: `rgb(var(--${i === j ? "ok" : "danger"}) / ${v === 0 ? 0 : 0.15 + 0.6 * (v / total)})` }}>{v}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">Abbreviations: {labels.map((l) => `${short(l)} = ${l}`).join(", ")}</p>
    </div>
  );
}
