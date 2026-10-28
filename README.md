# InfoMind AI Enterprise

**AI/ML-Based Intelligent Information Management and Retrieval System** — an educational, research-oriented prototype that ingests documents, classifies them with scikit-learn, indexes them for keyword + semantic search, and answers questions with cited evidence using a local LLM.

> **Not for operational use.** This is a student prototype. It is not certified for classified, restricted, or military use. Use only synthetic or public data. See [docs/SECURITY.md](docs/SECURITY.md).

## 1. Problem statement and objectives
Organisations accumulate documents that are hard to organise, find and interrogate. Objectives: (1) ingest PDF/DOCX/TXT/CSV/XLSX safely; (2) classify automatically with measurable accuracy and human review; (3) retrieve by keyword and meaning; (4) answer questions **only** from authorized evidence, with verifiable citations; (5) show real analytics; (6) run locally on a laptop.

## 2. Key features (all implemented and covered by tests)
- Upload with extension + MIME + file-structure validation, SHA-256 de-duplication, size limits, generated storage IDs (no user-controlled paths).
- DB-backed job queue and worker; staged pipeline (extract → chunk → embed → classify); retries are idempotent.
- TF-IDF + Logistic Regression vs Linear SVM, held-out evaluation, versioned models, low-confidence → review queue; human labels are stored separately and never overwritten.
- Keyword, semantic and hybrid search with category / file type / date filters, pagination and highlighting.
- RAG assistant: authorized retrieval, evidence-sufficiency gate, injection defences, citations validated against retrieved chunks, conversation persistence with owner-only access. Answers **stream** to the UI word by word (Server-Sent Events, `POST /chat/stream`) with a Stop button; text is shown only after its citations have been validated, and the saved message replaces the streamed text when it finishes.
- Rule-based entity extraction (dates, money, times, emails) plus optional spaCy NER.
- Role-based access (admin / analyst / reviewer) enforced on the backend; audit log.
- Dashboard + analytics from real records; each panel labelled measured / offline-evaluation / synthetic.
- Evaluation CLI (classification, retrieval Recall@K / Precision@K / MRR / nDCG, RAG checks) exporting JSON/CSV.

## 3. Architecture
```mermaid
flowchart LR
  UI[React + Vite] -->|REST /api/v1| API[FastAPI modular monolith]
  API --> PG[(PostgreSQL / SQLite dev)]
  API --> QD[(Qdrant)]
  API -->|service layer only| OL[Ollama: llama3.2:3b + nomic-embed-text]
  W[Worker: DB job table] --> PG
  W --> QD
  W --> OL
  API --- FS[(Upload dir outside web root)]
```
Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). API: [docs/API.md](docs/API.md) (also live at `/docs`).

## 4. Requirements
Target machine: i7-13700HX, 16 GB RAM, RTX 4050 6 GB, Windows 11. The app runs **without a GPU**; Ollama uses the GPU when it can. Prerequisites: Python 3.11+ (tested 3.13), Node 20+ (tested 22), Git; optional: Ollama, Docker Desktop, PostgreSQL, Tesseract (OCR is *not* implemented yet).

## 5. Quick start on Windows (no Docker, no Ollama needed to try it)
```powershell
cd infomind-ai-enterprise
.\scripts\setup.ps1                      # venv, backend deps, npm install, creates backend\.env
# edit backend\.env: set JWT_SECRET, DEV_ADMIN_PASSWORD. For a no-Ollama trial also set EMBEDDING_PROVIDER=hash and EMBEDDING_DIMENSIONS=256
cd backend
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m app.cli train           # trains the classifier on synthetic data
.\.venv\Scripts\python -m app.cli create-admin --email admin@example.com --password "<your password>"   # skip if DEV_ADMIN_* is set
.\.venv\Scripts\python -m app.cli seed-demo       # 14 synthetic demo documents (flagged "demo")
cd ..; .\scripts\dev.ps1                          # API :8000, UI :5173
```
Open http://localhost:5173 and sign in.

### Local models (Ollama, needed for the AI assistant and real semantic embeddings)
Install Ollama for Windows, then `.\scripts\pull-models.ps1` (pulls `llama3.2:3b` and `nomic-embed-text`; never automatic). If Ollama is down the app still starts; Settings shows model status and only the assistant / embedding features are disabled. Speed depends on quantization, context length (`OLLAMA_NUM_CTX`, default 4096) and free VRAM — do not assume all 6 GB/16 GB is available.

### PostgreSQL and Qdrant
- SQLite is the zero-setup default. For PostgreSQL set `DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/infomind` and run `alembic upgrade head`.
- Qdrant: `QDRANT_URL=path:../data/qdrant` (embedded, single process) or `http://localhost:6333` for a server.

### Docker (Postgres + Qdrant + API + worker + frontend)
```powershell
copy .env.example .env      # edit the placeholders
docker compose up --build -d
```
Then seed the empty database: `docker compose exec backend python -m app.cli train` and `... seed-demo`. UI: http://localhost:5173, API docs: http://localhost:8000/docs.
Ollama stays on the Windows host (GPU passthrough to Docker on Windows is not assumed); containers use `http://host.docker.internal:11434`. Stop with `docker compose down` (add `-v` to delete data).
- If host port 5432 is taken (for example by a local PostgreSQL), set `POSTGRES_HOST_PORT=5433` in `.env`; containers are unaffected.
- If the PostgreSQL password contains `@`, `:`, `/` or `%`, also set `DATABASE_URL` in `.env` with the password percent-encoded (`@` → `%40`).

## 6. Demonstration procedure
1. Log in as the admin. **Classification → Train on synthetic data** (or `python -m app.cli train`).
2. **Documents →** upload `data/sample/documents/*.txt` (or run `seed-demo`). Watch statuses reach `completed`.
3. Open a document: see category + scores (labelled uncalibrated probability or decision value), entities, processing history.
4. **Semantic Search:** try “rules about putting unauthorised programs on work computers” (keyword search finds nothing, semantic finds the acceptable-use policy); compare modes.
5. **AI Assistant:** ask “How many years must employee records be retained?” and inspect the citation card. Ask “What is the capital of Australia?” → the assistant reports insufficient evidence. Note: with the default `llama3.2:3b`, “How long are database backups retained?” gets an *insufficient evidence* reply; it answers “35 days” with citation using `llama3.1:8b` (see Known limitations); the Search page finds the right passage with either.
6. **Review Queue** (reviewer/admin): confirm or correct a low-confidence prediction; check **Audit Logs** (admin).
7. `python -m app.cli evaluate` → results in `data/evaluation/`.

## 7. Tests and quality
```powershell
.\scripts\test.ps1       # ruff + pytest (backend), tsc + vitest (frontend)
```
Last run on this machine: backend **75 passed**, `ruff` clean; frontend **27 passed**, `tsc` clean. Tests use SQLite, embedded Qdrant, the hashing embedder and a scripted fake LLM — no model downloads.

**Also verified on this machine (2026-10-28):**
- `docker compose up --build`: all five containers (PostgreSQL 16, Qdrant, API, worker, frontend) build and run. The API container runs `alembic upgrade head` against PostgreSQL (revision `0001`, 16 tables), the admin is seeded, 14 demo documents reach `completed` through the worker with real `nomic-embed-text` embeddings, and `/health/ready` reports database, vector store and Ollama OK.
- Browser walkthrough with headless Edge against the Docker stack: sign-in, dashboard, documents, document detail, search, assistant (cited answer and refusal), classification, analytics, reviews, audit and settings all render with no JavaScript errors. The screenshots were reviewed for the dashboard, search and assistant pages only; the others were checked for errors, not inspected by eye. This is a smoke test, not an accessibility or cross-browser review.
- Streaming assistant, in Docker with `llama3.1:8b` and a real browser: the answer text appears progressively (about 55 ms per word once it starts), the first word arrives about 1.3-2 s after sending when the model is warm, and Stop works. The first question after Ollama has been idle took about 12 s because the model has to be reloaded. Answers here are only a few words long, so the visible benefit is small; it matters more for longer answers. Verified through the frontend dev proxy; **not** verified behind a production reverse proxy (see Troubleshooting for buffering).
- RAG against Ollama: see [docs/EVALUATION.md](docs/EVALUATION.md). With the default `llama3.2:3b` the assistant wrongly refuses some answerable questions when a second, less relevant chunk is retrieved. With `llama3.1:8b` (`OLLAMA_LLM_MODEL` in `.env`, `ollama pull llama3.1:8b`, about 4.9 GB, about 4.6 GB of the 6 GB GPU in use) the official evaluation scored 4/4 answerable and 3/3 refused. Small synthetic sample: not evidence of general reliability.

**Not verified:** PostgreSQL via a native Windows install (only the Docker PostgreSQL was used), OCR (not implemented), other browsers, and any load or security testing.

## 8. Classification training / evaluation
`python -m app.cli train [--csv path]` and `python -m app.cli evaluate [--skip-rag]`. Metrics from the bundled synthetic data are near-perfect because the data is template-generated; they show the pipeline works, **not** real-world accuracy. See [docs/MODEL_CARD.md](docs/MODEL_CARD.md) and [docs/EVALUATION.md](docs/EVALUATION.md).

## 9. Known limitations
No OCR yet (scanned PDFs fail with a clear message); single-node in-memory rate limiter; JWT in browser storage (XSS exposure); no live push for other pages (documents and dashboard poll every 2-8 s, only the assistant streams); stopping or losing the connection mid-answer saves nothing; each chat question is independent (no conversation memory); search totals are capped at 200 candidates; keyword search is SQL `LIKE` + term overlap (not BM25); RAG faithfulness needs manual review; with the default `llama3.2:3b` the assistant can wrongly refuse an answerable question when retrieval also returns a less relevant chunk (measured; `llama3.1:8b` did not show this on the test questions, see EVALUATION.md); uses synthetic data only; no antivirus scanning of uploads.

## 10. Future enhancements
OCR via Tesseract, server-pushed status events for document processing (instead of polling), BM25 / reranking, Redis-backed rate limits, httpOnly-cookie sessions, entity relationship graph, scheduled retraining workflow with approval, per-document sharing.

Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
