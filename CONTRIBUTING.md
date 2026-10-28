# Contributing to InfoMind AI Enterprise

Thank you for considering a contribution. This is an educational, research-oriented prototype, so the most valuable contributions are the ones that make it **more correct, better tested and more honest about what it can do**.

## Ground rules (these are not negotiable)

- **Synthetic or public data only.** Never add real, personal, confidential or classified documents, even as test fixtures.
- **No secrets.** Never commit `.env` files, passwords, tokens or keys. `.env` is git-ignored; only placeholders belong in `.env.example`.
- **No claims the code cannot back up.** Do not describe a feature as working unless it is implemented and tested, and never invent metrics. If you add an evaluation number, say how it was measured. Do not claim military, classified or other certification.
- **Model calls stay behind the backend.** The browser must never talk to Ollama (or any model) directly.
- **The app must still start without Ollama**, and models must never be downloaded automatically.
- Security-sensitive reports (an authorisation bypass, a way to read another user's documents, a prompt-injection bypass): please **do not open a public issue with exploit details**. Use GitHub's private vulnerability reporting on the repository if it is enabled, or contact the maintainer through their GitHub profile.

## Good first contributions

The "Known limitations" and "Future enhancements" sections of the [README](README.md) and [docs/PROJECT_EXPLAINED.md](docs/PROJECT_EXPLAINED.md) are the backlog. Examples:

- More tests for existing behaviour (upload edge cases, search filters, review flows, the streaming parser).
- A better keyword ranking (BM25) or a reranker for hybrid search; see the measured weakness in [docs/EVALUATION.md](docs/EVALUATION.md).
- OCR for scanned PDFs (Tesseract) with a clear fallback when it is not installed.
- Accessibility and small-screen improvements in the web app.
- Documentation fixes that correct something that is actually wrong or unclear.

Please open an issue (or comment on one) before starting anything larger than a small fix, so the approach can be agreed first.

**Quality over quantity.** Pull requests that only change whitespace, rewrite wording without fixing a problem, or are opened just to collect a count (for example during Hacktoberfest) may be closed without merging. A small change that fixes a real problem and has a test is always welcome.

## Setting up

Prerequisites: Python 3.11+ (tested on 3.13), Node 20+ (tested on 22), Git. Ollama and Docker are optional.

On Windows (PowerShell), from the repository root:

```powershell
.\scripts\setup.ps1          # virtual environment, backend and frontend dependencies, creates backend\.env
# edit backend\.env: set JWT_SECRET and DEV_ADMIN_PASSWORD
# for a trial without Ollama also set EMBEDDING_PROVIDER=hash and EMBEDDING_DIMENSIONS=256
cd backend
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m app.cli train
.\.venv\Scripts\python -m app.cli seed-demo
cd ..
.\scripts\dev.ps1            # API on :8000, web app on :5173
```

The full instructions, including Docker and the optional local models, are in the [README](README.md). The data flows are explained with diagrams in [docs/PROJECT_EXPLAINED.md](docs/PROJECT_EXPLAINED.md), and the layout of the code is summarised in section 19 of that file.

## Before you open a pull request

Run the checks. All of them must pass:

```powershell
.\scripts\test.ps1
```

That runs, in order: `ruff check app` and `pytest` in `backend`, then `npm run typecheck` and `npm test` in `frontend`. The tests need no model downloads (they use SQLite, an in-memory Qdrant, a hashing embedder and a scripted fake language model).

- **Add or update tests** for the behaviour you change. A bug fix should include a test that fails without the fix.
- **Match the surrounding code**: naming, comment density and idiom. Backend lint settings are in `backend/ruff.toml` (line length 120). The frontend uses TypeScript strict mode, Tailwind with the colour tokens in `src/styles/index.css`, and TanStack Query for server data.
- **Keep authorisation on the server.** Hiding a button in the web app is a convenience, never a control. New routes need a role check and, for per-document routes, an ownership check (other users get 404).
- **Database changes** need an Alembic migration (`backend/alembic/versions/`) and must work on both PostgreSQL and SQLite.
- **Update the documentation** when behaviour, configuration or the API changes (`README.md`, `docs/`). If you change a diagram's subject, edit its Mermaid source in `docs/diagrams/` and update the picture in `docs/images/`.
- **Do not commit** generated or local files: `.env`, uploaded files, trained model files (`models/*.joblib`), local databases, `node_modules`, virtual environments.

## Commits and pull requests

- Write the commit subject as an imperative sentence in plain English, for example "Skip classification when the model file is missing". Explain the *why* in the body when it is not obvious.
- Keep a pull request to one purpose. Describe what changed, why, and how you tested it (paste the test output summary). Link the issue it addresses.
- Be honest in the description about what you did **not** verify.
- Expect review comments; maintainers may ask for changes or decline a change that does not fit the project's scope.

## Licence

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE) that covers the project.
