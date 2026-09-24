# Project Instructions: Wolfpack AI

Monorepo with three deliverables: the `wolfpackai` Python framework, the AMP
(Agent Management Platform) control plane, and the documentation website.

## Tech Stack

| Area | Stack |
|---|---|
| Framework (`framework/`) | Python 3.10+, Pydantic v2, OpenTelemetry, uv, setuptools |
| Providers | OpenAI, Anthropic, Google GenAI, any OpenAI-compatible endpoint |
| Backend (`control-plane/backend/`) | FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Redis, ClickHouse (optional) |
| Frontend (`control-plane/frontend/`) | React 18, TypeScript, Vite, Tailwind, Zustand, Recharts, i18next, Playwright |
| Website (`website/`) | Vite, React, TypeScript, deployed to Netlify |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

## Build & Run

```bash
# Framework
cd framework && uv sync --extra test --group dev && uv run pytest

# Control plane: infra + migrations + API on :8000
cd control-plane && ./run.sh

# Backend tests (workers off, seed off)
cd control-plane/backend && uv run pytest

# Frontend
cd control-plane/frontend && npm install && npm run dev
npm run lint && npm run build
npm run e2e          # reseeds demo data, then Playwright

# Website
cd website && npm ci && npm run build
```

CI runs exactly four jobs: framework pytest, backend pytest, frontend lint plus
build, website build. Keep all four green.

## Project Structure

```
framework/wolfpack/     Published package (import name is `wolfpack`)
  agent/                Agent dataclass, run loop, events, Skill
  models/               Provider adapters, ModelRouter, message/response types
  tools/                @tool decorator, Function, Toolkit, JSON Schema builder
  telemetry/ observer/  Tracker contract, OTel tracker, AMP observer client
  guardrails/ run/      PII, prompt injection, allowlist; HITL requirements and approval stores
  knowledge/ vectordb/  RAG readers, embeddings, vector store adapters
  memory/ workflow/ team/ evals/ schedules/ channels/ data/ coding/ mcp/
framework/examples/     Numbered, runnable examples per capability
control-plane/backend/  FastAPI app: app/routes, app/services, app/models, alembic/
control-plane/frontend/ AMP web interface (English and Brazilian Portuguese)
docker/                 Compose files for development, staging, production
website/                Documentation site
paper/                  Academic manuscript, built with Pandoc
```

## Conventions

- Module docstrings explain the design intent and cite the borrowed pattern.
  Keep that habit when adding modules.
- Public API is curated by hand in `framework/wolfpack/__init__.py`. Any new
  exported symbol goes in both the imports and `__all__`.
- Agent configuration uses `@dataclass` fields, not constructor arguments.
- `from __future__ import annotations` at the top of every Python module.
- Errors surface explicitly. Telemetry paths are the exception: the observer
  buffers and never breaks a run when the backend is unreachable.
- Tests: `framework/tests/test_<area>.py` and
  `control-plane/backend/tests/test_<area>.py`, pytest with `pytest-asyncio`.
  `framework/tests/fake_model.py` provides the deterministic model used to test
  agent behavior without provider calls.
- Frontend files are PascalCase for components (`src/pages`, `src/components`),
  camelCase for stores and libraries. Every user-facing string goes through
  i18next (`src/i18n/en.json` and `src/i18n/ptBR.json`).
- Commits: imperative, capitalized, no prefix. Examples: `Add model routing
  documentation`, `Release 0.2.2`. Work happens on `main`.

## Database Changes

Every schema change needs an Alembic revision in
`control-plane/backend/alembic/versions/`, numbered sequentially (`00NN_name.py`).
`control-plane/backend/tests/test_migrations.py` checks the chain, so do not
leave branch points unmerged.

## Observability Contract

The framework emits OpenTelemetry spans with GenAI (Generative Artificial
Intelligence) semantic conventions. `create_tracker()` picks the backend by
environment: `WOLFPACK_AMP_URL` sends to AMP, `WOLFPACK_TRACER=otel` uses the
OpenTelemetry SDK, otherwise it is a no-op. The ingestion contract in
`control-plane/backend/app/schemas/contract.py` is deliberately tolerant, so
changing span attributes on the framework side does not require a backend
change, but span type and cost fields must stay in sync.

## Versions

`framework/pyproject.toml` version drives the PyPI (Python Package Index)
release. Backend version lives in `control-plane/backend/pyproject.toml`, which
depends on the framework as an editable local path.
