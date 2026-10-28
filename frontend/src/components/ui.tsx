import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "../lib/utils";

type Tone = "ok" | "warn" | "danger" | "info" | "muted" | "accent";
const toneClass: Record<Tone, string> = {
  ok: "bg-ok/15 text-ok", warn: "bg-warn/15 text-warn", danger: "bg-danger/15 text-danger",
  info: "bg-info/15 text-info", muted: "bg-raised text-muted", accent: "bg-accent/15 text-accent",
};

export function Badge({ tone = "muted", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", toneClass[tone])}>{children}</span>;
}

export function Button({ variant = "primary", loading, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; loading?: boolean }) {
  const styles = {
    primary: "bg-accent text-accent-fg hover:opacity-90",
    secondary: "bg-raised text-fg border border-border hover:bg-border/60",
    ghost: "text-muted hover:text-fg hover:bg-raised",
    danger: "bg-danger/15 text-danger hover:bg-danger/25",
  }[variant];
  return (
    <button {...rest} disabled={disabled || loading}
      className={cn("inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed", styles, className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Card({ title, action, children, className }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-lg border border-border bg-surface", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          {title && <h2 className="text-sm font-semibold">{title}</h2>}
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: Tone }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold tabular-nums", tone && toneClass[tone].split(" ")[1])}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}…
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-6 py-10 text-center">
      <Inbox className="h-6 w-6 text-muted" aria-hidden />
      <p className="font-medium">{title}</p>
      {children && <p className="max-w-md text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden />
      <div className="flex-1">
        <p>{message}</p>
        {onRetry && <button onClick={onRetry} className="mt-2 text-accent underline">Retry</button>}
      </div>
    </div>
  );
}

export function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-muted">{label}</span>
      {children}
      {error && <span role="alert" className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
}

const inputClass = "w-full rounded-md border border-border bg-bg px-3 py-2 text-sm placeholder:text-muted/70 focus:border-accent";
// forwardRef is required so react-hook-form's register() can attach its ref
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(props, ref) {
  return <input {...props} ref={ref} className={cn(inputClass, props.className)} />;
});
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(props, ref) {
  return <select {...props} ref={ref} className={cn(inputClass, props.className)} />;
});

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-muted">
          <tr>{head.map((h) => <th key={h} scope="col" className="border-b border-border px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  );
}

export function SourceNote({ kind }: { kind: "measured" | "offline" | "synthetic" }) {
  const map = {
    measured: ["info", "Measured from application records"],
    offline: ["warn", "Offline evaluation on held-out data"],
    synthetic: ["warn", "Synthetic data: demonstrates the pipeline, not real-world accuracy"],
  } as const;
  return <Badge tone={map[kind][0]}>{map[kind][1]}</Badge>;
}
