# Security notes and threat model

**Scope:** local educational prototype. Not accredited; do not load classified, restricted or personal data.

## Implemented controls (each has an API-level test unless noted)
| Area | Control |
|---|---|
| AuthN | bcrypt password hashing; JWT (HS256) with expiry and `jti`; dummy-hash comparison for unknown emails; login/register rate limits |
| AuthZ | Role checks in FastAPI dependencies; owner-or-admin document access with 404 for others; owner-only conversations (even vs admin); admin-only training, user management, audit |
| Uploads | extension allow-list, declared-MIME check, structural validation (PDF header, OOXML members, UTF-8 text), size cap with bounded read, zip-expansion cap, server-generated storage IDs, filename kept as metadata only, path-resolution guard, stored outside any served directory, `nosniff` on download. Files are parsed, never executed |
| Data access | SQLAlchemy parameterised queries; LIKE terms are bound parameters; user input never concatenated into SQL |
| RAG | See `rag_service.py`: scope → sanitize/drop injection-like chunks → delimited data blocks with aliases → JSON-only output → citation validation → evidence gate. No tools, shell or network access for the model. Streaming (`/chat/stream`) releases answer text only after `supported: true` and a valid citation were seen in the model's JSON, and the final saved message goes through the same validation as `/chat` (`AnswerStream`, `_finish`; tests in `test_chat_stream.py`). Streamed text is shown before the whole reply has been validated; the final message is authoritative |
| Audit | login success/failure, register, upload, download, delete, reclassify, reprocess, review, role change, training, denied requests, assistant questions (outcome flag only — no prompt text), each with actor, outcome and request id. No passwords/tokens/content. Application code has no update/delete path for audit rows (not enforced at DB-privilege level) |
| Errors | central handlers; 500s return a generic message + request id; processing errors are sanitised (no server paths) |
| Config | `.env` ignored by Git; placeholders only in `.env.example`; production mode refuses default/short `JWT_SECRET` and a dev admin password; docs UI and `/openapi.json` disabled in production; `ENABLE_REGISTRATION=false` closes self-sign-up; the first admin comes from `INITIAL_ADMIN_*` (password read from the environment, at least 10 characters); the container drops root after fixing the data directory's ownership; narrow CORS (explicit origins, no credentials) |

## Optional: Ollama's hosted cloud
With `OLLAMA_BASE_URL=https://ollama.com` and `OLLAMA_API_KEY`, question text and retrieved passages are sent to Ollama's servers, so they leave your machine (their stated policy: not logged, not used for training; not verified here). The key is a bearer secret in the hosting environment settings only. The client never echoes it, `python -m app.cli check-llm` prints only whether it is set, and production refuses to send it over plain `http://` to a remote host.

## Optional: Ollama behind a tunnel
`backend/app/gateway.py` is an authenticating gateway for reaching a local Ollama from a hosted API (see DEPLOYMENT.md). Loopback-only listener, Bearer key compared in constant time before any routing, allow-list of three calls (`POST /api/chat`, `POST /api/embed`, `GET /api/tags`), request-size and per-minute caps, no pass-through of the caller's credentials, docs and schema disabled. Covered by `test_ollama_remote.py`. Residual risks: anyone holding the key can use the GPU; the key sits in the hosted API's environment settings; the tunnel provider carries the traffic; the in-process rate cap is global, not per caller.

## Known weaknesses (deliberately documented)
- Token is kept in `localStorage` (XSS could steal it) and tokens cannot be revoked before expiry; a production build should use httpOnly cookies + CSRF protection and a revocation list.
- Rate limiting is in-process and per-IP only; no account lockout.
- Prompt-injection defences reduce but cannot eliminate risk; heuristics can both miss attacks and exclude benign text (excluded passages are reported to the user).
- No malware scanning, no encryption at rest, no TLS termination in the bundled setup (put a reverse proxy in front for HTTPS).
- Admins can read all documents (policy choice); there is no per-document sharing yet.
- Joblib model artifacts are unpickled on load — only load files produced by this app's training in `MODEL_DIR`.
- Download access is audited, document *view* is not.

## Threats considered
Unauthorized cross-user access (tests in `test_auth_and_docs.py`, `test_search_rag.py`) · malicious uploads / path traversal / spoofed types · prompt injection via document text · fabricated citations · secret leakage via config or logs · denial of service via huge files or unbounded model calls (limits and timeouts exist; not a hardened DoS defence).
