# Wolfpack AI — Plano de evolução (Fases 5–11)

> Base: análise de lacunas frente às 12 capacidades de sistemas de agentes (HITL, tools,
> orquestração multiagente, memória/estado, RAG, workflows, streaming, observabilidade,
> guardrails, evals, MCP, LGPD/GDPR) + pesquisa nos frameworks de referência (agno,
> crewAI, vercel/ai). A proposta adota padrões já validados nesses código-fontes.

---

## 1. Matriz de gap: onde estamos hoje

Legenda: ✅ pronto e validado · 🟡 parcial/esboço · ❌ não implementado

| Capacidade | Estado wolfpack | Observação |
|---|---|---|
| Tool calling | ✅ | OpenAI/Anthropic/Google validados nos exemplos |
| RAG / conhecimento | ✅ | Memory/Qdrant/PGVector + embeddings OpenAI/Ollama/HuggingFace |
| Observabilidade / tracing | ✅ | OTel `gen_ai.*` + WolfpackObserver → AMP; E2E validado |
| Streaming | 🟡 | Eventos por passo (RunTool/Content/Step) existem; streaming chunk-level do LLM funcional; sem structured-output validation na stream |
| HITL | ✅ | RunRequirement com pause/resume, HMAC signature, approval store (local SQLite ou AMP), approvals API com resolve |
| Memória / estado | ✅ | SessionMemory pluggable (SQLite padrão, SQLiteSessionStore), personal memory consentida |
| Saída estruturada | ✅ | `output_schema` Pydantic com parse pós-geração + retry via feedback |
| Guardrails / segurança | ✅ | `pre_hooks`/`post_hooks` (BaseGuardrail), PII masking/block, prompt-injection shield, tool allowlist |
| Workflows determinísticos | ✅ | Workflow DAG com passadas sequenciais, condições (@router) e retry |
| Multiagente (team) | ✅ | Team com leader delegador, modos coordinate/route/broadcast/tasks, parent_run_id |
| Evals / scoring | ✅ | Scores API, evals runner LLM-judge básico, score_configs |
| MCP | 🟡 | MCP client funcional; server MCP não implementado |
| LGPD/GDPR | 🟡 | Redação PII em traces via Observer, retenção/TTL configurável, export/deletar traces por titular, sessões isoladas por tenant |

**AMP backend**: ingestion assíncrona (job queue), APIs públicas de scores, sessions, aprovações,
governança, privacidade, schedule policies, mesh, channels. RBAC básico (read_only/editor/admin),
retenção configurável, export/deletar traces. **Frontend**: dashboard com traces, métricas,
sessions, schedule policies, alert destinations, aprovações.

---

## 2. O que vamos construir (priorização estratégica)

### P0 — Base de confiança (necessário para tudo o mais e para LGPD/GDPR)
1. **HITL durável** (copy do `RunRequirement`/`ToolExecution` do agno + aprovação do vercel):
   - `RunStatus` (running/paused/completed/cancelled/error) + `RunRequirement` (confirmation,
     user_input, user_feedback, external_execution) com `is_resolved()`.
   - Tool flags já existem; o loop para de fato ao achar requisito pendente; persistir
     **approval rows** (tabela AMP `approvals` ou JSON no run) e **API de resume**
     (`POST /api/approvals/{id}/resolve` + `run.continue()`).
   - HMAC signature (vercel) para que a resposta de aprovação não possa ser forjada.
2. **Guardrails + saída estruturada** (copy do agno/crewAI):
   - `pre_hooks`/`post_hooks` unificados (`BaseGuardrail`/`BaseEval`), roda guardrails de
     forma síncrona (abort input inválido), hooks async em background.
   - Guardrails built-in P0: **PII masking/block**, **prompt-injection shield**,
     **allowlist de tools por usuário/tenant/role**, **saída formatada por schema**.
   - `output_schema` no Agent (Pydantic) com parse pós-geração + retry via feedback
     (crewAI).
3. **Memória persistida + sessões**:
   - `SessionMemory` plugada a um `SessionStore` (SQLite/file por padrão, Postgres via AMP
     mais tarde); long-term memory (resumo + recall) similar crewAI.
   - AMP: `sessions` endpoint + associação `trace.session_id` já existe no schema.

### P1 — Diferenciadores do produto
4. **Team/multi-agente** (agno `TeamMode` + crewAI manager):
   - Modos coordinate/route/broadcast/tasks; manager que delega via tool; `Team.run()`.
   - Observabilidade preservada: runs aninhados (`parent_run_id`).
5. **Workflows determinísticos**:
   - `Workflow`/`Flow`: DAG simples com passadas, condições (`@router` leve), retry.
   - Reusa tools+guardrails do legado.
6. **Evals/scoring operacional**:
   - AMP: runner LLM-judge (worker) que pontua traces segundo `score_configs`;
     endpoints `/scores`, `/score-configs`; seed de configs.
7. **MCP client**:
   - Conectar a servidores MCP remoto (incluindo remote MCP) e expor tools como
     `@tool`/Function; via `wolfpack[tools-mcp]`.
8. **Streaming token-level + robustez**:
   - `Model.invoke_stream()`; `run(stream=True)` entrega chunks reais; otimização de
     dedup no `_stream`.

### P2 — AMP enterprise (LGPD/GDPR + governança)
9. **Retenção e TTL** por projeto (`retention_days` já no schema) + job de limpeza.
10. **PII redaction em traces** (config por projeto; mascarar antes de persistir).
11. **RBAC**: perfis read-only/editor/admin + `api_keys` com escopo/expiração.
12. **Endpoints de direito do titular**: localizar/exportar/deletar dados por usuário
    (`user_id`) cruzando traces+observations+scores+embeddings.
13. **Ingestion assíncrona**: fila Redis/Inngest (tirar fusão síncrona do request).
14. **Export** de trace/projeto (JSON/CSV) para migração/auditoria.

### P3 — Frontend de prod
- Páginas novas: **Evals**, **Sessions**, **Agents** (registry do que roda), **Guardrails**,
  **Settings** avancado (retenção, PII, RBAC), **Trace filters** por scores/tags/uso.
- Componentes shadcn/ui + zod (deixado para simplificar ao invés de duplicar).

---

## 3. Fases de implantação (executáveis)

### Fase 5 — HITL durável + Guardrails + Saída estruturada (+ LGPD base)
Dias: 5–7
- `RunStatus`/`RunRequirement`/pause/resume/`approval` (framework + AMP approval + API)
- `pre/post_hooks` + `BaseGuardrail` + guardrails PII/prompt-injection/allowlist
- `output_schema` + parse Pydantic + retry
- Testes combinados; exemplos `examples/06_hitl_guardrails/`
Cobertura LGPD: base (mascarar PII, bloquear prompt injection, saída validada).

### Fase 6 — Memória persistente, Sessions e Workflows
Dias: 4–6
- `SessionStore` pluggable (SQLite default; Postgres opcional), long-term memory
- `OPAM sessions` endpoints + frontend Sessions
- `Workflow`/ (DAG) + retry/condicional
- Testes + exemplos `examples/06_workflows/`

### Fase 7 — Team multi-agent + MCP
Dias: 5–7
- `Team` (coordinate/route/broadcast/tasks) + `leader`, `parent_run_id` nos traces
- `Team.run/arun` + Tevents/Tracing aninhado
- MCP client: `mcp.connect(url)` → tools como Functions; fallback listo fácil
- Exemplos `examples/07_teams/`, `examples/08_mcp/`

### Fase 8 — Evals + ingestão assíncrona + RBAC + retenção
Dias: 5–7
- AMP: fila Redis/In `Ingestão::` (processors), `scores`/`evaluators` API; worker LLM-judge
- RBAC em api_keys (read_only), TTL job de retenção, export JSON/CSV
- Frontend: página de Evals, Sessions, Trace com acores, Settings av.
- E2E: agente → guardrail → pause/aprovação → resume → elevar → eval → score

### Fase 9 (hardening LGPD) — PII nos traces, titular endpoints, zip
Dias: 3–4
- `redact_pii` na pipeline de ingestion + opções `record_input/output`
- `/users/{id}/export|delete` (cross-teans), embeddings linkados por tenant
- Auditoria: registrar aprovações (quem/quando/o quê), retention curto p/ logs

---

## 4. Dependências-chave

- Fase 5 é pré-requisito de 6, 8 (guardrails/HITL alimentam queda → evals).
- 7 (team) incorpora o `Workflow` da 6 (sentando `parent_run_id`).
- 8/9 dependem de a ingestão parar de ser síncrona (Fase 8.0, Fila).

---

## 5. Impacto e esforço

| Bloco | Dias | Risco | Mitigação |
|---|---|---|---|
| HITL+Guardrails+Saída estr | 5–7 | Médio | copy do estado agno/crewai; teste de integração contínuo |
| Memória+Workflow | 4–6 | Baixo | storage isolado e pluggable; DAG pequeno |
| Team+MCP | 5–6 | Médio | manager delegador ~crewai v1 |
| Evals+Ingestão+RBAC+TTL | 5–7 | Médio | fila simples (Inngest/Redis), worker isolado |
| LGPD (PII, titular) | 3–4 | Médio | redação config, endpoints + testes de conformidade |
| **Total** | **~24–30 dias** | | entregável por fase e testável |

---

## 6. Ordem sugerida de execução (sujeito à tua aprovação)

1. **Fase 5** (HITL + Guardrails + Saída estruturada) — maior valor e base jurídica.
2. **Fase 6** (Memória/sessões + Workflow).
3. **Fase 7** (Team + MCP).
4. **Fase 8** (Evals + Ingestion async + RBAC/retention + frontend).
5. **Fase 9** (Consolidar LGPD/GDPR: PII nos traces, titular, export).

Cada fase termina com exemplos executáveis e testes. Framework continua `pip install wolfpack`;
o AMP continua deployável on-prem/cloud com `run.sh`.

---

## 7. Perguntas para decidir antes de eu executar

1. **Ordem de fases**: começar por Fase 5 (HITL/guardrails) confirmado? Ou priorizar Team/Workflows (discussão de produto) antes de cidadania?
2. **HITL storage**: aprovação persistida no AMP (tabela `approvals`) via API — ou localmente no próprio run (SQLite) com opção de publicar? (press: AMP central, recomendado).
3. **Guardrails PII**: mascarar (não persistir) vs pseudonimizar (reversível)? Define a estratégia LGPD.
4. **Workflow/Team**: implementar no framework (como agno) ou somente via API/SDK externa? (recomendado: framework nativo).
5. **MCP**: cliente primeiro (consumir tools externas) — suficiente? (server MCP para expor nossos tools fica depois).
6. **Ingestão async**: usar Redis+rq/worker próprio ou integrar In `Inngest` (já no stack)? Inngest alinha ao stack de infra do projeto.