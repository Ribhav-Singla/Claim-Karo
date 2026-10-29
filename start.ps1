# Starts everything: Postgres + CloudBeaver + LiveKit (Docker), FastAPI backend, the LiveKit
# voice agent, and the Next.js frontend.
# Every start wipes the database; the backend then recreates the tables and reseeds them.
# Usage: .\start.ps1             fresh database every time
#        .\start.ps1 -KeepData   keep sessions and claims from earlier runs
#        (stop with .\stop.ps1)
param([switch]$KeepData)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$api = Join-Path $root "api"
$web = Join-Path $root "web"
$pidFile = Join-Path $root ".pids"

if (Test-Path $pidFile) {
    Write-Host "Already running (found .pids). Run .\stop.ps1 first." -ForegroundColor Yellow
    exit 1
}

# 1. Docker: Postgres + CloudBeaver + LiveKit media server
Write-Host "Starting Postgres, CloudBeaver and LiveKit..." -ForegroundColor Cyan
docker compose -f (Join-Path $root "docker-compose.yml") up -d --wait postgres cloudbeaver livekit
if ($LASTEXITCODE -ne 0) { throw "docker compose failed. Is Docker Desktop running?" }

# Fresh data: drop every table. The backend applies db/schema.sql and copies data/*.json
# back in when it starts (step 4), so this only has to empty the database.
if ($KeepData) {
    Write-Host "Keeping existing data (-KeepData)." -ForegroundColor Yellow
} else {
    Write-Host "Deleting old data..." -ForegroundColor Cyan
    docker compose -f (Join-Path $root "docker-compose.yml") exec -T postgres `
        psql -v ON_ERROR_STOP=1 -q -U claimkaro -d claim_karo `
        -c "SET client_min_messages = warning; DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    if ($LASTEXITCODE -ne 0) { throw "Could not reset the database." }
}

# 2. First-run setup
if (-not (Test-Path (Join-Path $api ".env"))) {
    Copy-Item (Join-Path $api ".env.example") (Join-Path $api ".env")
    Write-Host "Created api\.env - add your ANTHROPIC_API_KEY and SARVAM_API_KEY." -ForegroundColor Yellow
}
$python = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating Python venv..." -ForegroundColor Cyan
    py -3.13 -m venv (Join-Path $api ".venv")
}
# Also covers venvs created before the LiveKit agent existed.
& $python -c "import livekit.agents" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend packages..." -ForegroundColor Cyan
    & $python -m pip install -q -r (Join-Path $api "requirements.txt")
    # turn-detector and VAD model weights, so the first call doesn't wait for a download
    Push-Location $api; & $python -m livekit.agents download-files; Pop-Location
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

# 4. Backend, voice agent and frontend, each in its own window so logs stay visible.
#    The backend creates the tables and seeds users, vehicles, policies and documents on startup.
$backend = Start-Process powershell -PassThru -WorkingDirectory $api -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo API'; & '$python' -m uvicorn main:app --reload --port 8000"
)
$agent = Start-Process powershell -PassThru -WorkingDirectory $api -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo Agent'; & '$python' -m agent.claim_agent dev"
)
$frontend = Start-Process powershell -PassThru -WorkingDirectory $web -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo Web'; npm run start"
)
"$($backend.Id)`n$($agent.Id)`n$($frontend.Id)" | Set-Content $pidFile

Write-Host ""
Write-Host "Claim Karo is starting:" -ForegroundColor Green
Write-Host "  App          http://localhost:3000"
Write-Host "  API          http://localhost:8000"
Write-Host "  LiveKit      ws://localhost:7880  (dev keys devkey / secret; voice agent 'claim-karo')"
Write-Host "  CloudBeaver  http://localhost:8978  (connection 'Claim Karo (Postgres)'; admin cbadmin / ClaimKaro123)"
Write-Host "  Postgres     localhost:5433  db claim_karo  user claimkaro / claimkaro"
Write-Host "Stop everything with .\stop.ps1"
