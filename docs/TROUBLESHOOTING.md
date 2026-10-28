# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Assistant: “Ollama is not reachable” | Start Ollama (`ollama serve` or the tray app); check `OLLAMA_BASE_URL`. In Docker use `http://host.docker.internal:11434`, never `localhost`. Settings → AI model availability shows what is missing |
| Model “not available” though Ollama runs | `ollama pull llama3.2:3b` and `ollama pull nomic-embed-text` (models are never auto-downloaded) |
| Document stuck `failed` with “semantic indexing failed” | Qdrant or the embedding model was down; text/keyword search still work. Fix the service, then **Reprocess** |
| Embedding dimension error | `EMBEDDING_DIMENSIONS` must match the model (nomic-embed-text = 768). Changing models creates a new Qdrant collection → reprocess documents |
| Documents never leave `queued` | No worker. Set `RUN_WORKER_IN_API=true` (default outside Docker) or run `python -m app.workers.worker` |
| “Scanned documents need OCR” | OCR is not implemented; upload text-based PDFs |
| `No trained classification model` (409/404) | Admin: Classification → Train, or `python -m app.cli train` |
| 401 after a while | Token expired (`ACCESS_TOKEN_MINUTES`, default 60); sign in again |
| Qdrant “already accessed by another process” | Embedded `path:` mode allows one process; run Qdrant server (Docker) or set `RUN_WORKER_IN_API=true` and don't start a separate worker/CLI at the same time |
| `docker compose` cannot connect to the daemon | Start Docker Desktop |
| `POSTGRES_PASSWORD`/`JWT_SECRET` required | Create `.env` from `.env.example` |
| `ports are not available: ... 127.0.0.1:5432` | Another PostgreSQL already uses the host port. Set `POSTGRES_HOST_PORT=5433` in `.env` and run `docker compose up -d` again |
| Backend crashes on startup or cannot log in to PostgreSQL when the password contains `@`, `:`, `/` or `%` | The password is placed in a URL. Set `DATABASE_URL` in `.env` with the password percent-encoded (`@` → `%40`). `POSTGRES_PASSWORD` stays unencoded |
| Changed `POSTGRES_PASSWORD` but PostgreSQL still rejects the old/new one | The password is only applied when the data volume is first created. `docker compose down -v` (deletes data) or change it with `ALTER USER` |
| Qdrant “client version ... is incompatible with server version” | `qdrant-client` must stay within one minor version of the server image (`requirements.txt` pins 1.12.x for `qdrant/qdrant:v1.12.4`) |
| Assistant says “insufficient evidence” for a question the Search page answers | Known limitation of the 3B model when a less relevant chunk is also retrieved; see docs/EVALUATION.md. Set `OLLAMA_LLM_MODEL=llama3.1:8b` in `.env` (`ollama pull llama3.1:8b`, then `docker compose up -d backend worker`); needs about 4.6 GB of VRAM, so close other GPU-heavy apps || Assistant answer appears all at once instead of streaming (behind your own proxy) | A reverse proxy is buffering the response. Disable buffering for `/api/v1/chat/stream` (nginx: `proxy_buffering off;`, the API already sends `X-Accel-Buffering: no`). The bundled Vite proxy streams correctly |
| First assistant answer after a break takes about 10 s | Ollama unloaded the idle model and reloads it from disk; later answers are fast. Set `OLLAMA_KEEP_ALIVE` (for example `30m`) in Ollama's environment to keep it loaded |
| Slow answers | CPU inference or a long context: lower `OLLAMA_NUM_CTX` / `RAG_TOP_K`, close GPU-heavy apps; 6 GB VRAM is shared with Windows |
| Port 5173/8000 in use | Stop the old process or change ports (`--port`, `VITE_PROXY_TARGET`) |
| PowerShell blocks scripts | `Set-ExecutionPolicy -Scope Process Bypass` |
