import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SourceNote, Spinner, Table } from "../../components/ui";
import { ConfusionMatrix } from "../../components/ConfusionMatrix";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDate, pct } from "../../lib/utils";

export default function ClassificationPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [text, setText] = useState("");
  const metrics = useQuery({ queryKey: ["cls-metrics"], queryFn: api.metrics, retry: false });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const train = useMutation({
    mutationFn: api.train,
    onSuccess: () => { setTimeout(() => { void qc.invalidateQueries({ queryKey: ["cls-metrics"] }); void qc.invalidateQueries({ queryKey: ["models"] }); }, 3000); },
  });
  const predict = useMutation({ mutationFn: () => api.predict(text) });

  const noModel = metrics.error instanceof ApiError && metrics.error.status === 404;
  const m = metrics.data;

  return (
    <>
      <PageHeader title="Classification" description="TF-IDF + Logistic Regression vs Linear SVM. Metrics come from a held-out test split."
        action={user?.role === "admin" && <Button loading={train.isPending} onClick={() => train.mutate()}>Train on synthetic data</Button>} />
      {train.isSuccess && <p role="status" className="mb-4 text-sm text-ok">{train.data.message}</p>}
      {train.isError && <div className="mb-4"><ErrorState error={train.error} /></div>}

      {metrics.isLoading ? <Spinner label="Loading model metrics" /> : noModel ? (
        <EmptyState title="No trained model yet">{user?.role === "admin" ? "Use “Train on synthetic data” to create the first model." : "Ask an administrator to train a model."}</EmptyState>
      ) : metrics.error || !m || !m.metrics || !m.comparison ? <ErrorState error={metrics.error} onRetry={() => void metrics.refetch()} /> : (
        <div className="space-y-4">
          <Card title="Active model" action={<SourceNote kind={m.dataset_info.name === "synthetic" ? "synthetic" : "offline"} />}>
            <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-muted">Version</dt><dd className="break-all font-mono text-xs">{m.version}</dd></div>
              <div><dt className="text-muted">Algorithm</dt><dd>{m.algorithm}</dd></div>
              <div><dt className="text-muted">Trained</dt><dd>{formatDate(m.dataset_info.trained_at)}</dd></div>
              <div><dt className="text-muted">Score type</dt><dd>{m.score_type === "probability_uncalibrated" ? "probability (uncalibrated)" : "decision value (not a probability)"}</dd></div>
              <div><dt className="text-muted">Dataset</dt><dd>{m.dataset_info.name}: {m.dataset_info.total} examples</dd></div>
              <div><dt className="text-muted">Split</dt><dd>{m.dataset_info.train} train / {m.dataset_info.validation} val / {m.dataset_info.test} test</dd></div>
              <div><dt className="text-muted">Selection</dt><dd>{m.dataset_info.selection_criterion}</dd></div>
              <div><dt className="text-muted">Evaluated on</dt><dd>{m.dataset_info.evaluation_split} · n={m.metrics.n_evaluated}</dd></div>
            </dl>
            {m.dataset_info.caveat && <p className="mt-3 rounded-md bg-warn/10 px-3 py-2 text-xs text-warn">{m.dataset_info.caveat}</p>}
          </Card>

          <Card title="Model comparison (held-out test split)">
            <Table head={["Model", "Accuracy", "Macro precision", "Macro recall", "Macro F1", "Weighted F1", "n"]}>
              {Object.entries(m.comparison).map(([name, c]) => (
                <tr key={name}>
                  <td className="px-3 py-2">{name}{name === m.algorithm && <span className="ml-2"><Badge tone="ok">selected</Badge></span>}</td>
                  <td className="px-3 py-2 tabular-nums">{pct(c.test.accuracy)}</td><td className="px-3 py-2 tabular-nums">{pct(c.test.macro_precision)}</td>
                  <td className="px-3 py-2 tabular-nums">{pct(c.test.macro_recall)}</td><td className="px-3 py-2 tabular-nums">{pct(c.test.macro_f1)}</td>
                  <td className="px-3 py-2 tabular-nums">{pct(c.test.weighted_f1)}</td><td className="px-3 py-2 tabular-nums">{c.test.n_evaluated}</td>
                </tr>
              ))}
            </Table>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Per-class metrics">
              <Table head={["Class", "Precision", "Recall", "F1", "Support"]}>
                {Object.entries(m.metrics.per_class).map(([c, v]) => (
                  <tr key={c}><td className="px-3 py-2">{c}</td><td className="px-3 py-2 tabular-nums">{v.precision.toFixed(2)}</td><td className="px-3 py-2 tabular-nums">{v.recall.toFixed(2)}</td><td className="px-3 py-2 tabular-nums">{v.f1.toFixed(2)}</td><td className="px-3 py-2 tabular-nums">{v.support}</td></tr>
                ))}
              </Table>
            </Card>
            <Card title="Confusion matrix"><ConfusionMatrix labels={m.metrics.confusion_matrix.labels} matrix={m.metrics.confusion_matrix.matrix} /></Card>
          </div>
        </div>
      )}

      <Card title="Try the classifier" className="mt-4">
        <textarea aria-label="Text to classify" value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={50000}
          placeholder="Paste text to classify…" className="w-full rounded-md border border-border bg-bg p-3 text-sm" />
        <div className="mt-3 flex items-center gap-3">
          <Button variant="secondary" disabled={!text.trim() || noModel} loading={predict.isPending} onClick={() => predict.mutate()}>Classify</Button>
          {predict.data && (
            <span className="text-sm">
              <Badge tone="accent">{predict.data.category}</Badge> <span className="text-muted">score {predict.data.score.toFixed(3)} ({predict.data.score_type === "decision_score" ? "decision value" : "uncalibrated probability"})</span>
              {predict.data.low_confidence && <span className="ml-2"><Badge tone="warn">low confidence</Badge></span>}
            </span>
          )}
        </div>
        {predict.isError && <div className="mt-3"><ErrorState error={predict.error} /></div>}
      </Card>

      {models.data && models.data.length > 1 && (
        <Card title="Model history" className="mt-4">
          <Table head={["Version", "Algorithm", "Macro F1", "Created", "Active"]}>
            {models.data.map((v) => <tr key={v.id}><td className="px-3 py-2 font-mono text-xs">{v.version}</td><td className="px-3 py-2">{v.algorithm}</td><td className="px-3 py-2 tabular-nums">{pct(v.headline.macro_f1)}</td><td className="px-3 py-2">{formatDate(v.created_at)}</td><td className="px-3 py-2">{v.is_active ? "yes" : ""}</td></tr>)}
          </Table>
        </Card>
      )}
    </>
  );
}
