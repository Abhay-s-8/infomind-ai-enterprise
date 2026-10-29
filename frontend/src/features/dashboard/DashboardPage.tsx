import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Select, SourceNote, Spinner, Stat } from "../../components/ui";
import { api } from "../../lib/api";
import { chart } from "../../lib/chart";
import { formatDate, pct, STATUS_TONE } from "../../lib/utils";
import { useState } from "react";

export default function DashboardPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["overview", days], queryFn: () => api.overview(days), refetchInterval: 8000 });

  if (isLoading) return <Spinner label="Loading overview" />;
  if (error || !data) return <ErrorState error={error} onRetry={() => void refetch()} />;

  const dist = Object.entries(data.classification_distribution).map(([name, value]) => ({ name, value }));
  const distMax = Math.max(1, ...dist.map((d) => d.value));
  const sys = data.system;
  const empty = data.totals.documents === 0;

  return (
    <>
      <PageHeader title="Overview" description="Live figures computed from your document records."
        action={
          <Select aria-label="Date range" value={days} onChange={(e) => setDays(Number(e.target.value))} className="!w-auto">
            <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
          </Select>
        } />
      {data.has_demo_data && <p className="mb-4 rounded-md border border-border bg-accent-soft px-3 py-2 text-sm text-accent">Your workspace contains synthetic demonstration documents (marked “demo”).</p>}

      <div className="panels grid-cols-2 lg:grid-cols-5">
        <Stat label="Total documents" value={data.totals.documents} />
        <Stat label="Processed" value={data.totals.completed} tone="ok" />
        <Stat label="Awaiting processing" value={data.totals.pending} tone={data.totals.pending ? "warn" : undefined} />
        <Stat label="Failed" value={data.totals.failed} tone={data.totals.failed ? "danger" : undefined} />
        <div className="col-span-2 lg:col-span-1"><Stat label="Success rate" value={pct(data.processing_success_rate)} hint="completed / (completed + failed)" /></div>
      </div>

      {empty ? (
        <div className="mt-6">
          <EmptyState title="No documents yet" action={<Link to="/documents" className="link">Upload your first document</Link>}>
            Upload PDF, DOCX, TXT, CSV or XLSX files. Admins can load synthetic demo data with <code className="measured">python -m app.cli seed-demo</code>.
          </EmptyState>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Card title="Classification distribution" action={<SourceNote kind="measured" />}>
            {dist.length === 0 ? (
              <div>
                <p className="font-medium">No classified documents</p>
                <p className="mt-1 text-sm text-muted">Train a model on the Classification page, then reclassify documents.</p>
              </div>
            ) : (
              <ul className="space-y-4">
                {dist.map((d) => (
                  <li key={d.name}>
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <span>{d.name}</span>
                      <span className="measured text-muted">{d.value}</span>
                    </div>
                    <div className="mt-1.5 h-1.5 rounded-sm bg-sunk" aria-hidden>
                      <div className="h-full rounded-sm bg-cool" style={{ width: `${(d.value / distMax) * 100}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Documents by status" action={<SourceNote kind="measured" />}>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={Object.entries(data.by_status).map(([name, value]) => ({ name, value }))}>
                  <CartesianGrid stroke={chart.grid} vertical={false} />
                  <XAxis dataKey="name" stroke={chart.axis} fontSize={12} />
                  <YAxis allowDecimals={false} stroke={chart.axis} fontSize={12} />
                  <Tooltip contentStyle={chart.tooltip} cursor={{ fill: chart.grid, fillOpacity: 0.4 }} />
                  <Bar dataKey="value" fill={chart.series} radius={[2, 2, 0, 0]} maxBarSize={24} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card title="Recent uploads">
          {data.recent_uploads.length === 0 ? <p className="text-sm text-muted">Nothing uploaded yet.</p> : (
            <ul className="space-y-3 text-sm">
              {data.recent_uploads.map((u) => (
                <li key={u.id} className="flex items-center justify-between gap-2">
                  <Link to={`/documents/${u.id}`} className="link truncate">{u.filename}</Link>
                  <Badge tone={STATUS_TONE[u.status] ?? "muted"}>{u.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent searches">
          {data.recent_searches.length === 0 ? <p className="text-sm text-muted">No searches yet.</p> : (
            <ul className="space-y-3 text-sm">
              {data.recent_searches.map((s, i) => (
                <li key={i} className="flex items-baseline justify-between gap-3">
                  <Link to={`/search?q=${encodeURIComponent(s.query)}`} className="link truncate">{s.query}</Link>
                  <span className="flex shrink-0 gap-3 text-xs text-muted"><span>{s.mode}</span><span className="measured">{s.results}</span></span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent AI questions">
          {data.recent_questions.length === 0 ? <p className="text-sm text-muted">No questions asked yet.</p> : (
            <ul className="space-y-3 text-sm">
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
        {!sys.llm_available && <p className="mt-3 text-sm text-muted">The AI assistant is disabled until Ollama is running with the configured model. Everything else keeps working.</p>}
      </Card>
    </>
  );
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return <Badge tone={ok ? "ok" : "danger"}>{label}: {ok ? "available" : "unavailable"}</Badge>;
}
