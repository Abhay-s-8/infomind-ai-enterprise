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
| `render.yaml` (default) | **No** (validated: accepted) | Free web service + Render's free PostgreSQL: the database persists (until it expires, see below); original files and the vector index reset on every restart | A free, working demo with persistent users and documents |
| `render.paid.yaml` | **Yes**: without a payment method Render rejects it with `need_payment_info` | Everything persists on a 1 GB disk | Durable data, no expiry |

1. In your Render project choose **New, then Blueprint**, connect GitHub and select `Abhay-s-8/infomind-ai-enterprise`, branch `main`. (For the paid file, set the Blueprint file path to `render.paid.yaml` after adding a payment method under Account Settings, Billing.)
2. When prompted, enter `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` (at least 10 characters; use a **new** password). `JWT_SECRET` is generated for you.
3. Check the plan on the review screen, then apply. The first build takes several minutes.
4. When the service is live, open `https://<your-service>.onrender.com/api/v1/health`; it should return `{"status":"ok"}`. The service name `infomind-api` must be free on Render; otherwise Render adds a suffix to the address.

On every start the container runs the database migration, creates the admin if it does not exist, trains the classifier if none is active (`AUTO_TRAIN`) and adds the synthetic demo documents (`SEED_DEMO`). All are safe to repeat. Set `SEED_DEMO` to `false` for real use.

**What the free variant means in practice.** Render's terms for free services (from render.com/docs/free): a free web service spins down after 15 minutes without traffic and takes about a minute to start again; it gets 750 free instance hours per month; its filesystem is lost on every restart, redeploy or spin-down. A free PostgreSQL database holds 1 GB, has no backups, **expires 30 days after creation and is deleted after a further 14-day grace period**; only one free database is allowed per workspace.

| Survives a restart (in the database) | Lost on every restart |
|---|---|
| Users and roles, documents and their extracted text, classifications, reviews, entities, analytics, audit log, conversations | The original uploaded file (download answers "missing", reprocess answers 409 "upload it again"); the trained model file (retrained at start, one extra model version each time) |

The vector index also lives on temporary storage, so `start.sh` rebuilds it from the stored text at every start (`AUTO_REINDEX`, `python -m app.cli reindex --if-needed`); search keeps working. Verified locally against a real PostgreSQL by discarding the container and starting a new one on the same database.

**The database expiry is the catch.** The database created for this deployment expires on **2026-11-27** (Render emails you before that). If it is deleted the API stops starting, because the migration cannot connect. To recover on the free plan: delete the expired database, create a new free one (same name, `render.yaml` does this), and update the service's `DATABASE_URL`; the data in it is lost (there are no backups). Upgrading the database to a paid plan in the Render dashboard before the end of the grace period keeps it. The `JWT_SECRET` is stable, so browser sessions survive restarts.

Design choices (both files):
- **Registration is off** (`ENABLE_REGISTRATION=false`). Only the admin can create accounts.
- **Production mode:** no `/docs` and no `/openapi.json`; a weak or default `JWT_SECRET` stops the app from starting.
- **`CORS_ORIGINS`** allows only the Vercel URL. If you use another domain, change it.
- The data directory is created and handed to an unprivileged user at start-up; the app does not run as root.
- Paid file only: one persistent disk at `/var/data` for the SQLite database, uploads, vectors and model, which needs a single instance.

**Cost** (approximate, from a web search of Render's pricing; check render.com/pricing): the free file costs nothing (no card). The paid file's `0.5c-512mb` web service is about $7 per month plus about $0.25 per month for the 1 GB disk. Measured locally: migrate + train + seed peaked at about 220 MB and the running API used about 180-235 MB, so 512 MB fits, but a large upload could need a bigger plan.

## Optional: bring the AI assistant online with Ollama's hosted cloud (no computer of yours needs to stay on)
Ollama also serves open-weight models from its own servers through the same API, so the hosted API can use them directly:
`hosted API -> https://ollama.com`. The hosted API sends your key as `Authorization: Bearer <key>` (`OLLAMA_API_KEY`).

1. Create an Ollama account and an API key at https://ollama.com/settings/keys. Check https://ollama.com/settings/usage for what your plan includes: at the time of writing Ollama's pricing page describes the free plan as "a small amount of monthly usage for a set of starter models" (the amount is not published there) and says other models need pay-as-you-go usage credits, priced per token (rates are on each model's page; whether a card is needed is not stated on the pages read). **Check the cost before relying on it.**
2. Pick a model and test it from your own terminal (the key stays in your terminal, never in a file or the repository):
   ```powershell
   cd backend
   $env:OLLAMA_BASE_URL = "https://ollama.com"; $env:OLLAMA_API_KEY = "<your key>"
   .\.venv\Scripts\python -m app.cli check-llm --list      # lists the model names this account can use
   $env:OLLAMA_LLM_MODEL = "<a name from the list>"
   .\.venv\Scripts\python -m app.cli check-llm             # one small JSON request; says whether the assistant can use it
   ```
   `check-llm` reports the first-text delay and whether the reply is valid JSON (the assistant requires it). It never prints the key. A model that produces only hidden reasoning (no answer text) fails the check.
3. Optional but recommended: measure answer quality with that model, as for the local models: `python -m app.cli evaluate` with the same three settings in the terminal. No cloud model has been evaluated with this application yet.
4. In the Render dashboard (service, Environment) set `OLLAMA_BASE_URL=https://ollama.com`, `OLLAMA_API_KEY` and `OLLAMA_LLM_MODEL`; leave `EMBEDDING_PROVIDER=hash` (only the language model is remote). Redeploy, because settings are read at start-up.

What to expect, honestly:
- Observed on 2026-10-29 with one account: `beam` worked (valid JSON, see EVALUATION.md); `gpt-oss:20b` and `gemma4:31b` returned HTTP 402 (credits required). Plans and models change, so run `check-llm` yourself.
- Always on; no tunnel or home computer involved. The free API still sleeps when idle and takes about a minute to wake.
- **Your documents' passages leave your machine** for every question. Ollama's pricing page states that prompt and response data is never logged or trained on and that hosting partners must not log or retain it; this is the provider's statement, not something verified here.
- Usage is metered by Ollama; a busy public demo could use up a free allowance. Watch https://ollama.com/settings/usage.
- Model names and availability change; rerun `check-llm --list` if the assistant reports Ollama is unreachable.
- The key sits in the hosted API's environment settings; anyone who learns it can spend your allowance. Revoke it at https://ollama.com/settings/keys if it leaks.

## Optional: bring the AI assistant online through a tunnel to your own computer
The hosted API cannot run Ollama, but it can use the Ollama on **your computer** while that computer is on. The path is
`hosted API -> https tunnel -> gateway on your PC -> Ollama`. Ollama has no login of its own, so it is never exposed directly:
the gateway (`backend/app/gateway.py`) listens on the loopback address only, requires `Authorization: Bearer <key>` on every request,
forwards **only** chat, embed and list-models calls (pull, delete, create and everything else are refused even with the key),
and caps request size and rate. The hosted API sends the key from `OLLAMA_API_KEY`.

1. Install the tunnel program once: `winget install Cloudflare.cloudflared` (a free "quick tunnel" needs no Cloudflare account).
2. On your PC run `.\scripts\ollama-tunnel.ps1`. On first use it creates the key in `%USERPROFILE%\.infomind\ollama-gateway.key` (outside the repository), starts the gateway, starts the tunnel and prints the tunnel address. Keep that window open. `.\scripts\ollama-tunnel.ps1 -ShowKey` prints the key once, to paste into the hosted API's settings; `-SelfTest` checks the gateway without a tunnel.
3. In the Render dashboard (service, Environment) set `OLLAMA_BASE_URL` to the printed `https://....trycloudflare.com` address, `OLLAMA_API_KEY` to the key, and `OLLAMA_LLM_MODEL=llama3.1:8b`; leave `EMBEDDING_PROVIDER=hash` (only the language model is remote). Redeploy, because the settings are read at start-up.
4. Settings in the web app should now show the language model as available. Ask a question on the AI Assistant page.

What to expect, honestly:
- The assistant works **only while your PC, Ollama and the tunnel are running**. Otherwise the page says Ollama is not reachable, as before.
- A quick tunnel gets a **new address every time it restarts**, so the setting must be changed and the API redeployed each time. A stable address needs a named Cloudflare tunnel on a domain you control.
- A redeploy of the free API wipes its temporary disk (see above), so the classifier is retrained at start-up.
- The first answer after Ollama has been idle takes about 10 to 12 seconds while the model loads (measured locally with `llama3.1:8b`); this is not measured through the tunnel.
- Setting `OLLAMA_API_KEY` together with a plain `http://` address to a remote host is refused in production, so the key is never sent unencrypted.
- Your documents' passages travel through the tunnel to your PC for each question; Cloudflare's network carries that traffic.
- Anyone who learns the key can use your GPU through the tunnel. Treat it like a password; delete `%USERPROFILE%\.infomind\ollama-gateway.key` and rerun the script to rotate it.

## 2. Web interface on Vercel
The project `infomind-ai-enterprise` is already linked to the GitHub repo (root directory `frontend`) and redeploys on every push to `main`.
1. In Vercel: **Project, Settings, Environment Variables**, add `VITE_API_BASE` = `https://<your-service>.onrender.com/api/v1` for *Production*. (Or `vercel env add VITE_API_BASE production` from the repo root.)
2. Redeploy (push a commit or use **Deployments, Redeploy**). The variable is read at build time.
3. Open the Vercel URL and sign in with the admin you chose in step 1.

## Checks and limits
- A newly started or woken instance can be slow on the first request.
- Everything is served over HTTPS by the hosts, but this prototype keeps the JWT in browser storage, has an in-process rate limiter and has no malware scanning of uploads (see SECURITY.md).
- Paid file: back up `/var/data` (Render disk snapshots) if the data matters.
- Verified locally by running the production image with the same variables as each blueprint (free: no disk, state under `/tmp`; paid: a root-owned volume): migration, admin creation, training, seeding, sign-in, closed registration, hidden docs, CORS for the Vercel origin only, and (paid) persistence across a redeploy. Both blueprints were also checked with Render's server-side validator. The free blueprint has since been deployed: the API runs on Render and the web interface on Vercel, with a restart test of the database-backed state.
- Troubleshooting: `need_payment_info` on a Blueprint means a paid plan was requested without a card on the account; use the default `render.yaml`.
