$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\backend"; .\.venv\Scripts\python -m ruff check app; .\.venv\Scripts\python -m pytest; Pop-Location
Push-Location "$root\frontend"; npm run typecheck; npm test; Pop-Location
