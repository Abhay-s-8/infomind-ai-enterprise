# Starts API (with in-process worker) and the frontend in two windows. Stop with Ctrl+C in each.
$root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\backend'; .\.venv\Scripts\python -m alembic upgrade head; .\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\frontend'; npm run dev"
Write-Host "Frontend: http://localhost:5173   API docs: http://localhost:8000/docs"
