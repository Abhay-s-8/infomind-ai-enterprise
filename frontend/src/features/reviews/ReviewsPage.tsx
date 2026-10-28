import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, Select, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/utils";
import type { ReviewItem } from "../../types";

function ReviewCard({ item, categories }: { item: ReviewItem; categories: string[] }) {
  const qc = useQueryClient();
  const [category, setCategory] = useState(item.predicted_category ?? "");
  const [note, setNote] = useState("");
  const submit = useMutation({
    mutationFn: (decision: "confirm" | "correct") => api.submitReview(item.document_id, { decision, category: decision === "correct" ? category : undefined, note }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
  const changed = category !== item.predicted_category;

  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <Link to={`/documents/${item.document_id}`} className="font-medium text-accent hover:underline">{item.filename}</Link>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>model {item.model_version}</span>
          <Badge tone="warn">predicted: {item.predicted_category} ({item.score?.toFixed(2)}{item.score_type === "decision_score" ? ", decision value" : ", uncalibrated"})</Badge>
          <span>{formatDate(item.created_at)}</span>
        </div>
      </div>
      <p className="mb-3 line-clamp-4 text-sm text-muted">{item.text_preview}</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm"><span className="mb-1 block text-muted">Final category</span>
          <Select aria-label={`Category for ${item.filename}`} value={category} onChange={(e) => setCategory(e.target.value)} className="min-w-[14rem]">
            {categories.map((c) => <option key={c}>{c}</option>)}
          </Select></label>
        <label className="min-w-[12rem] flex-1 text-sm"><span className="mb-1 block text-muted">Note (optional)</span><Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} /></label>
        {changed
          ? <Button loading={submit.isPending} onClick={() => submit.mutate("correct")}>Correct label</Button>
          : <Button loading={submit.isPending} onClick={() => submit.mutate("confirm")}>Confirm prediction</Button>}
      </div>
      {submit.isError && <div className="mt-3"><ErrorState error={submit.error} /></div>}
    </Card>
  );
}

export default function ReviewsPage() {
  const queue = useQuery({ queryKey: ["reviews"], queryFn: () => api.reviews(1) });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const categories = models.data?.find((m) => m.is_active)?.categories ?? [];
  const history = useQuery({ queryKey: ["review-history"], queryFn: api.reviewHistory });

  return (
    <>
      <PageHeader title="Review Queue" description="Low-confidence predictions awaiting a human decision. Your decision is stored separately from the machine prediction and never overwritten by the model." />
      {queue.isLoading ? <Spinner label="Loading review queue" /> : queue.error ? <ErrorState error={queue.error} onRetry={() => void queue.refetch()} /> :
        queue.data!.items.length === 0 ? <EmptyState title="Nothing to review">Predictions below the confidence threshold will appear here.</EmptyState> : (
          <div className="space-y-4">{queue.data!.items.map((i) => <ReviewCard key={i.document_id} item={i} categories={categories} />)}</div>
        )}
      {history.data && history.data.length > 0 && (
        <Card title="Recent decisions" className="mt-6">
          <ul className="space-y-1 text-sm">
            {history.data.slice(0, 10).map((h) => (
              <li key={h.id} className="flex flex-wrap gap-2"><span className="text-muted">{formatDate(h.created_at)}</span><Badge tone={h.decision === "confirm" ? "ok" : "warn"}>{h.decision}</Badge><span>{h.predicted ?? "—"} → {h.final}</span></li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
