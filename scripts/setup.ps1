# One-time setup on Windows (PowerShell):  .\scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\backend"
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created backend\.env - edit JWT_SECRET and the admin password." }
Pop-Location
Push-Location "$root\frontend"
npm install
Pop-Location
Write-Host "Done. Next: install Ollama (https://ollama.com), then run .\scripts\pull-models.ps1"
