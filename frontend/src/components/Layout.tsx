import { useQuery } from "@tanstack/react-query";
import {
  BarChart3, BotMessageSquare, ClipboardCheck, FileText, LayoutDashboard, LogOut, Menu, Moon, ScrollText, Search,
  Settings, Sun, Tags, X,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn } from "../lib/utils";
import type { Role } from "../types";

const NAV: { to: string; label: string; icon: typeof FileText; roles?: Role[] }[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard, roles: ["analyst"] },
  { to: "/documents", label: "Documents", icon: FileText, roles: ["analyst"] },
  { to: "/assistant", label: "AI Assistant", icon: BotMessageSquare, roles: ["analyst"] },
  { to: "/search", label: "Semantic Search", icon: Search, roles: ["analyst"] },
  { to: "/classification", label: "Classification", icon: Tags, roles: ["analyst"] },
  { to: "/analytics", label: "Analytics", icon: BarChart3, roles: ["analyst"] },
  { to: "/reviews", label: "Review Queue", icon: ClipboardCheck, roles: ["reviewer"] },
  { to: "/audit", label: "Audit Logs", icon: ScrollText, roles: [] },
  { to: "/settings", label: "Settings", icon: Settings },
];

function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try { return (localStorage.getItem("infomind.theme") as "dark" | "light") || "dark"; } catch { return "dark"; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("infomind.theme", theme); } catch { /* ignore */ }
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))] as const;
}

export default function Layout() {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const [theme, toggleTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const analystView = can("analyst");

  const status = useQuery({ queryKey: ["overview-status"], queryFn: () => api.overview(30), enabled: analystView, refetchInterval: 5000 });
  const pending = status.data?.totals.pending ?? 0;
  const ready = status.data?.system;

  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    if (q.trim()) navigate(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  const items = NAV.filter((n) => (n.roles === undefined ? true : n.roles.length === 0 ? can() : can(...n.roles)));

  return (
    <div className="flex min-h-full">
      <aside className={cn("fixed inset-y-0 left-0 z-30 w-60 shrink-0 border-r border-border bg-surface transition-transform md:static md:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          <div>
            <div className="text-sm font-semibold">InfoMind AI</div>
            <div className="text-[10px] uppercase tracking-widest text-muted">Enterprise · prototype</div>
          </div>
          <button className="md:hidden" aria-label="Close menu" onClick={() => setOpen(false)}><X className="h-5 w-5" /></button>
        </div>
        <nav aria-label="Primary" className="space-y-1 p-3">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
              className={({ isActive }) => cn("flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors", isActive ? "bg-accent/15 text-accent" : "text-muted hover:bg-raised hover:text-fg")}>
              <Icon className="h-4 w-4" aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      {open && <div className="fixed inset-0 z-20 bg-black/50 md:hidden" onClick={() => setOpen(false)} aria-hidden />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-border bg-surface/90 px-4 backdrop-blur">
          <button className="md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
          {analystView && (
            <form onSubmit={submitSearch} role="search" className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" aria-hidden />
              <input value={q} onChange={(e) => setQ(e.target.value)} aria-label="Global search" placeholder="Search documents…"
                className="w-full rounded-md border border-border bg-bg py-2 pl-9 pr-3 text-sm" />
            </form>
          )}
          <div className="ml-auto flex items-center gap-3 text-sm">
            {analystView && (
              <span className="hidden items-center gap-2 text-xs text-muted sm:flex" title="Documents currently being processed">
                <span className={cn("h-2 w-2 rounded-full", ready ? (ready.database.ok && ready.vector_store.ok ? "bg-ok" : "bg-danger") : "bg-muted")} aria-hidden />
                {ready ? (ready.database.ok && ready.vector_store.ok ? "System online" : "System degraded") : "Checking…"}
                {pending > 0 && <span className="rounded-full bg-warn/15 px-2 py-0.5 text-warn">{pending} processing</span>}
              </span>
            )}
            <button onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} className="rounded-md p-2 text-muted hover:bg-raised hover:text-fg">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <div className="hidden text-right leading-tight sm:block">
              <div className="text-xs">{user?.email}</div>
              <div className="text-[10px] uppercase tracking-wide text-muted">{user?.role}</div>
            </div>
            <button onClick={() => void logout()} aria-label="Log out" className="rounded-md p-2 text-muted hover:bg-raised hover:text-fg"><LogOut className="h-4 w-4" /></button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-6"><Outlet /></main>
        <footer className="border-t border-border px-6 py-3 text-xs text-muted">
          Educational prototype. Use synthetic or public data only. Not approved for classified or operational use.
        </footer>
      </div>
    </div>
  );
}
