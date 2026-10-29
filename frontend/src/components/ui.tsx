import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "../lib/utils";

// Amber means a person (work waiting on someone), cool means the system; ok and danger are for status only.
type Tone = "ok" | "warn" | "danger" | "info" | "muted" | "accent";
const toneClass: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok", warn: "bg-accent-soft text-accent", danger: "bg-danger-soft text-danger",
  info: "bg-cool-soft text-cool", muted: "bg-sunk text-muted", accent: "bg-accent-soft text-accent",
};

/** A chip carries state only: the label face inside a hairline, tinted by what it means. */
export function Badge({ tone = "muted", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cn("inline-flex items-center rounded border border-border px-1.5 py-0.5 text-xs font-medium", toneClass[tone])}>{children}</span>;
}

export function Button({ variant = "primary", loading, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; loading?: boolean }) {
  const styles = {
    primary: "border border-accent bg-accent text-accent-fg hover:bg-accent/90 active:bg-accent/80",
    secondary: "border border-border-strong bg-surface text-fg hover:bg-sunk active:bg-bg",
    ghost: "border border-transparent text-muted hover:bg-sunk hover:text-fg active:bg-bg",
    danger: "border border-transparent bg-danger-soft text-danger hover:border-danger/50 active:bg-danger/20",
  }[variant];
  return (
    <button {...rest} disabled={disabled || loading}
      className={cn("inline-flex min-h-9 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-micro ease-out disabled:cursor-not-allowed disabled:opacity-50", styles, className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

/** A hairline panel one step up from the ground. */
export function Card({ title, action, children, className }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-lg border border-border bg-surface", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          {title && <h2 className="text-base">{title}</h2>}
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/** A figure and its label. It has no box of its own: set stats inside `.panels` so they share one surface. */
export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: Tone }) {
  return (
    <div className="p-4">
      <div className="text-sm text-muted">{label}</div>
      <div className={cn("reading mt-2 text-3xl", tone && toneClass[tone].split(" ")[1])}>{value}</div>
      {hint && <div className="mt-2 text-xs text-muted">{hint}</div>}
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

/** `bare` drops the box, for use inside a panel that already has one. */
export function EmptyState({ title, children, action, bare }: { title: string; children?: ReactNode; action?: ReactNode; bare?: boolean }) {
  return (
    <div className={cn("flex flex-col items-center gap-2 px-6 py-10 text-center", !bare && "rounded-lg border border-border bg-surface")}>
      <Inbox className="h-5 w-5 text-muted" aria-hidden />
      <p className="font-medium">{title}</p>
      {children && <p className="max-w-md text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-danger/50 bg-danger-soft p-4 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden />
      <div className="flex-1">
        <p>{message}</p>
        {onRetry && <button onClick={onRetry} className="link mt-2">Retry</button>}
      </div>
    </div>
  );
}

export function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block text-muted">{label}</span>
      {children}
      {error && <span role="alert" className="mt-1.5 block text-xs text-danger">{error}</span>}
    </label>
  );
}

// Inputs sit on the deepest step inside an edge that reads against the panel (3:1).
const inputClass = "w-full rounded-md border border-edge bg-sunk px-3 py-2 text-sm placeholder:text-muted transition-colors duration-micro ease-out hover:border-fg-2 focus:border-accent disabled:opacity-50";
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
        <thead className="text-muted">
          <tr>{head.map((h) => <th key={h} scope="col" className="border-b border-border-strong px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-border [&>tr]:transition-colors [&>tr]:duration-micro [&>tr:hover]:bg-sunk">{children}</tbody>
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
