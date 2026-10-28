# Stops what start.ps1 started. Data in Postgres is kept (Docker volume).
# Usage: .\stop.ps1          stop everything
#        .\stop.ps1 -Reset   also delete the database and CloudBeaver volumes
param([switch]$Reset)
$root = $PSScriptRoot
$pidFile = Join-Path $root ".pids"

if (Test-Path $pidFile) {
    foreach ($id in Get-Content $pidFile) {
        if ($id) {
            # /T kills the whole tree (uvicorn reloader, node dev server) started in that window
            taskkill /T /F /PID $id 2>$null | Out-Null
        }
    }
    Remove-Item $pidFile
    Write-Host "Stopped backend and frontend." -ForegroundColor Green
} else {
    Write-Host "No .pids file: backend/frontend not started by start.ps1." -ForegroundColor Yellow
}

$compose = Join-Path $root "docker-compose.yml"
if ($Reset) {
    docker compose -f $compose down -v
    Write-Host "Stopped containers and deleted volumes." -ForegroundColor Green
} else {
    docker compose -f $compose down
    Write-Host "Stopped containers (data kept)." -ForegroundColor Green
}
