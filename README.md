# Wolfpack AI

Framework Python de criação de agentes de IA com observabilidade enterprise embutida
e um Control Plane (AMP) para monitorar, inspecionar e escalar agentes e times de
agentes em produção.

```
framework/     # wolfpack: framework Python de agentes (pip/uv)
control-plane/ # AMP: backend FastAPI + frontend React (dashboard de traces)
docker/        # docker-compose: postgres, redis, minio, qdrant, inngest
docs/          # plano de implantação e arquitetura
```

## O que vem do framework

- **Agent** com loop de tool-calling: `Agent(model=..., tools=[...]).run(msg)`.
- **Tools tipadas**: decorator `@tool` com schema JSON inferido de type hints + docstring.
- **Knowledge/RAG**: `Knowledge` com chunking e `VectorDb` (Qdrant, PGVector, memória).
- **Models multi-provedor**: OpenAI, Anthropic, Gemini, Ollama, Groq (OpenAILike).
- **Observabilidade nativa**: cada run emite spans OpenTelemetry `gen_ai.*` via um
  `Tracker` plugável. Por padrão envia ao Control Plane (AMP) se `WOLFPACK_AMP_URL` estiver set.

## Começar com o framework

```bash
cd framework
uv sync --extra test --group dev
```

Exemplos 100% funcionais, organizados por tema em `framework/examples/` (ver
`framework/examples/README.md`):

```bash
# minimal + streaming + memória
uv run python examples/01_basic/01_hello_agent.py
uv run python examples/01_basic/03_stream_events.py

# tool-calling (multi-provedor: openai | anthropic | ollama)
uv run python examples/02_tools/03_multi_provider.py "anthropic:claude-haiku-4-5"

# RAG com embeddings reais
uv run python examples/03_rag/01_rag_memory.py

# observabilidade -> Control Plane
uv run python examples/05_observability/02_amp_observer.py
```

```python
from wolfpack import Agent, tool, get_model_from_env

@tool
def get_weather(city: str) -> str:
    """Obtém o clima de uma cidade.
    Args:
        city: nome da cidade.
    """
    return f"{city}: 22°C, nublado."

agent = Agent(
    name="Assistente",
    model=get_model_from_env(),
    tools=[get_weather],
)
out = agent.run("Como está em Lisboa?")
print(out.content, out.usage)
```

## Observabilidade -> Control Plane

Defina o tracker para enviar cada run ao AMP:

```bash
export WOLFPACK_AMP_URL=http://localhost:8000
export WOLFPACK_AMP_API_KEY="pk-...:secret"
```

`create_tracker()` então devolve o `WolfpackObserver` automático; cada agent `run()`
envia traço/span (trace, steps, LLM calls, tools, uso de tokens) para o AMP.

Ver `framework/examples/05_observability/02_amp_observer.py` (exemplo real).

## Control Plane

```bash
# infra + backend
cd control-plane
./run.sh        # docker compose infra + alembic + uvicorn :8000
./stop.sh       # derruba tudo

# frontend
cd control-plane/frontend
npm install
npm run dev     # http://localhost:5173 (proxy para :8000)
```

A UI é **bilíngue (inglês/pt-BR)** via react-i18next: idioma detectado do navegador
e trocável no seletor do topo (persistido em localStorage).

Login com uma API key (default dev: `pk-wp-dev:dev-secret`). Crie org/project/chave
via `Admin` endpoints (`X-Admin-Key: dev-admin-key-change-me` por padrão).

### Endpoints principais (backend :8000)

- `POST /api/public/ingestion`  (HTTP 202, async job; contrato langfuse-like)
- `GET  /api/public/traces`     (listar runs; filtro por name/env/session)
- `GET  /api/public/traces/{id}`(detalhe com árvore de spans + usage/cost)
- `GET  /api/public/metrics`    (count, p50/p95, tokens, cost)
- `POST /admin/organizations|projects|api-keys`

## Estrutura de pacotes (framework)

```
wolfpack/
  agent/        # Agent, run loop, eventos de streaming, Protocol
  models/       # BaseModel, OpenAI/Anthropic/Gemini(OpenAILike), utils
  tools/        # Function, FunctionCall, Toolkit, @tool, factory RAG
  knowledge/    # Knowledge (chunking, readers), embeddings
  vectordb/     # VectorDb (Memory/Qdrant/PGVector), embeddings
  memory/       # session memory (MVP), store
  telemetry/    # Tracker OTel + create_tracker() plugável
  observer/     # WolfpackObserver -> AMP ingestion
  team/         # (fase 2) orquestração multi-agente
```

## Roadmap (fases)

1. ✅ Core: agent/tools/RAG, models multi-provedor, telemetría OTel.
2. ✅ AMP backend: FastAPI, ingestion, trace storage Postgres, Alembic, seed.
3. ✅ AMP frontend: dashboard/metrics, trace explorer com span tree.
4. ✅ HITL durável, guardrails PII/prompt-injection/allowlist, saída estruturada.
5. ✅ Memória persistida SQLite, workflows DAG, team multi-agente, evals, schedules.
6. ⏳ Chat gateway, MCP client, AMP enterprise (RBAC, retenção, titular), ClickHouse.

Documentação detalhada: `docs/PLAN_IMPLANTACAO.md`.