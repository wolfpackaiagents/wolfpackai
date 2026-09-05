#!/usr/bin/env bash
# Starts the Wolfpack Control Plane (AMP) with uv.
# Infra (postgres, qdrant, minio, redis) via docker-compose + FastAPI backend + seed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
COMPOSE="$ROOT/../docker/docker-compose.yml"

echo "▶ Wolfpack Control Plane (AMP)"
echo "  env: ${WOLFPACK_ENV:-development}"

# 1. Infra (docker-compose)
if command -v docker >/dev/null 2>&1; then
  echo "▶ Starting infra (postgres/redis/minio/qdrant/prometheus)..."
  docker compose -f "$COMPOSE" up -d postgres redis minio qdrant redis-exporter prometheus
else
  echo "⚠ docker not found; assuming services are already running."
fi

# 2. Backend dependencies (uv sync)
echo "▶ Syncing backend dependencies (uv)..."
uv --directory "$BACKEND" sync --extra test --group dev

# 3. Schema migration (Alembic)
echo "▶ Applying migrations (Alembic)..."
uv --directory "$BACKEND" run alembic upgrade head
echo "✔ Migrations applied successfully."

# 4. Backend (FastAPI + uvicorn)
echo "▶ Starting API (uvicorn on :8000)..."
exec uv --directory "$BACKEND" run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
