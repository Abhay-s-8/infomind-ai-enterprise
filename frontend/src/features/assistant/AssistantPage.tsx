import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, FileText, Plus, SendHorizonal, Square, ThumbsDown, ThumbsUp, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import type { ChatResponse, Citation, Message } from "../../types";

function SourceList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div>
      <div className="mb-2 text-sm text-muted">Sources</div>
      <ul className="space-y-3">
        {citations.map((c) => (
          <li key={c.chunk_id} className="border-l-2 border-cool pl-3">
            <Link to={`/documents/${c.document_id}`} className="measured inline-flex items-center gap-1.5 text-cool underline decoration-border-strong underline-offset-4 transition-colors duration-micro ease-out hover:decoration-cool"><FileText className="h-3.5 w-3.5" aria-hidden />{c.filename}<span className="sr-only"> · </span>{c.page ? `page ${c.page}` : "page unavailable"}</Link>
            <p className="measured mt-1 text-fg-2">{c.excerpt}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AssistantPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const [meta, setMeta] = useState<Pick<ChatResponse, "retrieval_mode" | "excluded_suspicious" | "inference"> | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  // Provisional answer text while the model is still writing; replaced by the saved, validated message on completion.
  const [live, setLive] = useState<{ text: string; citations: Citation[] } | null>(null);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const status = useQuery({ queryKey: ["system-models"], queryFn: api.systemModels, refetchInterval: 15000 });
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: api.conversations });
  const thread = useQuery({ queryKey: ["conversation", activeId], queryFn: () => api.conversation(activeId!), enabled: !!activeId });

  const ask = useMutation({
    mutationFn: async ({ q, id }: { q: string; id: string | null }) => {
      const controller = new AbortController();
      abort.current = controller;
      const result: { done?: ChatResponse } = {};
      await api.chatStream(q, id ?? undefined, (e) => {
        if (e.type === "citations") setLive({ text: "", citations: e.data });
        else if (e.type === "delta") setLive((l) => ({ citations: l?.citations ?? [], text: (l?.text ?? "") + e.data.text }));
        else if (e.type === "done") result.done = e.data;
      }, controller.signal);
      return result.done!; // chatStream rejects unless a `done` event arrived
    },
    onSuccess: async (res) => {
      setActiveId(res.conversation_id);
      setMeta({ retrieval_mode: res.retrieval_mode, excluded_suspicious: res.excluded_suspicious, inference: res.inference });
      // wait for the saved message so the streamed bubble is replaced by it without a flash of empty thread
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["conversations"] }),
        qc.invalidateQueries({ queryKey: ["conversation", res.conversation_id] }),
      ]);
    },
    onSettled: () => { setPending(null); setLive(null); abort.current = null; },
  });
  const stopped = ask.error instanceof DOMException && ask.error.name === "AbortError";
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteConversation(id),
    onSuccess: (_, id) => { if (id === activeId) setActiveId(null); void qc.invalidateQueries({ queryKey: ["conversations"] }); },
  });
  const rate = useMutation({ mutationFn: ({ id, v }: { id: string; v: "up" | "down" }) => api.feedback(id, v), onSuccess: () => void qc.invalidateQueries({ queryKey: ["conversation", activeId] }) });

  useEffect(() => { bottom.current?.scrollIntoView?.({ behavior: "smooth" }); }, [thread.data, pending, live?.text]);
  useEffect(() => () => abort.current?.abort(), []);

  const send = (q: string) => {
    if (!q.trim() || ask.isPending) return;
    setLastQuestion(q);
    setPending(q);
    setInput("");
    setMeta(null);
    ask.mutate({ q, id: activeId });
  };
  const submit = (e: FormEvent) => { e.preventDefault(); send(input); };
  const copy = async (m: Message) => {
    try { await navigator.clipboard.writeText(m.content); setCopied(m.id); setTimeout(() => setCopied(null), 1500); } catch { /* clipboard unavailable */ }
  };

  const llmDown = status.data && !status.data.llm.available;

  return (
    <>
      <PageHeader title="AI Assistant" description="Answers are grounded in your authorized documents and cite their sources. Each question is answered independently." />
      {llmDown && (
        <p role="alert" className="mb-4 rounded-md border border-border bg-accent-soft px-3 py-2 text-sm text-accent">
          The language model <code className="measured">{status.data!.llm.model}</code> is not available (is Ollama running and the model pulled?). Questions will fail until it is; search and the rest of the app still work.
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
        <aside aria-label="Conversations" className="self-start rounded-lg border border-border bg-surface p-3">
          <Button variant="secondary" className="mb-3 w-full" onClick={() => { setActiveId(null); setMeta(null); }}><Plus className="h-4 w-4" /> New conversation</Button>
          {conversations.isLoading ? <Spinner /> : conversations.data?.length === 0 ? <p className="text-sm text-muted">No conversations yet.</p> : (
            <ul className="space-y-1">
              {conversations.data?.map((c) => (
                <li key={c.id} className={`group flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors duration-micro ease-out ${c.id === activeId ? "bg-accent-soft text-accent" : "hover:bg-sunk"}`}>
                  <button className="min-w-0 flex-1 truncate text-left" onClick={() => { setActiveId(c.id); setMeta(null); }}>{c.title}</button>
                  <button aria-label={`Delete conversation ${c.title}`} className="ml-2 rounded p-1 text-muted transition-colors duration-micro ease-out hover:bg-danger-soft hover:text-danger active:bg-danger/20" onClick={() => remove.mutate(c.id)}><Trash2 className="h-3.5 w-3.5" /></button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="flex min-h-[28rem] flex-col rounded-lg border border-border bg-surface">
          <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
            {!activeId && !pending && <EmptyState bare title="Ask a question about your documents">The assistant only answers from retrieved passages and tells you when the evidence is insufficient.</EmptyState>}
            {thread.data?.messages.map((m) => (
              <div key={m.id} className={m.role === "user" ? "ml-auto max-w-[85%] rounded-lg bg-accent-soft px-3 py-2 text-sm" : "max-w-[95%] text-sm"}>
                {m.role === "user" ? m.content : (
                  <div className="space-y-4">
                    <p className="whitespace-pre-wrap text-base leading-relaxed">{m.content}</p>
                    {m.sufficient_evidence === false && <Badge tone="warn">insufficient evidence</Badge>}
                    <SourceList citations={m.citations} />
                    <div className="flex items-center gap-1 text-muted">
                      <button aria-label="Copy answer" className="rounded p-1.5 transition-colors duration-micro ease-out hover:bg-sunk hover:text-fg active:bg-bg" onClick={() => void copy(m)}><Copy className="h-3.5 w-3.5" /></button>
                      {copied === m.id && <span className="text-xs text-ok">Copied</span>}
                      <button aria-label="Helpful" aria-pressed={m.feedback === "up"} className={`rounded p-1.5 transition-colors duration-micro ease-out hover:bg-sunk active:bg-bg ${m.feedback === "up" ? "text-ok" : ""}`} onClick={() => rate.mutate({ id: m.id, v: "up" })}><ThumbsUp className="h-3.5 w-3.5" /></button>
                      <button aria-label="Not helpful" aria-pressed={m.feedback === "down"} className={`rounded p-1.5 transition-colors duration-micro ease-out hover:bg-sunk active:bg-bg ${m.feedback === "down" ? "text-danger" : ""}`} onClick={() => rate.mutate({ id: m.id, v: "down" })}><ThumbsDown className="h-3.5 w-3.5" /></button>
                      {m.latency_ms !== null && <span className="measured ml-auto text-xs">{(m.latency_ms / 1000).toFixed(1)} s</span>}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {pending && <div className="ml-auto max-w-[85%] rounded-lg bg-accent-soft px-3 py-2 text-sm">{pending}</div>}
            {ask.isPending && !live && <Spinner label="Searching documents and generating an answer" />}
            {ask.isPending && live && (
              <div className="max-w-[95%] text-sm" aria-live="off">
                <div className="space-y-4">
                  <p className="whitespace-pre-wrap text-base leading-relaxed">{live.text}<span aria-hidden className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent align-text-bottom" /></p>
                  <SourceList citations={live.citations} />
                </div>
              </div>
            )}
            {stopped && <p className="text-sm text-muted">Stopped. This question and the partial answer were not saved.</p>}
            {ask.isError && !stopped && <ErrorState error={ask.error} onRetry={() => send(lastQuestion)} />}
            {meta && (meta.retrieval_mode !== "hybrid" || meta.excluded_suspicious > 0 || meta.inference) && (
              <div className="space-y-1 text-sm text-muted">
                {meta.retrieval_mode !== "hybrid" && <p>Retrieval mode: {meta.retrieval_mode}.</p>}
                {meta.excluded_suspicious > 0 && <p>{meta.excluded_suspicious} passage(s) were excluded because they contained instruction-like text.</p>}
                {meta.inference && <p><strong className="font-medium text-fg-2">Inference (not stated directly in the sources):</strong> {meta.inference}</p>}
              </div>
            )}
            <div ref={bottom} />
          </div>
          <form onSubmit={submit} className="flex gap-2 border-t border-border p-3">
            <input aria-label="Question" value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} placeholder="Ask a question about your documents…"
              className="flex-1 rounded-md border border-edge bg-sunk px-3 py-2 text-sm placeholder:text-muted transition-colors duration-micro ease-out hover:border-fg-2 focus:border-accent" />
            {ask.isPending && <Button type="button" variant="secondary" onClick={() => abort.current?.abort()}><Square className="h-4 w-4" /> Stop</Button>}
            <Button type="submit" disabled={!input.trim()} loading={ask.isPending}><SendHorizonal className="h-4 w-4" /> Send</Button>
          </form>
        </section>
      </div>
    </>
  );
}
