import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, Select, Spinner, Table } from "../../components/ui";
import { api } from "../../lib/api";
import { ALLOWED_EXTENSIONS, formatBytes, formatDate, MAX_UPLOAD_MB, STATUS_TONE, validateFile } from "../../lib/utils";

export default function DocumentsPage() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [fileType, setFileType] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [messages, setMessages] = useState<{ tone: "ok" | "danger" | "warn"; text: string }[]>([]);
  const [dragging, setDragging] = useState(false);

  const list = useQuery({
    queryKey: ["documents", page, q, status, fileType],
    queryFn: () => api.documents({ page, page_size: 15, q, status, file_type: fileType }),
    refetchInterval: (query) => (query.state.data?.items.some((d) => !["completed", "failed"].includes(d.status)) ? 2500 : false),
  });

  const upload = useMutation({
    mutationFn: (files: File[]) => api.upload(files, setProgress),
    onSuccess: (res) => {
      const msgs: { tone: "ok" | "danger" | "warn"; text: string }[] = res.results.map((r) => ({ tone: r.duplicate ? "warn" : "ok", text: r.duplicate ? `${r.document.filename}: duplicate of an existing document` : `${r.document.filename}: uploaded, processing started` }));
      res.errors.forEach((e) => msgs.push({ tone: "danger", text: `${e.filename}: ${e.error}` }));
      setMessages(msgs);
      void qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e: Error) => setMessages([{ tone: "danger", text: e.message }]),
    onSettled: () => setProgress(null),
  });

  const handleFiles = (files: FileList | File[]) => {
    const picked = Array.from(files);
    const rejected: typeof messages = [];
    const ok: File[] = [];
    picked.forEach((f) => {
      const err = validateFile(f);
      err ? rejected.push({ tone: "danger", text: `${f.name}: ${err}` }) : ok.push(f);
    });
    setMessages(rejected);
    if (ok.length) upload.mutate(ok);
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); };

  const totalPages = list.data ? Math.max(1, Math.ceil(list.data.total / list.data.page_size)) : 1;

  return (
    <>
      <PageHeader title="Documents" description={`Upload ${ALLOWED_EXTENSIONS.join(", ").toUpperCase()} files (max ${MAX_UPLOAD_MB} MB each). Files are validated, de-duplicated, indexed and classified.`} />

      <div onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
        className={`mb-4 flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${dragging ? "border-accent bg-accent/5" : "border-border"}`}>
        <UploadCloud className="h-6 w-6 text-muted" aria-hidden />
        <p className="text-sm">Drag files here or</p>
        <input ref={inputRef} type="file" multiple hidden data-testid="file-input" aria-label="Choose files"
          accept={ALLOWED_EXTENSIONS.map((e) => `.${e}`).join(",")}
          onChange={(e) => { if (e.target.files) handleFiles(e.target.files); e.target.value = ""; }} />
        <Button variant="secondary" onClick={() => inputRef.current?.click()} loading={upload.isPending}>Choose files</Button>
        {progress !== null && (
          <div className="w-full max-w-xs" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-1.5 overflow-hidden rounded bg-raised"><div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} /></div>
            <p className="mt-1 text-xs text-muted">{progress}% uploaded</p>
          </div>
        )}
      </div>

      {messages.length > 0 && (
        <ul className="mb-4 space-y-1" aria-live="polite">
          {messages.map((m, i) => <li key={i} className={`text-sm ${m.tone === "ok" ? "text-ok" : m.tone === "warn" ? "text-warn" : "text-danger"}`}>{m.text}</li>)}
        </ul>
      )}

      <Card>
        <div className="mb-4 flex flex-wrap gap-3">
          <Input aria-label="Filter by filename" placeholder="Filter by filename" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} className="max-w-xs" />
          <Select aria-label="Status filter" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="max-w-[10rem]">
            <option value="">All statuses</option>
            {["queued", "extracting", "chunking", "embedding", "classifying", "indexed", "completed", "failed"].map((s) => <option key={s}>{s}</option>)}
          </Select>
          <Select aria-label="File type filter" value={fileType} onChange={(e) => { setFileType(e.target.value); setPage(1); }} className="max-w-[9rem]">
            <option value="">All types</option>
            {ALLOWED_EXTENSIONS.map((t) => <option key={t}>{t}</option>)}
          </Select>
        </div>
        {list.isLoading ? <Spinner label="Loading documents" /> : list.error ? <ErrorState error={list.error} onRetry={() => void list.refetch()} /> :
          list.data!.items.length === 0 ? <EmptyState title="No documents found">Upload a file above, or adjust the filters.</EmptyState> : (
            <>
              <Table head={["Name", "Type", "Size", "Status", "Category", "Uploaded"]}>
                {list.data!.items.map((d) => (
                  <tr key={d.id}>
                    <td className="px-3 py-2"><Link to={`/documents/${d.id}`} className="text-accent hover:underline">{d.filename}</Link>{d.is_demo && <span className="ml-2"><Badge tone="warn">demo</Badge></span>}</td>
                    <td className="px-3 py-2 uppercase text-muted">{d.extension}</td>
                    <td className="px-3 py-2 tabular-nums text-muted">{formatBytes(d.size_bytes)}</td>
                    <td className="px-3 py-2"><Badge tone={STATUS_TONE[d.status] ?? "muted"}>{d.status}</Badge></td>
                    <td className="px-3 py-2">{d.category ?? <span className="text-muted">—</span>}{d.verified_category && <span className="ml-1 text-xs text-ok" title="Human verified">✓</span>}</td>
                    <td className="px-3 py-2 text-muted">{formatDate(d.created_at)}</td>
                  </tr>
                ))}
              </Table>
              <div className="mt-4 flex items-center justify-between text-sm text-muted">
                <span>{list.data!.total} documents</span>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                  <span>Page {page} of {totalPages}</span>
                  <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
                </div>
              </div>
            </>
          )}
      </Card>
    </>
  );
}
