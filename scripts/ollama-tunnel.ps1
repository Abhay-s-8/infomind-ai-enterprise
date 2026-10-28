# Makes the Ollama on THIS computer usable by the hosted API, safely.
#   Ollama  <--  gateway (checks a secret key, allows only chat / embed / list-models)  <--  Cloudflare quick tunnel  <--  hosted API
# Keep this window open while you want the hosted AI assistant to work; closing it (or Ctrl+C) stops both programs.
#
#   .\scripts\ollama-tunnel.ps1               start the gateway and a tunnel, print the two settings for the hosted API
#   .\scripts\ollama-tunnel.ps1 -ShowKey      print the key (needed once, to paste into the hosted API's settings)
#   .\scripts\ollama-tunnel.ps1 -SelfTest     start the gateway, check it answers only with the key, stop (no tunnel)
#
# The key is created on first use in %USERPROFILE%\.infomind\ollama-gateway.key, outside the repository.
param(
  [string]$Cloudflared = "",
  [int]$Port = 11435,
  [string]$Upstream = "http://127.0.0.1:11434",
  [switch]$ShowKey,
  [switch]$SelfTest
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$py = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Backend virtual environment not found. Run .\scripts\setup.ps1 first." }

$keyDir = Join-Path $env:USERPROFILE ".infomind"
$keyFile = Join-Path $keyDir "ollama-gateway.key"
if (-not (Test-Path $keyFile)) {
  New-Item -ItemType Directory -Force $keyDir | Out-Null
  $bytes = New-Object byte[] 36
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $new = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=")
  Set-Content -Path $keyFile -Value $new -NoNewline -Encoding ascii
  icacls $keyFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null   # only you can read it
  Write-Host "Created a new gateway key at $keyFile"
}
$key = (Get-Content $keyFile -Raw).Trim()
if ($ShowKey) { Write-Host "OLLAMA_API_KEY=$key"; return }

try { Invoke-RestMethod "$Upstream/api/tags" -TimeoutSec 3 | Out-Null }
catch { throw "Ollama is not answering at $Upstream. Start Ollama first." }

$env:OLLAMA_GATEWAY_KEY = $key
$env:OLLAMA_UPSTREAM = $Upstream
$env:OLLAMA_GATEWAY_PORT = "$Port"
$gateway = Start-Process -FilePath $py -ArgumentList @("-m", "app.gateway") -WorkingDirectory $backend -PassThru -WindowStyle Hidden
$tunnel = $null
try {
  $local = "http://127.0.0.1:$Port"
  $ready = $false
  for ($i = 0; $i -lt 50 -and -not $ready; $i++) {
    Start-Sleep -Milliseconds 200
    try { Invoke-WebRequest "$local/api/tags" -UseBasicParsing -TimeoutSec 2 | Out-Null } catch {
      if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { $ready = $true }
    }
  }
  if (-not $ready) { throw "The gateway did not start on port $Port (is the port already in use?)." }
  $withKey = Invoke-RestMethod "$local/api/tags" -Headers @{ Authorization = "Bearer $key" } -TimeoutSec 5
  Write-Host ("Gateway is up on {0}: {1} model(s) visible, and requests without the key are refused." -f $local, @($withKey.models).Count)
  if ($SelfTest) { return }

  if (-not $Cloudflared) {
    $found = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($found) { $Cloudflared = $found.Source }
  }
  if (-not $Cloudflared -or -not (Test-Path $Cloudflared)) {
    throw "cloudflared was not found. Install it (winget install Cloudflare.cloudflared) or pass -Cloudflared <path to cloudflared.exe>."
  }
  $log = Join-Path $env:TEMP "infomind-cloudflared.log"
  Remove-Item $log -ErrorAction SilentlyContinue
  $tunnel = Start-Process -FilePath $Cloudflared -ArgumentList @("tunnel", "--url", $local, "--no-autoupdate") `
    -RedirectStandardError $log -PassThru -WindowStyle Hidden
  $url = $null
  for ($i = 0; $i -lt 120 -and -not $url; $i++) {
    Start-Sleep -Milliseconds 500
    if ($tunnel.HasExited) { throw "cloudflared stopped. See $log" }
    if (Test-Path $log) {
      $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($m) { $url = $m.Matches[0].Value }
    }
  }
  if (-not $url) { throw "No tunnel address appeared. See $log" }
  Write-Host ""
  Write-Host "Tunnel is up. Set these on the hosted API (Render > service > Environment), then redeploy it:"
  Write-Host "  OLLAMA_BASE_URL=$url"
  Write-Host "  OLLAMA_API_KEY=<the key: run  .\scripts\ollama-tunnel.ps1 -ShowKey>"
  Write-Host "  OLLAMA_LLM_MODEL=llama3.1:8b"
  Write-Host ""
  Write-Host "This address changes every time the tunnel restarts. Press Ctrl+C to stop sharing Ollama."
  while ($true) {
    Start-Sleep -Seconds 5
    if ($gateway.HasExited) { throw "The gateway stopped." }
    if ($tunnel.HasExited) { throw "The tunnel stopped." }
  }
}
finally {
  foreach ($p in @($tunnel, $gateway)) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
  Write-Host "Stopped."
}
