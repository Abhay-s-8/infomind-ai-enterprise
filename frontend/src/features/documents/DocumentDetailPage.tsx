import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, RefreshCw, Tags, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, ErrorState, PageHeader, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatBytes, formatDate, STATUS_TONE } from "../../lib/utils";

export default function DocumentDetailPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { can } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const doc = useQuery({
    queryKey: ["document", id], queryFn: () => api.document(id),
    refetchInterval: (q) => (q.state.data && !["completed", "failed"].includes(q.state.data.status) ? 2000 : false),
  });
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["document", id] }); void qc.invalidateQueries({ queryKey: ["documents"] }); };
  const onError = (e: Error) => setActionError(e.message);
  const reprocess = useMutation({ mutationFn: () => api.reprocess(id), onSuccess: () => { setActionError(null); refresh(); }, onError });
  const reclassify = useMutation({ mutationFn: () => api.reclassify(id), onSuccess: () => { setActionError(null); refresh(); }, onError });
  const remove = useMutation({ mutationFn: () => api.deleteDocument(id), onSuccess: () => { void qc.invalidateQueries({ queryKey: ["documents"] }); navigate("/documents"); }, onError });
  const dropEntity = useMutation({ mutationFn: (eid: string) => api.removeEntity(id, eid), onSuccess: refresh, onError });
  const download = useMutation({ mutationFn: () => api.downloadDocument(id, doc.data!.filename), onError });

  if (doc.isLoading) return <Spinner label="Loading document" />;
  if (doc.error || !doc.data) return <ErrorState error={doc.error} onRetry={() => void doc.refetch()} />;
  const d = doc.data;
  const canMutate = can("analyst");
  const pred = d.prediction;

  return (
    <>
      <Link to="/documents" className="link mb-3 inline-flex items-center gap-1 text-sm text-muted"><ArrowLeft className="h-4 w-4" /> Documents</Link>
      <PageHeader title={d.filename} description={`ID ${d.id}`}
        action={canMutate && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => download.mutate()}><Download className="h-4 w-4" /> Download</Button>
            <Button variant="secondary" loading={reprocess.isPending} onClick={() => reprocess.mutate()}><RefreshCw className="h-4 w-4" /> Reprocess</Button>
            <Button variant="secondary" loading={reclassify.isPending} onClick={() => reclassify.mutate()}><Tags className="h-4 w-4" /> Reclassify</Button>
            {confirmDelete ? (
              <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>Confirm delete</Button>
            ) : (
              <Button variant="danger" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" /> Delete</Button>
            )}
          </div>
        )} />
      {actionError && <div className="mb-4"><ErrorState error={new Error(actionError)} /></div>}
      {d.deletion_state === "delete_failed" && <p role="alert" className="mb-4 rounded-md border border-danger/50 bg-danger-soft px-3 py-2 text-sm text-danger">A previous delete did not complete. Delete again to retry.</p>}
      {d.error_message && <p role="alert" className="mb-4 rounded-md border border-danger/50 bg-danger-soft px-3 py-2 text-sm text-danger">{d.error_message}</p>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Details" className="lg:col-span-1">
          <dl className="space-y-2 text-sm">
            {[
              ["Status", <Badge key="s" tone={STATUS_TONE[d.status] ?? "muted"}>{d.status}</Badge>],
              ["Type", `${d.extension.toUpperCase()}, ${d.mime_type}`], ["Size", formatBytes(d.size_bytes)],
              ["Uploaded", formatDate(d.created_at)], ["Pages", d.page_count ?? "not available for this format"],
              ["Chunks", d.chunk_count], ["Semantic index", d.indexed ? "indexed" : "not indexed"],
              ["SHA-256", <span key="h" className="measured break-all text-xs">{d.sha256}</span>],
            ].map(([k, v]) => <div key={String(k)} className="flex justify-between gap-3"><dt className="shrink-0 whitespace-nowrap text-muted">{k}</dt><dd className="text-right">{typeof v === "string" || typeof v === "number" ? <span className="measured">{v}</span> : v}</dd></div>)}
          </dl>
        </Card>

        <Card title="Classification" className="lg:col-span-2">
          {!pred ? <p className="text-sm text-muted">No prediction yet. An administrator can train a model on the Classification page; then use Reclassify.</p> : (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted">Machine prediction:</span><Badge tone="info">{pred.category}</Badge>
                <span className="measured text-xs text-muted">model {pred.model_version}</span>
                {pred.review_status === "needs_review" && <Badge tone="warn">needs review</Badge>}
              </div>
              <div className="flex items-center gap-2"><span className="text-muted">Human-verified:</span>{d.verified_category ? <Badge tone="ok">{d.verified_category}</Badge> : <span className="text-muted">not reviewed</span>}</div>
              <p className="text-xs text-muted">
                {pred.score_type === "probability_uncalibrated" ? "Scores are Logistic Regression probabilities and are not calibrated." : "Scores are SVM decision values, not probabilities."} Predicted {formatDate(pred.created_at)}.
              </p>
              <ul className="space-y-1">
                {Object.entries(pred.all_scores).sort((a, b) => b[1] - a[1]).map(([c, s]) => (
                  <li key={c} className="flex items-center gap-2">
                    <span className="w-48 truncate">{c}</span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded bg-sunk"><span className="block h-full bg-cool" style={{ width: `${Math.max(2, Math.min(100, pred.score_type === "probability_uncalibrated" ? s * 100 : (s + 1.5) * 33))}%` }} /></span>
                    <span className="measured w-16 text-right text-muted">{s.toFixed(3)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card title="Extracted entities" className="lg:col-span-1">
          {d.entities.length === 0 ? <p className="text-sm text-muted">No entities found. Extraction is heuristic and may miss items.</p> : (
            <ul className="space-y-1 text-sm">
              {d.entities.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-2">
                  <span><Badge tone="info">{e.label}</Badge> <span className="ml-1">{e.text}</span></span>
                  {can("reviewer") && <button className="rounded px-1.5 py-0.5 text-xs text-muted transition-colors duration-micro ease-out hover:bg-danger-soft hover:text-danger active:bg-danger/20" aria-label={`Remove entity ${e.text}`} onClick={() => dropEntity.mutate(e.id)}>remove</button>}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Processing history" className="lg:col-span-2">
          <ol className="space-y-1 text-sm">
            {d.events.map((e, i) => (
              <li key={i} className="flex gap-3"><span className="measured w-44 shrink-0 text-xs text-muted">{formatDate(e.created_at)}</span><Badge tone={STATUS_TONE[e.stage] ?? "muted"}>{e.stage}</Badge><span className="text-muted">{e.message}</span></li>
            ))}
          </ol>
        </Card>

        <Card title="Extracted text preview" className="lg:col-span-3">
          {d.text_preview ? <pre className="measured max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-sunk p-3 text-muted">{d.text_preview}</pre> : <p className="text-sm text-muted">No text extracted yet.</p>}
        </Card>
      </div>
    </>
  );
}
