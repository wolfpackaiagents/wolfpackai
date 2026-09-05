#!/usr/bin/env bash
# Stops the Wolfpack Control Plane (AMP): backend + infra via docker-compose.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$ROOT/../docker/docker-compose.yml"

echo "▶ Stopping API..."
# kills backend uvicorn / uv run (if running)
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  uvicorn stopped" || echo "  uvicorn was not running"

echo "▶ Shutting down docker infra..."
if command -v docker >/dev/null 2>&1; then
  docker compose -f "$COMPOSE" down
else
  echo "⚠ docker not found."
fi

echo "✔ Control Plane stopped."