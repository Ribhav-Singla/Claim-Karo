#!/usr/bin/env bash
set -Eeuo pipefail

# Stops the macOS processes started by start.sh.
# Usage:
#   ./stop.sh         Stop services and keep database data
#   ./stop.sh --reset Stop services and delete database volumes

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.pids"
COMPOSE_FILE="$ROOT/docker-compose.yml"

if [[ "${1:-}" != "" && "${1:-}" != "--reset" ]]; then
    echo "Usage: $0 [--reset]" >&2
    exit 2
fi

if [[ -f "$PID_FILE" ]]; then
    while IFS= read -r pid; do
        if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    echo "Stopped backend, voice agent and frontend."
else
    echo "No .pids file: backend/agent/frontend not started by start.sh."
fi

if [[ "${1:-}" == "--reset" ]]; then
    docker compose -f "$COMPOSE_FILE" down -v
    echo "Stopped containers and deleted volumes."
else
    docker compose -f "$COMPOSE_FILE" down
    echo "Stopped containers (data kept)."
fi
