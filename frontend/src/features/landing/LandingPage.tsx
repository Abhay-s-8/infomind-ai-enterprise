import { useQuery } from "@tanstack/react-query";
import { Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useTheme } from "../../lib/theme";

const FEATURES: { title: string; text: string }[] = [
  { title: "Bring in your documents", text: "PDF, Word, Excel, CSV and text files are checked, de-duplicated and processed in the background, with every step recorded." },
  { title: "Sorted automatically, checked by people", text: "A scikit-learn model suggests a category. When it is unsure, the document goes to a reviewer, whose decision is kept separately and never overwritten." },
  { title: "Find it by words or by meaning", text: "Keyword, semantic and combined search with category, file type and date filters, and the matching words highlighted." },
  { title: "Answers that show their sources", text: "The assistant answers only from documents you are allowed to see, and says so when the evidence is not there. Needs a local language model (Ollama)." },
  { title: "Numbers from real records", text: "Dashboards are built from what is actually stored, and each panel says whether it is measured, evaluated offline, or synthetic." },
  { title: "Roles and an audit trail", text: "Administrator, analyst and reviewer roles are enforced on the server. Sign-ins, uploads, reviews and denied requests are logged." },
];

const STEPS = [
  { title: "Upload", text: "Add files. Bad or duplicate files are refused with a clear reason." },
  { title: "Process", text: "Text is extracted, split into passages, indexed, classified and scanned for dates, amounts and emails." },
  { title: "Search and ask", text: "Look things up, or ask a question and get the passages the answer came from." },
  { title: "Review", text: "Reviewers confirm or correct uncertain categories; admins can see the audit log." },
];

const wrap = "mx-auto w-full max-w-7xl px-4 md:px-8";

function Section({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className={`${wrap} scroll-mt-20 py-16 md:py-24`}>
      <h2 className="text-3xl md:text-4xl">{title}</h2>
      {intro && <p className="mt-3 max-w-2xl text-base text-muted">{intro}</p>}
      <div className="mt-10">{children}</div>
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
      <header className="sticky top-0 z-10 border-b border-border bg-surface">
        <div className={`${wrap} flex h-14 items-center gap-4`}>
          <Link to="/" className="flex items-baseline gap-3">
            <span className="text-base font-medium tracking-tight">InfoMind AI</span>
            <span className="hidden text-xs text-muted sm:inline">Enterprise prototype</span>
          </Link>
          <nav aria-label="Site" className="ml-6 hidden gap-5 text-sm text-muted md:flex">
            <a href="#features" className="transition-colors duration-micro ease-out hover:text-fg">Features</a>
            <a href="#how-it-works" className="transition-colors duration-micro ease-out hover:text-fg">How it works</a>
            <a href="#about" className="transition-colors duration-micro ease-out hover:text-fg">About</a>
          </nav>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <button onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} className="rounded-md p-2 text-muted transition-colors duration-micro ease-out hover:bg-sunk hover:text-fg active:bg-bg">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <Link to="/login" className="rounded-md border border-transparent px-3 py-1.5 text-muted transition-colors duration-micro ease-out hover:bg-sunk hover:text-fg active:bg-bg">Sign in</Link>
            {canRegister && <Link to="/register" className="rounded-md border border-accent bg-accent px-3 py-1.5 font-medium text-accent-fg transition-colors duration-micro ease-out hover:bg-accent/90 active:bg-accent/80">Create account</Link>}
          </div>
        </div>
      </header>

      <main>
        <div className={`${wrap} grid gap-12 py-16 md:grid-cols-12 md:items-center md:gap-8 md:py-24`}>
          <div className="md:col-span-5">
            <h1 className="text-5xl md:text-6xl">Find answers in your documents</h1>
            <p className="mt-5 max-w-md text-lg text-fg-2">Every answer cites the passages it came from.</p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/login" className="inline-flex min-h-10 items-center rounded-md border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors duration-micro ease-out hover:bg-accent/90 active:bg-accent/80">Sign in</Link>
              {canRegister && <Link to="/register" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface px-4 py-2 text-sm font-medium transition-colors duration-micro ease-out hover:bg-sunk active:bg-bg">Create account</Link>}
              <a href="#how-it-works" className="link px-2 py-2 text-sm text-muted">See how it works</a>
            </div>
            {registrationClosed && <p className="mt-4 text-sm text-muted">New accounts on this site are created by an administrator.</p>}
          </div>

          <figure className="md:col-span-7" aria-label="Illustration of an answer with its source">
            <div className="panels">
              <div className="px-5 py-3 text-sm text-muted">Illustration, synthetic demo documents</div>
              <div className="px-5 py-4 text-base text-fg-2">How long are database backups retained?</div>
              <div className="px-5 py-6 text-xl leading-snug">
                Full database backups are retained for <strong className="measured text-xl font-medium text-cool">35 days</strong>.
              </div>
              <div className="bg-sunk px-5 py-4">
                <div className="text-sm text-muted">Source</div>
                <div className="measured mt-1 text-cool">backup_runbook.txt</div>
                <p className="measured mt-3 text-fg-2">“…Full backups of the inventory database run every night at 02:30 and are retained for 35 days.”</p>
              </div>
            </div>
            <figcaption className="mt-4 max-w-xl text-sm text-muted">Every answer carries the passages it came from. If the documents do not contain the answer, the assistant says so instead of guessing.</figcaption>
          </figure>
        </div>

        <Section id="features" title="What it does" intro="Everything below is implemented and covered by automated tests; see the project documentation for the details and the known limits.">
          <ul className="panels sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ title, text }) => (
              <li key={title} className="p-6">
                <h3 className="text-lg">{title}</h3>
                <p className="mt-2 text-base text-muted">{text}</p>
              </li>
            ))}
          </ul>
        </Section>

        <section id="how-it-works" className={`${wrap} scroll-mt-20 grid gap-10 py-16 md:grid-cols-12 md:py-24`}>
          <div className="md:col-span-4"><h2 className="text-3xl md:text-4xl">How it works</h2></div>
          <ol className="border-l border-border-strong md:col-span-8">
            {STEPS.map((s, i) => (
              <li key={s.title} className="relative pb-10 pl-8 last:pb-0">
                <span className="measured absolute -left-px top-0 -translate-x-1/2 bg-bg px-2 py-0.5 text-cool">{i + 1}</span>
                <h3 className="text-xl">{s.title}</h3>
                <p className="mt-2 max-w-xl text-base text-muted">{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <Section id="about" title="About this project">
          <div className="panels md:grid-cols-2">
            <div className="p-6">
              <h3 className="text-lg">Built with</h3>
              <p className="mt-2 text-base text-muted">React, TypeScript and Tailwind in the browser. FastAPI, SQLAlchemy and PostgreSQL on the server, Qdrant for vector search, scikit-learn for classification, and Ollama for local language models.</p>
            </div>
            <div className="p-6">
              <h3 className="text-lg text-accent">Please note</h3>
              <p className="mt-2 text-base text-muted">This is an educational, research-oriented prototype. Use synthetic or public data only. It is not certified or approved for classified, restricted, personal or operational use.</p>
            </div>
          </div>
        </Section>

        <section className="border-y border-border bg-sunk">
          <div className={`${wrap} flex flex-wrap items-center justify-between gap-6 py-12`}>
            <div>
              <h2 className="text-2xl">Ready to try it?</h2>
              <p className="mt-2 text-base text-muted">{canRegister ? "Sign in, or create an account to get started." : "Sign in with the account your administrator gave you."}</p>
            </div>
            <div className="flex gap-3">
              <Link to="/login" className="inline-flex min-h-10 items-center rounded-md border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors duration-micro ease-out hover:bg-accent/90 active:bg-accent/80">Sign in</Link>
              {canRegister && <Link to="/register" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface px-4 py-2 text-sm font-medium transition-colors duration-micro ease-out hover:bg-bg active:bg-sunk">Create account</Link>}
            </div>
          </div>
        </section>
      </main>

      <footer className="px-4 py-6 text-sm text-muted md:px-8">
        <div className="mx-auto max-w-7xl">InfoMind AI Enterprise is an educational prototype. Use synthetic or public data only.</div>
      </footer>
    </div>
  );
}
