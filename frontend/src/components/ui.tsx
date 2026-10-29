import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { Button as PixelButton, Card as PixelCard, InputStyles } from "pixel-retroui";
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "../lib/utils";

// Yellow (red-orange in light) means a person, cool means the system; ok and danger are for status only.
type Tone = "ok" | "warn" | "danger" | "info" | "muted" | "accent";
const toneClass: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok", warn: "bg-accent-soft text-accent", danger: "bg-danger-soft text-danger",
  info: "bg-cool-soft text-cool", muted: "bg-sunk text-muted", accent: "bg-accent-soft text-accent",
};

/** A chip carries state only: a pixel outline in the tone's own colour. */
export function Badge({ tone = "muted", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cn("inline-flex items-center border-2 border-current px-1.5 py-0.5 font-display text-xs", toneClass[tone])}>{children}</span>;
}

type Variant = "primary" | "secondary" | "ghost" | "danger";
// The pixel-retroui button takes its colours as props; each variant names tokens, never literals.
const buttonColors: Record<Variant, { bg?: string; textColor?: string; shadow?: string; borderColor?: string }> = {
  primary: { bg: "var(--color-accent)", textColor: "var(--color-accent-ink)" },
  secondary: {},
  ghost: { bg: "transparent", textColor: "var(--color-muted)", shadow: "transparent", borderColor: "transparent" },
  danger: { bg: "var(--color-bad-soft)", textColor: "var(--color-bad)", borderColor: "var(--color-bad)" },
};

export function Button({ variant = "primary", loading, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <PixelButton {...rest} {...buttonColors[variant]} disabled={disabled || loading}
      className={cn("!m-0 inline-flex min-h-9 items-center justify-center gap-2 !px-3 !py-1.5 text-sm", className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </PixelButton>
  );
}

/** A pixel-retroui card with an optional title bar. */
export function Card({ title, action, children, className }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <PixelCard className={cn("!m-0 !p-0", className)}>
      <section>
        {(title || action) && (
          <header className="flex items-center justify-between gap-2 border-b-4 border-pixel px-4 py-3">
            {title && <h2 className="text-base">{title}</h2>}
            {action}
          </header>
        )}
        <div className="p-4">{children}</div>
      </section>
    </PixelCard>
  );
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm text-muted">{description}</p>}
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
    <div className={cn("flex flex-col items-center gap-2 px-6 py-10 text-center", !bare && "pixel-panel")}>
      <Inbox className="h-6 w-6 text-muted" aria-hidden />
      <p className="font-display">{title}</p>
      {children && <p className="max-w-md text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="flex items-start gap-3 border-4 border-danger bg-danger-soft p-4 text-sm">
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

// forwardRef is required so react-hook-form's register() can attach its ref. The pixel-retroui Input cannot take one,
// so this reuses its exported frame and field styles around a plain input.
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return (
    <div className={cn(InputStyles.pixelContainer, "!block w-full", className)}>
      <input {...props} ref={ref} className={cn(InputStyles.pixelInput, "w-full !py-2 text-sm placeholder:text-muted disabled:opacity-50")} />
    </div>
  );
});
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...props }, ref) {
  return <select {...props} ref={ref} className={cn("pixel-field w-full px-3 py-2 text-sm disabled:opacity-50", className)} />;
});

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-muted">
          <tr>{head.map((h) => <th key={h} scope="col" className="border-b-4 border-pixel px-3 py-2 font-display text-xs font-normal">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y-2 divide-border [&>tr]:transition-colors [&>tr]:duration-micro [&>tr:hover]:bg-sunk">{children}</tbody>
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
