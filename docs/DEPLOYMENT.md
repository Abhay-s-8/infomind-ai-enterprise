# Deployment: API on Render, web interface on Vercel

Educational prototype: deploy it with **synthetic or public data only**. A public URL means anyone on the internet can reach the login page.

```
Browser ──► Vercel (static React app) ──HTTPS + CORS──► Render web service (FastAPI + SQLite + embedded Qdrant on one disk)
```

## What works and what does not on Render
Ollama needs your GPU and cannot run on Render, so this deployment runs **without the language model**:

| Works | Does not work |
|---|---|
| Sign-in, roles, audit log, upload and processing, classification and review queue, entities, analytics, keyword search, lexical ("hash") search | The AI assistant (it reports "Ollama is not reachable"), neural semantic search (`nomic-embed-text`) |

The "hash" embedder is lexical (word-overlap), not semantic; it is labelled as such in Settings. To get the assistant back, point `OLLAMA_BASE_URL` at a machine that runs Ollama and set `EMBEDDING_PROVIDER=ollama`, `EMBEDDING_DIMENSIONS=768` (then reprocess documents so vectors are rebuilt).

## 1. API on Render (about 5 minutes, in the dashboard)
`render.yaml` in the repo root describes the service. Render needs access to this (private) GitHub repo.
1. In your Render project choose **New, then Blueprint**, connect GitHub and select `Abhay-s-8/infomind-ai-enterprise`, branch `main`.
2. When prompted, enter `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` (at least 10 characters; use a **new** password). `JWT_SECRET` is generated for you.
3. Check the plan and disk shown on the review screen, then apply. The first build takes several minutes.
4. When the service is live, open `https://<your-service>.onrender.com/api/v1/health`; it should return `{"status":"ok"}`.

On every start the container runs the database migration, creates the admin if it does not exist, trains the classifier if none is active (`AUTO_TRAIN`) and adds the synthetic demo documents (`SEED_DEMO`). All are safe to repeat. Set `SEED_DEMO` to `false` for real use.

Design choices (all in `render.yaml`):
- **One persistent disk** (`/var/data`) holds the SQLite database, uploaded files, vectors and the trained model, so they stay consistent across restarts and redeploys. A disk needs a paid instance and a single instance, so the service cannot be scaled out.
- **Registration is off** (`ENABLE_REGISTRATION=false`). Only the admin can create accounts.
- **Production mode:** no `/docs` and no `/openapi.json`; a weak or default `JWT_SECRET` stops the app from starting.
- **`CORS_ORIGINS`** allows only the Vercel URL. If you use another domain, change it.
- Ownership of the disk is fixed at start-up and the app then runs as an unprivileged user.

**Cost** (approximate, from Render's pricing at the time of writing; check render.com/pricing): the `0.5c-512mb` web service is about $7 per month and the 1 GB disk about $0.25 per month. Measured here: migrate + train + seed peaked at about 220 MB and the running API used about 180 MB, so 512 MB fits with headroom, but a large upload could need a bigger plan. A free web service has no disk and spins down when idle, which would lose the files and vectors, so it is not used.

## 2. Web interface on Vercel
The project `infomind-ai-enterprise` is already linked to the GitHub repo (root directory `frontend`) and redeploys on every push to `main`.
1. In Vercel: **Project, Settings, Environment Variables**, add `VITE_API_BASE` = `https://<your-service>.onrender.com/api/v1` for *Production*. (Or `vercel env add VITE_API_BASE production` from the repo root.)
2. Redeploy (push a commit or use **Deployments, Redeploy**). The variable is read at build time.
3. Open the Vercel URL and sign in with the admin you chose in step 1.

## Checks and limits
- Free-tier or paid instances may take a moment to wake after a deploy; the first request can be slow.
- Everything is served over HTTPS by the hosts, but this prototype keeps the JWT in browser storage, has an in-process rate limiter and has no malware scanning of uploads (see SECURITY.md).
- Back up `/var/data` (Render disk snapshots) if the data matters.
- Verified locally by running the production image with a root-owned volume and the same variables as `render.yaml`: migration, admin creation, training, seeding, sign-in, closed registration, hidden docs, CORS for the Vercel origin only, persistence across a restart/redeploy. **Not verified on Render itself** (that needs your dashboard).
