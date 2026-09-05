# Wolfpack AI - Plano de Implantação

> Análise profunda dos frameworks de agentes existentes e arquitetura proposta para
> wolfpack-ai (framework Python) + Wolfpack Control Plane (plataforma de observabilidade
> enterprise).

---

## 1. Contexto e Objetivo

Criar um framework Python (`wolfpack-ai`) para codificar agentes de IA complexos que:

- Chamam **tools** tipadas, **vector databases**, **bases de conhecimento** (RAG).
- Permitem montar **times/equipes de agentes** (Workflow / Team / Crew).
- Expõem **observabilidade enterprise** de primeiro nível: toda execução emite traces,
  spans, métricas, logs, errores, custos e latencias, prontos para um control plane.

E a plataforma **Wolfpack Control Plane** (o "AMP" - Agent Management Platform):

- **Tracing & Observability**: monitorar/tracer agentes e workflows em tempo real.
- **Controlled Unified**: plataforma centralizada para gestão, monitoramento e escala.
- **Seamless Integrations**: conecta com sistemas enterprise, data sources, cloud.
- **Advanced Security**: segurança e compliance built-in.
- **Actionable Insights**: analytics e reporting para otimizar performance/decisão.
- **On-premise and Cloud**: deploy docker-compose on-premise ou cloud.

---

## 2. Referentes analizados (branches profundas)

### 2a. agno (ex-phidata) — Python
- **Abstração central**: `Agent`, `Team`, `Workflow`; todos indiretamente implementam
  um `AgentProtocol` mínimo (`run()/arun()`) que retorna `RunOutput` + iterador de eventos.
- **Model loop único**: `Model.response()`/`stream()` é o único lugar onde o loop de
  tool-calling vive (responde, executa tools, munda a lista de mensagens, repete).
- **Tools**: decorator `@tool`, `Toolkit.register`, schema JSON inferido de type hints
  + docstring (GetJSONSchema). Hooks/HITL (`requires_confirmation`, `requires_user_input`).
- **Conhecimiento**: `Knowledge` com readers por tipo de arquivo, estrategias de
  chunking (fixed/recursive/semantic/code), vectordb abstraction (pgvector, qdrant, chroma...).
  RAG tool `create_knowledge_search_tool`.
- **Equipo/Teams**: modos coordinate/route/broadcast/tasks; lider delegate via tool.
- **Observabilidad**: NO inventa tracing próprio; ancla OpenTelemetry/OpenInference.
  Depende do `AgnoInstrumentor` (OpenInference) que convertir a OTel spans. Hub-de-datos.
  preparadores exportables (span exporter).

### 2b. crewAI — Python (times/crew)
- **Abstração**: `Crew` (Pydantic BaseModel) contensemble `tasks` + `agents` + `process`.
  `Agent`, `Task`, `Process(sequential|hierarchical)`, `Flow` gráfico (`@start/@listen/@router`).
- **Execucão agente**: `agent/core.py` + `crew_agent_executor.py`. Native function calling
  vs ReAct text pattern (con uplift parser). max_iter, context-window handling, RPM limiter.
- **Orquestração**: `_execute_tasks`; hierarchical crea un `manager_agent` que delega a
  especialistas via tool `Delegate work to coworker`. `kickoff_for_each` parallel.
- **Memoria**: `Memory` unificado (recency/semantic/importance), backend pluggable
  (lancedb, qdrant, sqlite), recall adaptativo multilevel.
- **Observabilidad**: singletón `CrewAIEventBus` com eventos `emission`+`span-link` (TaskStarted,
  LLMCallStarted, ToolUsageStarted...). Envia a Plus backend/OTel. Hook pluggable via `bus.on`.

### 2c. vercel/ai — TypeScript (agent-v1)
- **Abstraction `Agent`**: contrato minimal `generate()`/`stream()`, implementado por
  `ToolLoopAgent`. Cadastry gover de `StepResult` (paso/paso) con content parts (text,
  reasoning, tool-call, tool-result...).
- **Tools**: sistema de **ToolSet tipado Zod**: `tool()`, `dynamicTool()`, `execute` +
  `outputSchema`. Schemas converts a JSON-schema para provider.
- **Telemetría**: `Telemetry` interface completa (`onStart/onStepStart/onLanguageModelCall/
  onToolExecution/perform...`), `TelemetryDispatcher` (fan-out), registro global. Adapter
  OTEL oficial (`OpenTelemetry` class) con Reporting `gen_ai.*` semantic conventions iç
  span tree: rootSpan→stepSpan→inferenceSpan→toolSpans.
- **Traces**: cada generation tiene `callId` (correlación), `StepResult[]` como ledger
  completo de pasos, `StreamTextPart` unión para replay streaming.

### 2d. langfuse — Observabilidad (AMP)
- **Modelo de datos**: `Trace`, `Observation` (tipo span/generation/event/agent/tool...
  `ObservationType`), `Score` (numeric/boolean/categorical/correction), `TraceSession`,
  versioned `Prompt`. Postgres para identidad/metadata; **ClickHouse (o Postgres)** escrito denso.
- **Ingestion**: routeha `POST /api/public/ingestion` (Sapo, respuesta 207 por evento),
  `POST /api/public/otel/v1/traces` (OTel). Evento `{id, type, timestamp, body}`, dedup por
  `event.id` UUID. Batch max 3.5MB, gzip OTel.
- **Pipeline**: SDK/OTel -> web API -> RedIS IngestiónQueue (worker) -> ClickhouseWriter ->
  CH stores. Postgres holds api_keys, projects, models, score_configs, prompts, sessions.
- **Multi-tenant**: `Project` + `projectId` em toda fila; API keys project-scoped.
- **Métricas**: counts, latencies, tokens, cost, p50/90/99; dimensiones environment/level/name/type.
- **Eval/scoring**: evals async (LLM-as-judge ou code) trigger via worker.
- **Deployment**: docker-compose: langfuse-web, langfuse-worker, clickhouse, minio, redis, postgres.

---

## 3. Decisões de arquitectura para wolfpack-ai

Extraídas de las 4 referencias, adaptadas al stack pedido por el usuario.

### 3.1 Framework Python (`wolfpack`)
Adoptar el "contracto no API" de agno + el modelo de evento de vercel.

1. **`.run()`/`.arun()` como único contrato**, retornando `RunOutput` + iterador
   de eventos de streaming (estilo ToolLoopAgent + agno).
2. **Modelo de mensaje canónico**: roles `system|user|assistant|tool`, con
   `tool_call_id`, `tool_calls`, `reasoning_content`, `references`, `metrics`.
3. **Tools tipadas**: decorador `@tool` + pydantic schema inferido; `Toolkit`;
   FunctionCall executor; policy de falla; HITL (`requires_confirmation`).
4. **Model abstraction**: clase base `Model` con `invoke()/invoke_stream()` + proveedores
   thin (OpenAI, Anthropic, Ollama, OpenAILike). Fallback multi-proveedor.
5. **Conocimiento/RAG**: `Knowledge` con readers+chunking; `VectorDb` abstraction con
   qdrant/pgvector/redis/chroma; hybrid search + reranking.
6. **Equipo multigente**: `Team` con modos coordinate/route/broadcast/tasks + modo
   hierarchical (manager agent con tool de delegación).
7. **Memoria**: session memory + short/long-term/entity, storage pluggable.
8. **Observabilidad nativa (la parte diferenciadora)**: cualquier ejecución del framework
   emite **spans OTel** con convención semántica `gen_ai.*` (como vercel/otel): spans por
   run de agente, paso, LLM call, tool exec, knowledge retrieval, memoria. Se envía via
   `SpanExporter` pluggable (langfuse, langsmith, o el propio wolfpack control plane).

### 3.2 Stack de infraestructura (pedido por usuario)
Usado para el Control Plane y las sanezamieto:

| Componente | Rol | Para qué se usa |
|---|---|---|
| **Postgres** | fuente principal+param, binario | identidad (proyectos, api_keys, modelos, prompts, score_configs, sesiones, evals) + trace store (MVP) |
| **Redis** | colas + cache | rediring del API, eventos de alta performance, rate-limit |
| **MinIO** | object store S3 | diario de eventos (event log durable), media, exports |
| **Qdrant** | vector DB | conocimiento/RAG de los agentes + semejanza (semantic search) |
| **Inngest** | workflow/pipeline async | pipeline de ingestion + evals + jobs (alternativa a BullMQ) |
| **ClickHouse** *(opcional, fase 2)* | columnar hot store | scale traces/observaciones a volumen alto (mirar langfuse) |

**Decisión trace storage (MVP)**: escribimos trazas en **Postgres** (tablas
`traces`, `observations`, `scores` con columnas + JSONB) para iniciar simple con el stack
dado; el diseño deja la puerta a ClickHouse como upgrade cuando el volumen lo exija.
Se define el **modo dual-write** (Postgres now, CH luego) con ádatos.

### 3.3 Control Plane — Backend (FastAPI + Python)
- API REST de ingestion + query + admin con **multi-tenancia** (proyecto).
- **Endpoints de ingestión** estilo langfuse:
  - `POST /api/public/ingestion` (batch, HTTP 207 por evento).
  - `POST /api/public/otel/v1/traces` (OTel/OTLP, gzip).
- Cola: eventos -> Redis/Inngest -> worker -> enriquicia (token count, model match,
  cost, flatten metadata) -> escritura Postgres + MinIO event log.
- **Query API** para traces/observations/scores/metrics con filtros.
- **Auth**: API keys project-scoped (`hashed_secret_key`), JWT admin.
- **Alembic** para migrations + **seed** de datos iniciales (modelos base, score configs).
- **Inngest** orchestrar evals (LLM-judge), retention, exports.

### 3.4 Control Plane — Frontend (React + Vite)
```
Vitе + React (TypeScript) + Tailwind + shadCN/ui + Zustand (estado) + Axios (client) + zod (validacción)
```
Páginas MVP:
1. **Login** - auth admin/proyectos.
2. **Dashboard** - métricas: conteo de runs, latencia p50/p95, tokens, costo, ret/error.
3. **Traces (Runs)** - listado filtrable (proyecto, agente, modelo, fecha, costo).
4. **Trace Detail** - árbol de spans por paso (step→LLM call→tool→memoria), payloads IO,
   prompt, tokens, costo, evaluación.
5. **Agentes/Pistas** - registro de agentes, modelos, tools usadas.
6. **Tools** - biblioteca de tools + esquemas.
7. **Conocimiento** - fuentes, filas, retajes (inventario RAG).
8. **Sesiones** - conversaciones agrupadas por sessionId.
9. **Evals/Scoring** - scores por trazado, configs.
12. Registro de **proyectos**/api_keys (admin).

---

## 4. Arquitectura de paquete (framework Python)

```
wolfpack/                          # framework ejecutable
  agent/
    agent.py          # Agent (dataclass), run()/arun(), dispatch
    protocol.py       # AgentProtocol minimal (run/arun, id, name)
    run.py            # Run (run_dispatch / _run / _run_stream) + RunOptions
    events.py         # tl event taxonomy (RunStarted/Content/Step/Tool/
    session.py        # Session persistence (memory_strategy)
    hooks.py
  models/
    base.py           # Model (ABC): invoke/invoke_stream, response loop
    openai.py, anthropic.py, ollama.py, ...
    fallback.py
    message.py        # Message model, roles
    response.py       # RunOutput, ModelResponseEvent, ToolExecution
  tools/
    function.py       # Function, FunctionCall, execute
    toolkit.py        # Toolkit register
    decorator.py      # @tool
  knowledge/
    knowl
    readers.py        # pdf/docx/md/html reader
    chunking/         # fixed, recursive, semantic
    retriever.py
  vectordb/
    base.py           # insert/upsert/search interface
    qdrant.py, pgvector.py, redis.py, chroma.py ...
  memory/
    manager.py
  team/
    team.py           # coordinate/route/broadcast/tasks
  telemetry/
    otel.py           # GenAI span emitter (gen_ai.*)
    exporters.py      # pluggable: to wolfpack AMP, OTLP, langfuse-compatible
  observer/
    client.py         # send events/spans to Control Plane AMP
```

---

## 5. Fases de implantação (Plan — status pós-implementação)

> Tooling: **uv** (venv + sync por pyproject) em framework/ e control-plane/backend.
> Control plane inicia com `control-plane/run.sh` e para com `control-plane/stop.sh`.

### Fase 0 — Infra & esqueleto ✅
- Estrutura: `framework/`, `control-plane/` (backend+frontend), `docker/`, `docs/`.
- `docker-compose.yml`: postgres (5439), redis (6382), minio (9000/9001), qdrant (6333); ports dedicados para não colidir com outros projetos do host.
- **uv**: `uv sync --extra test --group dev` em ambos os pyprojects; AleMBic inicial.

### Fase 1 — Framework Python core ✅
- `models/` (BaseModel + OpenAI/Anthropic/Gemini + OpenAILike p/ Ollama/Groq; `get_model`).
- `agent/` (contrato `run()`/`stream`, loop de tool-calling com spans por passo).
- `tools/` (`@tool`, Toolkit, FunctionCall, HITL `requires_confirmation`).
- `knowledge/` + `vectordb/` (Memory/Qdrant/PGVector, embeddings OpenAI/Ollama).
- `telemetry/` (Tracker OTel `gen_ai.*`, Noop, `create_tracker` plugável) + `observer/`.
- 10 testes green.

### Fase 2 — Control Plane backend ✅
- FastAPI + SQLAlchemy + Alembic; multi-tenant organizations/projects/api_keys.
- Ingestion `POST /api/public/ingestion` (HTTP 207, FK-safe); query `/traces`, `/traces/{id}`, `/metrics`.
- Admin (org/project/api-key) + seed automático; CORS.
- 5 testes de integração (SQLite/TestClient). **E2E real no Postgres**: agente wolfpack → `WolfpackObserver` → AMP → árvore de spans.

### Fase 3 — Control Plane Frontend ✅
- Vite + React + TS + Tailwind + zustand + axios + recharts; build limpo.
- Login, Dashboard (cards+charts), Traces (filtro/paginação), TraceDetail (span tree + payloads), Settings.

### Fase 4 — Pendente
- Team multi-agente (coordinate/route/broadcast/tasks + manager) e Workflow.
- Evals/scoring (LLM-judge), sessions UX, export/retention.
- Pipeline assíncrono via Inngest/Redis (tirar fusão síncrona do request).
- ClickHouse upgrade p/ volume alto; RBAC + audit logs; shadcn/ui + zod.

## 6. Esfuerzo estimado y riesgo

| Bloque | Días | Reducción de riesgo |
|---|---|---|
| Framework core | 6-8 | patrones ya probados en agno/crewAI |
| Observabilidad/AMP | 6-8 | modelo langfuse, spec OTel ya está ignorado |
| Frontend | 6 | stack de usuario ya decidido |
| Integraciones/infra | 3-4 | docker local, minio/qdrant test-ready |
| **Total MVP** | **~20-25 días** | rippled |

---

## 7. Preguntas pendientes antes de implementar (necesito tu OK)

1. **Trazas en Postgres vs ClickHouse** ¿iniciar MVP solo con Postgres (más directo con tu
   stack) y dejar CH para después, o añadir ClickHouse ya?
2. **Nombre del paquete Python** ¿`wolfpack`? (import `wolfpack import Agent`). ¿`wolfpack-ai`?
3. **Alcance MVP de agentes**: ¿incluimos ya el modo "Team"/multi-agente jerárquico o primero
   single-Agent + tools + RAG y el team en fase 2?
4. **Providers iniciales**: ¿OpenAI SDK primero + Ollama local, o integrar más (Anthropic, Groq) desear 1?
5. **AMP "on-premise" imagen**: ¿generamos una imagen Docker única (compose total) con seed
   data para que corra, o Vas a integrar AMP en tu stack?

Responda este plan y quedo listo para implementar fase por fase.