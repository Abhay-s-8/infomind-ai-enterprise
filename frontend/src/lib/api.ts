import type {
  AuditEvent, ChatResponse, ChatStreamEvent, ClassificationAnalytics, Conversation, ConversationDetail, DocumentDetail, DocumentList,
  DocumentsAnalytics, ModelInfo, Overview, ReviewItem, SearchAnalytics, SearchMode, SearchResponse, SystemModels, UploadBatch, User,
} from "../types";

// Hosting dashboards and shells sometimes add a byte-order mark or whitespace to pasted values; either would turn an
// absolute URL into a relative one, so both are removed.
const BASE = (((import.meta.env.VITE_API_BASE as string | undefined) ?? "").replace(/^﻿/, "").trim().replace(/\/+$/, "")) || "/api/v1";
const TOKEN_KEY = "infomind.token";

export class ApiError extends Error {
  constructor(public status: number, message: string, public requestId?: string) {
    super(message);
  }
}

let memoryToken: string | null = null;
export function getToken(): string | null {
  try { return memoryToken ?? localStorage.getItem(TOKEN_KEY); } catch { return memoryToken; }
}
export function setToken(token: string | null): void {
  memoryToken = token;
  try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void): void { onUnauthorized = fn; }

function parseError(status: number, body: unknown): ApiError {
  const b = body as { error?: { message?: string; request_id?: string; details?: { field: string; message: string }[] }; detail?: unknown } | null;
  if (b?.error) {
    const extra = b.error.details?.map((d) => `${d.field}: ${d.message}`).join("; ");
    return new ApiError(status, extra ? `${b.error.message} (${extra})` : b.error.message ?? "Request failed", b.error.request_id);
  }
  if (typeof b?.detail === "string") return new ApiError(status, b.detail);
  return new ApiError(status, `Request failed (${status})`);
}

async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (auth && token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && auth) onUnauthorized();
    throw parseError(res.status, body);
  }
  return body as T;
}

/** Parses a Server-Sent Events body (we use fetch, not EventSource, because EventSource cannot send the auth header). */
async function streamChat(question: string, conversation_id: string | undefined, onEvent: (e: ChatStreamEvent) => void, signal?: AbortSignal): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json", Accept: "text/event-stream" });
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${BASE}/chat/stream`, { method: "POST", headers, body: JSON.stringify({ question, conversation_id }), signal });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (!res.ok || !res.body) {
    if (res.status === 401) onUnauthorized();
    throw parseError(res.status, await res.json().catch(() => null));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  const dispatch = (block: string) => {
    let type = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) type = line.slice(7);
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (!type || !data) return;
    const event = { type, data: JSON.parse(data) } as ChatStreamEvent;
    if (event.type === "done" || event.type === "error") finished = true;
    if (event.type === "error") throw new ApiError(event.data.status, event.data.message);
    onEvent(event);
  };
  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      dispatch(buffer.slice(0, cut));
      buffer = buffer.slice(cut + 2);
    }
    if (done) break;
  }
  if (buffer.trim()) dispatch(buffer);
  if (!finished) throw new ApiError(0, "The connection closed before the answer finished. Please retry.");
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : "";
};
const json = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  login: (email: string, password: string) => request<{ access_token: string }>("/auth/login", json({ email, password }), false),
  register: (email: string, password: string, full_name: string) => request<User>("/auth/register", json({ email, password, full_name }), false),
  me: () => request<User>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  users: () => request<User[]>("/users"),
  setRole: (id: string, role: string) => request<User>(`/users/${id}/role`, { method: "PATCH", body: JSON.stringify({ role }) }),

  documents: (p: { page?: number; page_size?: number; status?: string; category?: string; file_type?: string; q?: string; sort?: string }) =>
    request<DocumentList>(`/documents${qs(p)}`),
  document: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  reprocess: (id: string) => request(`/documents/${id}/reprocess`, { method: "POST" }),
  reclassify: (id: string) => request(`/documents/${id}/reclassify`, { method: "POST" }),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  removeEntity: (docId: string, entityId: string) => request<void>(`/documents/${docId}/entities/${entityId}`, { method: "DELETE" }),
  async downloadDocument(id: string, filename: string) {
    const res = await fetch(`${BASE}/documents/${id}/download`, { headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
    if (!res.ok) throw new ApiError(res.status, "Download failed");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },
  /** XHR (not fetch) so upload progress events are available. */
  upload(files: File[], onProgress: (pct: number) => void): Promise<UploadBatch> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/documents`);
      const token = getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
      xhr.onerror = () => reject(new ApiError(0, "Cannot reach the server. Is the backend running?"));
      xhr.onload = () => {
        let body: unknown = null;
        try { body = JSON.parse(xhr.responseText); } catch { /* non-JSON */ }
        xhr.status >= 200 && xhr.status < 300 ? resolve(body as UploadBatch) : reject(parseError(xhr.status, body));
      };
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      xhr.send(form);
    });
  },

  search: (mode: SearchMode, body: { query: string; category?: string; file_type?: string; page?: number; page_size?: number }) =>
    mode === "keyword"
      ? request<SearchResponse>(`/search${qs(body)}`)
      : request<SearchResponse>(`/search/${mode}`, json(body)),

  chat: (question: string, conversation_id?: string) => request<ChatResponse>("/chat", json({ question, conversation_id })),
  /** Streaming variant of `chat`; resolves after the `done` event and rejects on an `error` event or a dropped connection. */
  chatStream: (question: string, conversation_id: string | undefined, onEvent: (e: ChatStreamEvent) => void, signal?: AbortSignal) =>
    streamChat(question, conversation_id, onEvent, signal),
  conversations: () => request<Conversation[]>("/conversations"),
  conversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
  feedback: (messageId: string, feedback: "up" | "down") => request<void>(`/messages/${messageId}/feedback`, json({ feedback })),

  models: () => request<ModelInfo[]>("/classification/models"),
  metrics: () => request<ModelInfo>("/classification/metrics"),
  train: () => request<{ message: string }>("/classification/train", json({ dataset: "synthetic" })),
  predict: (text: string) => request<{ category: string; score: number; score_type: string; all_scores: Record<string, number>; low_confidence: boolean; model_version: string; note: string }>("/classification/predict", json({ text })),
  reviews: (page = 1) => request<{ items: ReviewItem[]; total: number }>(`/reviews${qs({ page })}`),
  submitReview: (documentId: string, body: { decision: "confirm" | "correct"; category?: string; note?: string }) =>
    request(`/reviews/${documentId}`, json(body)),

  reviewHistory: () => request<{ id: string; decision: string; predicted: string | null; final: string; note: string; created_at: string }[]>("/reviews/history"),

  overview: (days = 30) => request<Overview>(`/analytics/overview${qs({ days })}`),
  docAnalytics: (days = 30) => request<DocumentsAnalytics>(`/analytics/documents${qs({ days })}`),
  classAnalytics: () => request<ClassificationAnalytics>("/analytics/classification"),
  searchAnalytics: (days = 30) => request<SearchAnalytics>(`/analytics/search${qs({ days })}`),
  audit: (p: { action?: string; outcome?: string; page?: number }) => request<AuditEvent[]>(`/audit${qs(p)}`),
  systemModels: () => request<SystemModels>("/system/models"),
};
