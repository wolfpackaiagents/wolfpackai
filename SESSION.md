# Resumo Da Sessao

Data: 2026-09-28

## Estado Do Produto

O Wolfpack AI e um monorepo com tres produtos conectados:

- `framework/`: framework Python publicado como `wolfpack`.
- `control-plane/`: AMP (Agent Management Platform), plataforma de operacao, governanca e observabilidade.
- `wolfpack-studio/`: ambiente visual para desenhar e executar agentes.

A branch local ativa e `feat/agentforce`. O PR (Pull Request) do AgentForce foi mesclado em 2026-09-28 no commit `3711d399`:

`https://github.com/wolfpackaiagents/wolfpackai/pull/34`

## AgentForce

O AgentForce foi implementado em `framework/wolfpack/force/`. Ele fornece:

- Um agente coordenador que planeja e roteia o trabalho.
- Pools especializados de executores com limites independentes de concorrencia.
- Execucao em lote e por streaming, com eventos de progresso e ETA (Estimated Time of Arrival), a estimativa de conclusao.
- Previsoes de duracao, custo e gargalos por AIPrediction.
- Aquisicao de dados de lotes brutos, Knowledge, OKF (Open Knowledge Format) e fontes SQL (Structured Query Language).
- Sincronizacao das previsoes com o AMP.

Arquivos relevantes:

- `framework/wolfpack/force/force.py`
- `framework/wolfpack/force/acquisition.py`
- `framework/wolfpack/force/prediction.py`
- `framework/wolfpack/force/events.py`
- `framework/wolfpack/force/result.py`
- `framework/tests/test_force.py`

A suite do framework foi executada com 227 testes coletados. Os 7 testes do AgentForce passaram.

Os exemplos estao em `framework/examples/24_force/`:

- `01_basic_force.py`
- `02_instagram_proxy_force.py`
- `03_bets_political_strategy_force.py`
- `fatos_bets_brasil.md`

O exemplo Bets usa uma base de conhecimento para gerar comentarios simulados, encaminha o trabalho dinamicamente aos pools e registra acoes como curtidas por identificador de comentario.

## Studio E AMP

O Wolfpack Studio inclui o no AgentForce, formularios, geracao de DSL (Domain-Specific Language), linguagem especifica de dominio, e uma aba de instancia com progresso, pools, metricas e feed de simulacao.

Arquivos relevantes do Studio:

- `wolfpack-studio/frontend/src/components/instances/InstanceAgentForce.tsx`
- `wolfpack-studio/frontend/src/components/canvas/nodeVisuals.ts`
- `wolfpack-studio/frontend/src/styles/global.css`

O AMP inclui badges do AgentForce nas previsoes e uma visao de pools e sintese.

Arquivos relevantes do AMP:

- `control-plane/frontend/src/pages/Predictions.tsx`
- `control-plane/frontend/src/pages/PredictionDetail.tsx`

A integracao do Studio com o Mesh do AMP inclui registro automatico, `MeshIdentity`, heartbeats e traces verificados. Os commits relacionados sao `28deeaa`, `a22eb1f`, `576c3a5`, `a462a3b` e `bac6e7b`.

Imagens publicadas no Docker Hub:

- `wolfpackaiagents/wolfpack-studio-backend:0.1.0`
- `wolfpackaiagents/wolfpack-studio-frontend:0.1.0`

## Documentacao Do Website

A documentacao do AgentForce foi adicionada ao website e enviada no commit `b753f2d`:

- `website/src/data/framework.ts`: referencia, parametros e exemplo Python do AgentForce.
- `website/src/i18n/content.ts`: localizacao em portugues brasileiro.
- `website/scripts/generate-examples-data.mjs`: mapeamento de `24_force` para a categoria AgentForce.
- `website/src/data/examples.generated.ts`: dados de exemplos regenerados.

Validacao concluida com sucesso:

```text
cd website && npm run build
```

O build gerou 53 exemplos de documentacao. O Vite apresentou apenas o aviso existente sobre tamanho do bundle.

## Servicos

Todos os servicos locais do Wolfpack foram parados em 2026-09-28:

- Infraestrutura Docker Compose do Control Plane: PostgreSQL, Redis, MinIO e Inngest.
- Containers e stack Compose do Wolfpack Studio.
- Processos locais de desenvolvimento Uvicorn e Vite.

`docker ps` estava vazio apos o encerramento. Nao assumir que um servico esta ativo sem conferir.

## Posicionamento De Mercado

O Wolfpack foi comparado com LangChain, LangGraph, CrewAI e Agno.

Diferenciais centrais:

- Produto conectado entre framework, Studio visual e AMP.
- AgentForce para acoes paralelas em massa, pools especializados e previsao operacional.
- Conhecimento portavel e auditavel por OKF.
- Acesso controlado a dados por `SqlToolkit` e `DataAccessPolicy`.
- Traces baseados em OpenTelemetry, identidade Mesh, aprovacoes, privacidade, retencao, agendamentos, segredos criptografados e governanca no AMP.

Pontos fortes dos concorrentes que devem ser reconhecidos:

- LangChain possui o ecossistema de integracoes mais amplo.
- LangGraph e maduro para grafos com estado, persistencia e recuperacao.
- CrewAI e simples para times orientados a papeis e fluxos.
- Agno e a comparacao mais proxima como plataforma integrada.

Posicionamento recomendado:

> Wolfpack AI e uma plataforma para construir e operar agentes em producao: desenvolvimento visual no Studio, execucao governada no framework e observabilidade no AMP. O AgentForce permite acoes em massa baseadas em conhecimento e dados, com previsao de custo, duracao, gargalos e auditoria ponta a ponta.

## SDKs Em Outras Linguagens

E viavel criar SDKs (Software Development Kits), kits de desenvolvimento de software, para TypeScript, C#, Java e Rust com paridade funcional, mas nao como traducoes diretas do Python.

Ordem recomendada:

1. TypeScript.
2. C#.
3. Java.
4. Rust.

Antes da implementacao, definir contratos versionados entre SDKs para comportamento publico, eventos, payloads do AMP, semantica OpenTelemetry, guardrails e resultados do AgentForce. Criar testes deterministas de conformidade compartilhados entre os SDKs.

## Propriedade Intelectual E Investimento

O direcionamento comercial recomendado e open core:

- Manter uma camada limitada do SDK aberta para promover adocao de desenvolvedores.
- Monetizar AMP, Studio, recursos avancados do AgentForce, conectores enterprise, governanca, instalacao privada, SLA (Service-Level Agreement), acordo de nivel de servico, e suporte.

No Brasil, priorizar a titularidade da propriedade intelectual pela empresa, contratos de cessao com contribuidores, registro de marca, registro de programa de computador e protecao de segredo industrial. Software isolado em geral nao e patenteavel, portanto buscar avaliacao juridica especializada antes de um pedido de patente.

Investidores avaliarao principalmente tracao, pilotos pagos, receita recorrente, retencao, metricas operacionais, diferenciacao tecnica e titularidade clara da propriedade intelectual.

## Retomada E Proximos Passos

Em uma nova sessao, use o pedido:

```text
Leia SESSION.md e continue de onde paramos.
```

Proximos passos sugeridos:

1. Atualizar a branch local `main` antes do proximo trabalho no monorepo.
2. Definir o limite entre codigo aberto e recursos proprietarios antes de uma decisao de licenciamento.
3. Criar a especificacao multi-SDK e a suite de conformidade antes de implementar TypeScript, C#, Java ou Rust.
4. Identificar e validar casos de uso empresariais pagos para AgentForce, governanca e observabilidade.
