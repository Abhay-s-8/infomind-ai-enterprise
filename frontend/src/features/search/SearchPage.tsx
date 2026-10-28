import { useQuery } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Button, EmptyState, ErrorState, Input, PageHeader, Select, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { ALLOWED_EXTENSIONS, formatDate, highlightParts } from "../../lib/utils";
import type { SearchMode } from "../../types";

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const initial = params.get("q") ?? "";
  const [input, setInput] = useState(initial);
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [fileType, setFileType] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const query = params.get("q") ?? "";
  useEffect(() => { setInput(query); setPage(1); }, [query]); // the header search box changes ?q= while this page is mounted

  const results = useQuery({
    queryKey: ["search", query, mode, fileType, category, page],
    queryFn: () => api.search(mode, { query, file_type: fileType || undefined, category: category || undefined, page, page_size: 10 }),
    enabled: query.length > 0,
  });
  const categories = useQuery({ queryKey: ["categories"], queryFn: api.models, staleTime: 60_000 });
  const cats = categories.data?.find((m) => m.is_active)?.categories ?? [];

  const submit = (e: FormEvent) => { e.preventDefault(); setPage(1); setParams(input.trim() ? { q: input.trim() } : {}); };
  const totalPages = results.data ? Math.max(1, Math.ceil(results.data.total / results.data.page_size)) : 1;

  return (
    <>
      <PageHeader title="Semantic Search" description="Search only the documents you are authorized to see. Hybrid combines keyword and meaning-based ranking." />
      <form onSubmit={submit} className="mb-4 flex flex-wrap gap-3" role="search">
        <Input aria-label="Search query" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about a topic, term or fact…" className="min-w-[16rem] flex-1" />
        <Select aria-label="Search mode" value={mode} onChange={(e) => { setMode(e.target.value as SearchMode); setPage(1); }} className="max-w-[10rem]">
          <option value="hybrid">Hybrid</option><option value="semantic">Semantic</option><option value="keyword">Keyword</option>
        </Select>
        <Select aria-label="File type" value={fileType} onChange={(e) => { setFileType(e.target.value); setPage(1); }} className="max-w-[9rem]">
          <option value="">All types</option>{ALLOWED_EXTENSIONS.map((t) => <option key={t}>{t}</option>)}
        </Select>
        <Select aria-label="Category" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className="max-w-[14rem]">
          <option value="">All categories</option>{cats.map((c) => <option key={c}>{c}</option>)}
        </Select>
        <Button type="submit">Search</Button>
      </form>

      {!query ? <EmptyState title="Enter a query to search your documents" /> :
        results.isLoading ? <Spinner label="Searching" /> :
        results.error ? <ErrorState error={results.error} onRetry={() => void results.refetch()} /> :
        results.data!.results.length === 0 ? <EmptyState title="No matching passages">Try different words, another mode, or fewer filters.</EmptyState> : (
          <>
            <p className="mb-3 text-sm text-muted"><span className="measured">{results.data!.total}</span> passages in {results.data!.mode} mode. Results are capped at the top 200 candidates.</p>
            <ul className="panels">
              {results.data!.results.map((r) => (
                <li key={r.chunk_id} className="p-5">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <Link to={`/documents/${r.document_id}`} className="link font-medium">{r.filename}</Link>
                    <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
                      <span className="measured">{r.page ? `page ${r.page}` : "page n/a"}</span>
                      {r.category && <Badge tone="info">{r.category}</Badge>}
                      <span className="measured">{formatDate(r.created_at)}</span>
                      <Badge tone="info">score {r.score.toFixed(3)}</Badge>
                    </div>
                  </div>
                  <p className="max-w-3xl text-base leading-relaxed text-fg-2">
                    {highlightParts(r.excerpt, r.highlights).map((p, i) => (p.hit ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))}
                  </p>
                  <div className="measured mt-3 flex gap-4 text-muted"><span>keyword {r.keyword_score.toFixed(2)}</span>{r.semantic_score !== null && <span>semantic {r.semantic_score.toFixed(2)}</span>}</div>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex items-center justify-center gap-3 text-sm text-muted">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <span className="measured">Page {page} of {totalPages}</span>
              <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          </>
        )}
    </>
  );
}
