# Convenience targets (use Git Bash/WSL make). Windows users can use scripts\*.ps1 instead.
PY=backend/.venv/Scripts/python
setup: ; powershell -File scripts/setup.ps1
test: ; cd backend && ../$(PY) -m ruff check app && ../$(PY) -m pytest && cd ../frontend && npm run typecheck && npm test
train: ; cd backend && ../$(PY) -m app.cli train
seed: ; cd backend && ../$(PY) -m app.cli seed-demo
evaluate: ; cd backend && ../$(PY) -m app.cli evaluate
up: ; docker compose up --build -d
down: ; docker compose down
