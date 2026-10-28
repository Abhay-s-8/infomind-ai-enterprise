import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, EmptyState, ErrorState, PageHeader, SourceNote, Spinner, Stat, Table } from "../../components/ui";
import { api } from "../../lib/api";
import { pct } from "../../lib/utils";

const tip = { background: "#1e222a", border: "1px solid #2c313b", color: "#e8eaee" };

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const docs = useQuery({ queryKey: ["an-docs", days], queryFn: () => api.docAnalytics(days) });
  const cls = useQuery({ queryKey: ["an-cls"], queryFn: api.classAnalytics });
  const srch = useQuery({ queryKey: ["an-search", days], queryFn: () => api.searchAnalytics(days) });
  const sys = useQuery({ queryKey: ["system-models"], queryFn: api.systemModels });

  if (docs.isLoading || cls.isLoading || srch.isLoading) return <Spinner label="Loading analytics" />;
  if (docs.error || cls.error || srch.error || !docs.data || !cls.data || !srch.data) return <ErrorState error={docs.error ?? cls.error ?? srch.error} onRetry={() => { void docs.refetch(); void cls.refetch(); void srch.refetch(); }} />;
  const d = docs.data, c = cls.data, s = srch.data;

  return (
    <>
      <PageHeader title="Analytics" description="Each panel is labelled as measured application data, offline evaluation, or synthetic."
        action={<select aria-label="Date range" value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-md border border-border bg-bg px-3 py-2 text-sm"><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select>} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Pending reviews" value={c.pending_reviews} tone={c.pending_reviews ? "warn" : undefined} />
        <Stat label="Avg processing time" value={d.avg_processing_ms === null ? "n/a" : `${(d.avg_processing_ms / 1000).toFixed(1)} s`} hint={`${d.processing_jobs_measured} jobs measured`} />
        <Stat label="LLM" value={sys.data?.llm.available ? "available" : "unavailable"} tone={sys.data?.llm.available ? "ok" : "danger"} hint={sys.data?.llm.model} />
        <Stat label="Embeddings" value={sys.data?.embedding.available ? "available" : "unavailable"} tone={sys.data?.embedding.available ? "ok" : "danger"} hint={sys.data ? `${sys.data.embedding.provider}: ${sys.data.embedding.model}` : undefined} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title="Documents uploaded over time" action={<SourceNote kind="measured" />}>
          {d.uploads_over_time.length === 0 ? <EmptyState title="No uploads in this period" /> : (
            <div className="h-60"><ResponsiveContainer width="100%" height="100%"><LineChart data={d.uploads_over_time}>
              <CartesianGrid stroke="#2c313b" vertical={false} /><XAxis dataKey="date" stroke="#8e96a3" fontSize={12} /><YAxis allowDecimals={false} stroke="#8e96a3" fontSize={12} />
              <Tooltip contentStyle={tip} /><Line dataKey="count" stroke="#6398ff" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>
          )}
        </Card>
        <Card title="Documents by file type" action={<SourceNote kind="measured" />}>
          {d.by_file_type.length === 0 ? <EmptyState title="No documents yet" /> : (
            <div className="h-60"><ResponsiveContainer width="100%" height="100%"><BarChart data={d.by_file_type}>
              <CartesianGrid stroke="#2c313b" vertical={false} /><XAxis dataKey="type" stroke="#8e96a3" fontSize={12} /><YAxis allowDecimals={false} stroke="#8e96a3" fontSize={12} />
              <Tooltip contentStyle={tip} /><Bar dataKey="count" fill="#4ac98a" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
          )}
        </Card>
        <Card title="Documents by category" action={<SourceNote kind="measured" />}>
          {d.by_category.length === 0 ? <EmptyState title="No classified documents" /> : (
            <div className="h-60"><ResponsiveContainer width="100%" height="100%"><BarChart data={d.by_category} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid stroke="#2c313b" horizontal={false} /><XAxis type="number" allowDecimals={false} stroke="#8e96a3" fontSize={12} /><YAxis type="category" dataKey="category" width={150} stroke="#8e96a3" fontSize={11} />
              <Tooltip contentStyle={tip} /><Bar dataKey="count" fill="#a78bfa" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer></div>
          )}
        </Card>
        <Card title="Searches per day" action={<SourceNote kind="measured" />}>
          {s.searches_per_day.length === 0 ? <EmptyState title="No searches in this period" /> : (
            <div className="h-60"><ResponsiveContainer width="100%" height="100%"><LineChart data={s.searches_per_day}>
              <CartesianGrid stroke="#2c313b" vertical={false} /><XAxis dataKey="date" stroke="#8e96a3" fontSize={12} /><YAxis allowDecimals={false} stroke="#8e96a3" fontSize={12} />
              <Tooltip contentStyle={tip} /><Line dataKey="count" stroke="#ebb146" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>
          )}
          {s.by_mode.length > 0 && <Table head={["Mode", "Searches", "Avg latency"]}>{s.by_mode.map((m) => <tr key={m.mode}><td className="px-3 py-2">{m.mode}</td><td className="px-3 py-2 tabular-nums">{m.count}</td><td className="px-3 py-2 tabular-nums">{m.avg_latency_ms ?? "n/a"} ms</td></tr>)}</Table>}
        </Card>

        <Card title="Classification model comparison" action={<SourceNote kind={c.model?.synthetic_data ? "synthetic" : "offline"} />}>
          {!c.model ? <EmptyState title="No trained model">Train one on the Classification page.</EmptyState> : (
            <>
              <Table head={["Model", "Accuracy", "Macro F1", "Weighted F1"]}>
                {Object.entries(c.model.comparison).map(([k, v]) => <tr key={k}><td className="px-3 py-2">{k}{k === c.model!.algorithm ? " ✓" : ""}</td><td className="px-3 py-2 tabular-nums">{pct(v.accuracy)}</td><td className="px-3 py-2 tabular-nums">{pct(v.macro_f1)}</td><td className="px-3 py-2 tabular-nums">{pct(v.weighted_f1)}</td></tr>)}
              </Table>
              <p className="mt-2 text-xs text-muted">Trained on {c.model.dataset_size} examples; held-out test split.</p>
            </>
          )}
        </Card>
        <Card title="Per-class F1 (active model)" action={<SourceNote kind={c.model?.synthetic_data ? "synthetic" : "offline"} />}>
          {!c.model ? <EmptyState title="No trained model" /> : (
            <div className="h-60"><ResponsiveContainer width="100%" height="100%"><BarChart data={Object.entries(c.model.per_class_f1).map(([name, f1]) => ({ name, f1 }))} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid stroke="#2c313b" horizontal={false} /><XAxis type="number" domain={[0, 1]} stroke="#8e96a3" fontSize={12} /><YAxis type="category" dataKey="name" width={150} stroke="#8e96a3" fontSize={11} />
              <Tooltip contentStyle={tip} formatter={(v: number) => v.toFixed(3)} /><Bar dataKey="f1" fill="#6398ff" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer></div>
          )}
        </Card>

        <Card title="Retrieval evaluation (keyword vs semantic vs hybrid)" className="lg:col-span-2" action={<SourceNote kind="synthetic" />}>
          {!s.retrieval_evaluation ? (
            <EmptyState title="No retrieval evaluation has been run">Run <code>python -m app.cli evaluate</code> after seeding demo data.</EmptyState>
          ) : (
            <>
              <Table head={["Mode", ...Object.keys(Object.values(s.retrieval_evaluation.metrics)[0])]}>
                {Object.entries(s.retrieval_evaluation.metrics).map(([mode, m]) => <tr key={mode}><td className="px-3 py-2">{mode}</td>{Object.values(m).map((v, i) => <td key={i} className="px-3 py-2 tabular-nums">{v.toFixed(3)}</td>)}</tr>)}
              </Table>
              <p className="mt-2 text-xs text-muted">{s.retrieval_evaluation.n_queries} labelled queries over: {s.retrieval_evaluation.corpus}. Labels are author-assigned on an easy synthetic corpus; treat as a methodology demonstration.</p>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
