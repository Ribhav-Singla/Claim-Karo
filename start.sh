#!/usr/bin/env bash
set -Eeuo pipefail

# Starts the local Claim Karo stack on macOS (including Apple Silicon).
# Usage:
#   ./start.sh             Reset the database before starting
#   ./start.sh --keep-data Keep existing database data

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API="$ROOT/api"
WEB="$ROOT/web"
PID_FILE="$ROOT/.pids"
LOG_DIR="$ROOT/logs"
COMPOSE_FILE="$ROOT/docker-compose.yml"
KEEP_DATA=false

if [[ "${1:-}" == "--keep-data" ]]; then
    KEEP_DATA=true
elif [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--keep-data]" >&2
    exit 2
fi

if [[ -f "$PID_FILE" ]]; then
    echo "Already running (found .pids). Run ./stop.sh first." >&2
    exit 1
fi

command -v docker >/dev/null || { echo "Docker is required. Start Docker Desktop and try again." >&2; exit 1; }
command -v npm >/dev/null || { echo "Node.js and npm are required." >&2; exit 1; }

if command -v python3.13 >/dev/null; then
    PYTHON="$(command -v python3.13)"
elif command -v python3 >/dev/null; then
    PYTHON="$(command -v python3)"
else
    echo "Python 3.11+ is required." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "Python 3.11+ is required (found $("$PYTHON" --version))." >&2
    exit 1
fi

echo "Starting Postgres, CloudBeaver and LiveKit..."
docker compose -f "$COMPOSE_FILE" up -d --wait postgres cloudbeaver livekit

if [[ "$KEEP_DATA" == true ]]; then
    echo "Keeping existing data (--keep-data)."
else
    echo "Deleting old data..."
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -v ON_ERROR_STOP=1 -q -U claimkaro -d claim_karo \
        -c "SET client_min_messages = warning; DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
fi

if [[ ! -f "$API/.env" ]]; then
    cp "$API/.env.example" "$API/.env"
    echo "Created api/.env - add your ANTHROPIC_API_KEY and SARVAM_API_KEY."
fi

VENV="$API/.venv"
PYTHON_BIN="$VENV/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Creating Python virtual environment..."
    "$PYTHON" -m venv "$VENV"
fi

if ! "$PYTHON_BIN" -c 'import livekit.agents' >/dev/null 2>&1; then
    echo "Installing backend packages..."
    "$PYTHON_BIN" -m pip install -q -r "$API/requirements.txt"
    (cd "$API" && "$PYTHON_BIN" -m livekit.agents download-files)
fi

if [[ ! -d "$WEB/node_modules" ]]; then
    echo "Installing frontend packages..."
    (cd "$WEB" && npm install)
fi

echo "Building frontend..."
(cd "$WEB" && npm run build)

mkdir -p "$LOG_DIR"

(cd "$API" && exec nohup "$PYTHON_BIN" -m uvicorn main:app --reload --port 8000) \
    >"$LOG_DIR/api.log" 2>&1 &
BACKEND_PID=$!

(cd "$API" && exec nohup "$PYTHON_BIN" -m agent.claim_agent dev) \
    >"$LOG_DIR/agent.log" 2>&1 &
AGENT_PID=$!

(cd "$WEB" && exec nohup npm run start) \
    >"$LOG_DIR/web.log" 2>&1 &
FRONTEND_PID=$!

printf '%s\n' "$BACKEND_PID" "$AGENT_PID" "$FRONTEND_PID" > "$PID_FILE"

echo
echo "Claim Karo is starting:"
echo "  App          http://localhost:3000"
echo "  API          http://localhost:8000"
echo "  LiveKit      ws://localhost:7880  (dev keys devkey / secret; voice agent 'claim-karo')"
echo "  CloudBeaver  http://localhost:8978  (connection 'Claim Karo (Postgres)'; admin cbadmin / ClaimKaro123)"
echo "  Postgres     localhost:5433  db claim_karo  user claimkaro / claimkaro"
echo "  Logs         $LOG_DIR/{api,agent,web}.log"
echo "Stop everything with ./stop.sh"
