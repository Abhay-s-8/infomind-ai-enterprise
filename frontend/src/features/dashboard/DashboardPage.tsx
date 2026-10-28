import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, EmptyState, ErrorState, PageHeader, SourceNote, Spinner, Stat } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate, pct, STATUS_TONE } from "../../lib/utils";
import { useState } from "react";

export const CHART_COLORS = ["#6398ff", "#4ac98a", "#ebb146", "#f05f5f", "#a78bfa", "#38bdf8", "#f472b6"];

export default function DashboardPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["overview", days], queryFn: () => api.overview(days), refetchInterval: 8000 });

  if (isLoading) return <Spinner label="Loading overview" />;
  if (error || !data) return <ErrorState error={error} onRetry={() => void refetch()} />;

  const dist = Object.entries(data.classification_distribution).map(([name, value]) => ({ name, value }));
  const sys = data.system;
  const empty = data.totals.documents === 0;

  return (
    <>
      <PageHeader title="Overview" description="Live figures computed from your document records."
        action={
          <select aria-label="Date range" value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-md border border-border bg-bg px-3 py-2 text-sm">
            <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
          </select>
        } />
      {data.has_demo_data && <p className="mb-4 rounded-md bg-warn/10 px-3 py-2 text-sm text-warn">Your workspace contains synthetic demonstration documents (marked “demo”).</p>}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat label="Total documents" value={data.totals.documents} />
        <Stat label="Processed" value={data.totals.completed} tone="ok" />
        <Stat label="Awaiting processing" value={data.totals.pending} tone={data.totals.pending ? "warn" : undefined} />
        <Stat label="Failed" value={data.totals.failed} tone={data.totals.failed ? "danger" : undefined} />
        <Stat label="Success rate" value={pct(data.processing_success_rate)} hint="completed / (completed + failed)" />
      </div>

      {empty ? (
        <div className="mt-6">
          <EmptyState title="No documents yet" action={<Link to="/documents" className="text-accent underline">Upload your first document</Link>}>
            Upload PDF, DOCX, TXT, CSV or XLSX files. Admins can load synthetic demo data with <code>python -m app.cli seed-demo</code>.
          </EmptyState>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Card title="Classification distribution" action={<SourceNote kind="measured" />}>
            {dist.length === 0 ? <EmptyState title="No classified documents">Train a model on the Classification page, then reclassify documents.</EmptyState> : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={dist} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                      {dist.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: "#1e222a", border: "1px solid #2c313b", color: "#e8eaee" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            <ul className="mt-2 space-y-1 text-sm">
              {dist.map((d, i) => (
                <li key={d.name} className="flex items-center justify-between">
                  <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />{d.name}</span>
                  <span className="tabular-nums text-muted">{d.value}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Documents by status" action={<SourceNote kind="measured" />}>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={Object.entries(data.by_status).map(([name, value]) => ({ name, value }))}>
                  <CartesianGrid stroke="#2c313b" vertical={false} />
                  <XAxis dataKey="name" stroke="#8e96a3" fontSize={12} />
                  <YAxis allowDecimals={false} stroke="#8e96a3" fontSize={12} />
                  <Tooltip contentStyle={{ background: "#1e222a", border: "1px solid #2c313b", color: "#e8eaee" }} />
                  <Bar dataKey="value" fill="#6398ff" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card title="Recent uploads">
          {data.recent_uploads.length === 0 ? <p className="text-sm text-muted">Nothing uploaded yet.</p> : (
            <ul className="space-y-2 text-sm">
              {data.recent_uploads.map((u) => (
                <li key={u.id} className="flex items-center justify-between gap-2">
                  <Link to={`/documents/${u.id}`} className="truncate text-accent hover:underline">{u.filename}</Link>
                  <Badge tone={STATUS_TONE[u.status] ?? "muted"}>{u.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent searches">
          {data.recent_searches.length === 0 ? <p className="text-sm text-muted">No searches yet.</p> : (
            <ul className="space-y-2 text-sm">
              {data.recent_searches.map((s, i) => (
                <li key={i} className="flex justify-between gap-2"><Link to={`/search?q=${encodeURIComponent(s.query)}`} className="truncate hover:underline">{s.query}</Link>
                  <span className="shrink-0 text-xs text-muted">{s.mode} · {s.results}</span></li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent AI questions">
          {data.recent_questions.length === 0 ? <p className="text-sm text-muted">No questions asked yet.</p> : (
            <ul className="space-y-2 text-sm">
              {data.recent_questions.map((q, i) => <li key={i} title={formatDate(q.created_at)} className="truncate">{q.question}</li>)}
            </ul>
          )}
        </Card>
      </div>

      <Card title="System status" className="mt-6">
        <div className="flex flex-wrap gap-3 text-sm">
          <StatusPill ok={sys.database.ok} label="Database" />
          <StatusPill ok={sys.vector_store.ok} label="Vector store (Qdrant)" />
          <StatusPill ok={sys.ollama.ok} label="Ollama" />
          <StatusPill ok={sys.llm_available} label="Language model" />
          <StatusPill ok={sys.embedding_available} label="Embedding model" />
        </div>
        {!sys.llm_available && <p className="mt-3 text-xs text-muted">The AI assistant is disabled until Ollama is running with the configured model. Everything else keeps working.</p>}
      </Card>
    </>
  );
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return <Badge tone={ok ? "ok" : "danger"}>{label}: {ok ? "available" : "unavailable"}</Badge>;
}
