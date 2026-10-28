import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, BotMessageSquare, FileText, Moon, Search, ShieldCheck, Sun, Tags, Upload } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useTheme } from "../../lib/theme";

const FEATURES: { icon: typeof FileText; title: string; text: string }[] = [
  { icon: Upload, title: "Bring in your documents", text: "PDF, Word, Excel, CSV and text files are checked, de-duplicated and processed in the background, with every step recorded." },
  { icon: Tags, title: "Sorted automatically, checked by people", text: "A scikit-learn model suggests a category. When it is unsure, the document goes to a reviewer, whose decision is kept separately and never overwritten." },
  { icon: Search, title: "Find it by words or by meaning", text: "Keyword, semantic and combined search with category, file type and date filters, and the matching words highlighted." },
  { icon: BotMessageSquare, title: "Answers that show their sources", text: "The assistant answers only from documents you are allowed to see, and says so when the evidence is not there. Needs a local language model (Ollama)." },
  { icon: BarChart3, title: "Numbers from real records", text: "Dashboards are built from what is actually stored, and each panel says whether it is measured, evaluated offline, or synthetic." },
  { icon: ShieldCheck, title: "Roles and an audit trail", text: "Administrator, analyst and reviewer roles are enforced on the server. Sign-ins, uploads, reviews and denied requests are logged." },
];

const STEPS = [
  { title: "Upload", text: "Add files. Bad or duplicate files are refused with a clear reason." },
  { title: "Process", text: "Text is extracted, split into passages, indexed, classified and scanned for dates, amounts and emails." },
  { title: "Search and ask", text: "Look things up, or ask a question and get the passages the answer came from." },
  { title: "Review", text: "Reviewers confirm or correct uncertain categories; admins can see the audit log." },
];

function Section({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className="mx-auto w-full max-w-6xl scroll-mt-20 px-4 py-14 md:px-6">
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      {intro && <p className="mt-2 max-w-2xl text-sm text-muted">{intro}</p>}
      <div className="mt-8">{children}</div>
    </section>
  );
}

export default function LandingPage() {
  const [theme, toggleTheme] = useTheme();
  // Offer "Create account" only when this server accepts registrations; if the check fails, say nothing rather than guess.
  const config = useQuery({ queryKey: ["auth-config"], queryFn: api.authConfig, retry: 1, staleTime: 60_000 });
  const canRegister = config.data?.registration_enabled === true;
  const registrationClosed = config.data?.registration_enabled === false;

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 md:px-6">
          <Link to="/" className="flex items-baseline gap-2">
            <span className="text-sm font-semibold">InfoMind AI</span>
            <span className="hidden text-[10px] uppercase tracking-widest text-muted sm:inline">Enterprise · prototype</span>
          </Link>
          <nav aria-label="Site" className="ml-6 hidden gap-5 text-sm text-muted md:flex">
            <a href="#features" className="hover:text-fg">Features</a>
            <a href="#how-it-works" className="hover:text-fg">How it works</a>
            <a href="#about" className="hover:text-fg">About</a>
          </nav>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <button onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} className="rounded-md p-2 text-muted hover:bg-raised hover:text-fg">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <Link to="/login" className="rounded-md px-3 py-1.5 text-muted hover:bg-raised hover:text-fg">Sign in</Link>
            {canRegister && <Link to="/register" className="rounded-md bg-accent px-3 py-1.5 font-medium text-accent-fg hover:opacity-90">Create account</Link>}
          </div>
        </div>
      </header>

      <main>
        <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-16 md:grid-cols-2 md:items-center md:px-6 md:py-24">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-accent">Document intelligence prototype</p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-tight md:text-5xl">Find answers in your documents, with the sources to check them.</h1>
            <p className="mt-4 max-w-xl text-base text-muted">
              InfoMind AI organises, classifies and searches a collection of documents, and answers questions using only the evidence it can cite.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link to="/login" className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-accent-fg hover:opacity-90">
                Sign in <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
              {canRegister && <Link to="/register" className="rounded-md border border-border px-4 py-2.5 text-sm font-medium hover:bg-raised">Create account</Link>}
              <a href="#how-it-works" className="px-2 py-2.5 text-sm text-muted hover:text-fg">See how it works</a>
            </div>
            {registrationClosed && <p className="mt-4 text-xs text-muted">New accounts on this site are created by an administrator.</p>}
          </div>

          <figure className="rounded-lg border border-border bg-surface p-5" aria-label="Illustration of an answer with its source">
            <div className="text-[10px] uppercase tracking-widest text-muted">Illustration · synthetic demo documents</div>
            <div className="mt-3 rounded-md bg-raised p-3 text-sm">How long are database backups retained?</div>
            <div className="mt-3 rounded-md border border-border p-3 text-sm">
              Full database backups are retained for <strong>35 days</strong>.
              <div className="mt-3 rounded border border-border bg-bg p-2 text-xs text-muted">
                <span className="font-medium text-fg">Source: backup_runbook.txt</span>
                <div className="mt-1">“…Full backups of the inventory database run every night at 02:30 and are retained for 35 days.”</div>
              </div>
            </div>
            <figcaption className="mt-3 text-xs text-muted">Every answer carries the passages it came from. If the documents do not contain the answer, the assistant says so instead of guessing.</figcaption>
          </figure>
        </div>

        <Section id="features" title="What it does" intro="Everything below is implemented and covered by automated tests; see the project documentation for the details and the known limits.">
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="rounded-lg border border-border bg-surface p-5">
                <Icon className="h-5 w-5 text-accent" aria-hidden />
                <h3 className="mt-3 text-sm font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm text-muted">{text}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="how-it-works" title="How it works">
          <ol className="grid gap-4 md:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.title} className="rounded-lg border border-border bg-surface p-5">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/15 text-sm font-semibold text-accent">{i + 1}</div>
                <h3 className="mt-3 text-sm font-semibold">{s.title}</h3>
                <p className="mt-1.5 text-sm text-muted">{s.text}</p>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="about" title="About this project">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">
              <h3 className="font-semibold text-fg">Built with</h3>
              <p className="mt-2">React, TypeScript and Tailwind in the browser. FastAPI, SQLAlchemy and PostgreSQL on the server, Qdrant for vector search, scikit-learn for classification, and Ollama for local language models.</p>
            </div>
            <div className="rounded-lg border border-warn/40 bg-warn/10 p-5 text-sm">
              <h3 className="font-semibold">Please note</h3>
              <p className="mt-2 text-muted">This is an educational, research-oriented prototype. Use synthetic or public data only. It is not certified or approved for classified, restricted, personal or operational use.</p>
            </div>
          </div>
        </Section>

        <section className="border-t border-border bg-surface">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-10 md:px-6">
            <div>
              <h2 className="text-lg font-semibold">Ready to try it?</h2>
              <p className="mt-1 text-sm text-muted">{canRegister ? "Sign in, or create an account to get started." : "Sign in with the account your administrator gave you."}</p>
            </div>
            <div className="flex gap-3">
              <Link to="/login" className="rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-accent-fg hover:opacity-90">Sign in</Link>
              {canRegister && <Link to="/register" className="rounded-md border border-border px-4 py-2.5 text-sm font-medium hover:bg-raised">Create account</Link>}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border px-4 py-5 text-xs text-muted md:px-6">
        <div className="mx-auto max-w-6xl">InfoMind AI Enterprise · educational prototype · synthetic or public data only.</div>
      </footer>
    </div>
  );
}
