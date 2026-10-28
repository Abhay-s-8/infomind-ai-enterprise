import { z } from "zod";

export const cn = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export const pct = (v: number | null | undefined, digits = 1) => (v === null || v === undefined ? "n/a" : `${(v * 100).toFixed(digits)}%`);

export const ALLOWED_EXTENSIONS = ["pdf", "docx", "txt", "csv", "xlsx"] as const;
export const MAX_UPLOAD_MB = 25;

/** Client-side pre-check for fast feedback; the server re-validates extension, MIME and file structure. */
export function validateFile(file: File): string | null {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) return `Unsupported type ".${ext}". Allowed: ${ALLOWED_EXTENSIONS.join(", ")}.`;
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `Exceeds the ${MAX_UPLOAD_MB} MB limit.`;
  return null;
}

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
export const registerSchema = loginSchema.extend({
  password: z.string().min(10, "Use at least 10 characters"),
  full_name: z.string().max(255).optional(),
});

export const STATUS_TONE: Record<string, "ok" | "warn" | "danger" | "info" | "muted"> = {
  completed: "ok", indexed: "ok", failed: "danger", uploaded: "info", queued: "info",
  extracting: "warn", chunking: "warn", embedding: "warn", classifying: "warn",
};

/** Split text into plain/highlighted segments for safe rendering (no dangerouslySetInnerHTML). */
export function highlightParts(text: string, terms: string[]): { text: string; hit: boolean }[] {
  const clean = terms.filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!clean.length) return [{ text, hit: false }];
  const rx = new RegExp(`(${clean.join("|")})`, "gi");
  // split() with one capture group alternates non-match (even index) and match (odd index)
  return text.split(rx).map((s, i) => ({ text: s, hit: i % 2 === 1 })).filter((p) => p.text !== "");
}
