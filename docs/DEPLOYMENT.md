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
Two blueprints are provided. Render's own validator (`render blueprints validate`) was run on both.

| File | Needs a card? | Data | Use it for |
|---|---|---|---|
| `render.yaml` (default) | **No** (validated: accepted) | Resets whenever the free instance restarts or wakes from sleep | A demo that is always in a clean, consistent state |
| `render.paid.yaml` | **Yes**: without a payment method Render rejects it with `need_payment_info` | Persists on a 1 GB disk | Keeping uploads, users and vectors |

1. In your Render project choose **New, then Blueprint**, connect GitHub and select `Abhay-s-8/infomind-ai-enterprise`, branch `main`. (For the paid file, set the Blueprint file path to `render.paid.yaml` after adding a payment method under Account Settings, Billing.)
2. When prompted, enter `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` (at least 10 characters; use a **new** password). `JWT_SECRET` is generated for you.
3. Check the plan on the review screen, then apply. The first build takes several minutes.
4. When the service is live, open `https://<your-service>.onrender.com/api/v1/health`; it should return `{"status":"ok"}`. The service name `infomind-api` must be free on Render; otherwise Render adds a suffix to the address.

On every start the container runs the database migration, creates the admin if it does not exist, trains the classifier if none is active (`AUTO_TRAIN`) and adds the synthetic demo documents (`SEED_DEMO`). All are safe to repeat. Set `SEED_DEMO` to `false` for real use.

**What the free variant means in practice** (the persistence behaviour is by design; the sleep behaviour is Render's, check Render's current free-tier terms): free web services sleep after a period of inactivity and take a while to wake, and the app starts from empty each time (about 12 seconds locally to migrate, train and seed). Anything uploaded, any users the admin created, and review decisions are lost on each restart; the admin account and the 14 demo documents come back. The `JWT_SECRET` stays the same, so an old browser session simply gets a 401 and asks you to sign in again.

Design choices (both files):
- **Registration is off** (`ENABLE_REGISTRATION=false`). Only the admin can create accounts.
- **Production mode:** no `/docs` and no `/openapi.json`; a weak or default `JWT_SECRET` stops the app from starting.
- **`CORS_ORIGINS`** allows only the Vercel URL. If you use another domain, change it.
- The data directory is created and handed to an unprivileged user at start-up; the app does not run as root.
- Paid file only: one persistent disk at `/var/data` for the SQLite database, uploads, vectors and model, which needs a single instance.

**Cost** (approximate, from a web search of Render's pricing; check render.com/pricing): the free file costs nothing. The paid file's `0.5c-512mb` web service is about $7 per month plus about $0.25 per month for the 1 GB disk. Measured locally: migrate + train + seed peaked at about 220 MB and the running API used about 180-235 MB, so 512 MB fits, but a large upload could need a bigger plan.

## 2. Web interface on Vercel
The project `infomind-ai-enterprise` is already linked to the GitHub repo (root directory `frontend`) and redeploys on every push to `main`.
1. In Vercel: **Project, Settings, Environment Variables**, add `VITE_API_BASE` = `https://<your-service>.onrender.com/api/v1` for *Production*. (Or `vercel env add VITE_API_BASE production` from the repo root.)
2. Redeploy (push a commit or use **Deployments, Redeploy**). The variable is read at build time.
3. Open the Vercel URL and sign in with the admin you chose in step 1.

## Checks and limits
- A newly started or woken instance can be slow on the first request.
- Everything is served over HTTPS by the hosts, but this prototype keeps the JWT in browser storage, has an in-process rate limiter and has no malware scanning of uploads (see SECURITY.md).
- Paid file: back up `/var/data` (Render disk snapshots) if the data matters.
- Verified locally by running the production image with the same variables as each blueprint (free: no disk, state under `/tmp`; paid: a root-owned volume): migration, admin creation, training, seeding, sign-in, closed registration, hidden docs, CORS for the Vercel origin only, and (paid) persistence across a redeploy. Both blueprints were also checked with Render's server-side validator. **The service itself has not been created or run on Render yet.**
- Troubleshooting: `need_payment_info` on a Blueprint means a paid plan was requested without a card on the account; use the default `render.yaml`.
