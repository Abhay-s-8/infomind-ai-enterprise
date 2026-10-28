# API (v1)

Live, authoritative OpenAPI at `http://localhost:8000/docs` (development only). Base path `/api/v1`. Auth: `Authorization: Bearer <JWT>` from `POST /auth/login`. Errors: `{"error": {"code", "message", "request_id", "details?"}}` (401 from the auth dependency uses FastAPI's `{"detail"}`); every response carries `X-Request-ID`.

| Method & path | Auth | Notes |
|---|---|---|
| POST `/auth/register` | public (if enabled) | creates an **analyst**; password ≥ 10 chars; rate-limited |
| POST `/auth/login` · POST `/auth/logout` · GET `/auth/me` | public / user | login failures are audited; generic error message |
| GET `/users` · PATCH `/users/{id}/role` | admin | cannot demote self |
| POST `/documents` (multipart `files`) | analyst+ | ≤ 20 files; per-file results and errors; duplicates reported |
| GET `/documents` | user | filters `status,category,file_type,q`, `sort`, `page,page_size`; owner-scoped (admin: all) |
| GET `/documents/{id}` · `/content` · `/download` | owner/admin | others get 404; download audited |
| POST `/documents/{id}/reprocess` · `/reclassify` · DELETE `/documents/{id}` | owner/admin (analyst+) | delete: see consistency strategy |
| DELETE `/documents/{id}/entities/{eid}` | reviewer+ | soft-removes an annotation |
| GET `/search?query=` · POST `/search/semantic` · `/search/hybrid` | analyst+ | body: `query, category, file_type, date_from, date_to, page, page_size` |
| POST `/chat/stream` | analyst+ | same input and rules as `/chat`, returned as Server-Sent Events (see below). 404/422/401 are normal HTTP errors sent before the stream starts; model problems arrive as an `error` event on a 200 stream |
| POST `/chat` · GET `/conversations` · GET/DELETE `/conversations/{id}` · POST `/messages/{id}/feedback` | analyst+ | owner-only; 503 if the LLM is down; 502 on unreadable model output |
| POST `/classification/predict` · GET `/classification/metrics` · `/classification/models` | analyst+ | 404 / 409 until a model is trained |
| POST `/classification/train` | admin | 202; runs as a background task; audited |
| GET `/reviews` · POST `/reviews/{document_id}` · GET `/reviews/history` | reviewer+ | the review item id **is the document id** |
| GET `/analytics/overview\|documents\|classification\|search` | analyst+ | scoped to caller |
| GET `/audit` | admin | filters `action,outcome`, paginated |
| GET `/evaluations` | analyst+ | persisted evaluation runs |
| GET `/health` · `/health/ready` · `/system/models` | public / public / user | readiness reports DB, Qdrant, Ollama separately |

Citation object: `{document_id, filename, page|null, chunk_id, excerpt, score}`; `page` is `null` when the format has no page numbers.

## `POST /chat/stream` events
Request body is the same as `/chat` (`question`, optional `conversation_id`); response is `text/event-stream`. Use `fetch` with the `Authorization` header (browser `EventSource` cannot send it).
| Event | Data | Meaning |
|---|---|---|
| `meta` | `{retrieval_mode, excluded_suspicious}` | retrieval finished (sent first) |
| `citations` | `[Citation]` | citations that were validated against retrieved chunks; sent only when the answer will be streamed |
| `delta` | `{text}` | next piece of the answer text. **Provisional**: sent only after `supported: true` and at least one valid citation were seen |
| `done` | same body as `POST /chat` | the stored, fully validated message; **authoritative**, replaces any streamed text |
| `error` | `{message, status}` | terminal; nothing was saved. `status` is 503 (model unavailable), 502 (unreadable model output) or 500 |
No `citations`/`delta` events are sent when the evidence gate refuses (`meta` then `done`), when the model does not cite, or when it writes its JSON keys out of order; in those cases only `done` carries the answer. If the client disconnects before `done`, nothing is saved. The model is asked to write the keys in the order `supported`, `citations`, `answer`, `inference` so citations can be checked before any answer text is shown.
