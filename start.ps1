# Starts everything: Postgres + CloudBeaver (Docker), FastAPI backend, Next.js frontend.
# Usage: .\start.ps1        (stop with .\stop.ps1)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$api = Join-Path $root "api"
$web = Join-Path $root "web"
$pidFile = Join-Path $root ".pids"

if (Test-Path $pidFile) {
    Write-Host "Already running (found .pids). Run .\stop.ps1 first." -ForegroundColor Yellow
    exit 1
}

# 1. Docker: Postgres + CloudBeaver
Write-Host "Starting Postgres and CloudBeaver..." -ForegroundColor Cyan
docker compose -f (Join-Path $root "docker-compose.yml") up -d --wait postgres cloudbeaver
if ($LASTEXITCODE -ne 0) { throw "docker compose failed. Is Docker Desktop running?" }

# 2. First-run setup
if (-not (Test-Path (Join-Path $api ".env"))) {
    Copy-Item (Join-Path $api ".env.example") (Join-Path $api ".env")
    Write-Host "Created api\.env - add your ANTHROPIC_API_KEY and SARVAM_API_KEY." -ForegroundColor Yellow
}
$python = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating Python venv..." -ForegroundColor Cyan
    py -3.13 -m venv (Join-Path $api ".venv")
    & $python -m pip install -q -r (Join-Path $api "requirements.txt")
}
if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Write-Host "Installing frontend packages..." -ForegroundColor Cyan
    Push-Location $web; npm install; Pop-Location
}

# 3. Production build of the frontend (NEXT_PUBLIC_* env vars are baked in here)
Write-Host "Building frontend..." -ForegroundColor Cyan
Push-Location $web
npm run build
$buildExit = $LASTEXITCODE
Pop-Location
if ($buildExit -ne 0) { throw "Frontend build failed. Fix the errors above and run .\start.ps1 again." }

# 4. Backend and frontend, each in its own window so logs stay visible
$backend = Start-Process powershell -PassThru -WorkingDirectory $api -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo API'; & '$python' -m uvicorn main:app --reload --port 8000"
)
$frontend = Start-Process powershell -PassThru -WorkingDirectory $web -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo Web'; npm run start"
)
"$($backend.Id)`n$($frontend.Id)" | Set-Content $pidFile

Write-Host ""
Write-Host "Claim Karo is starting:" -ForegroundColor Green
Write-Host "  App          http://localhost:3000"
Write-Host "  API          http://localhost:8000  (WebSocket /ws)"
Write-Host "  CloudBeaver  http://localhost:8978  (connection 'Claim Karo (Postgres)'; admin cbadmin / ClaimKaro123)"
Write-Host "  Postgres     localhost:5433  db claim_karo  user claimkaro / claimkaro"
Write-Host "Stop everything with .\stop.ps1"
