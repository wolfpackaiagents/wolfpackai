import { controlPlaneSections, type SectionContent as ControlPlaneSection } from "../data/control-plane";
import { frameworkSections, type Parameter, type SectionContent as FrameworkSection } from "../data/framework";
import type { Example } from "../data/examples.generated";

export type Language = "en" | "pt-BR";

type FrameworkTranslation = Partial<Omit<FrameworkSection, "parameters" | "codeExamples">> & {
  parameters?: Parameter[];
  codeExamples?: Array<{ title?: string }>;
};

const frameworkPt: Record<string, FrameworkTranslation> = {
  agent: {
    description: "Agent e o loop central de execucao. Ele combina um modelo de provedor, ferramentas tipadas, recuperacao opcional de conhecimento, memoria de sessao, guardrails, saida estruturada, aprovacoes e telemetria.",
    parameters: [
      { name: "name", type: "str", required: true, description: "Nome estavel do agente usado nas execucoes e na telemetria." },
      { name: "model", type: "BaseModel", required: true, description: "Modelo criado com get_model() ou get_model_from_env()." },
      { name: "tools", type: "list", required: false, default: "[]", description: "Funcoes decoradas com @tool ou instancias de Toolkit." },
      { name: "knowledge", type: "Knowledge", required: false, description: "Instancia de conhecimento que injeta uma ferramenta de busca." },
      { name: "telemetry", type: "Tracker", required: false, description: "Rastreador compativel com OpenTelemetry ou WolfpackObserver." },
      { name: "session_id", type: "str", required: false, description: "Habilita memoria persistente de sessao com varias interacoes." },
      { name: "max_iterations", type: "int", required: false, default: "20", description: "Maximo de iteracoes de chamada de ferramentas em uma execucao." },
    ],
    codeExamples: [{ title: "Um agente com ferramentas tipadas" }],
  },
  tools: {
    title: "Ferramentas e Toolkits",
    description: "O decorador @tool transforma uma funcao Python tipada em uma ferramenta chamada pelo modelo. O Wolfpack deriva o esquema JSON das anotacoes de tipo e da docstring. Toolkit agrupa funcoes relacionadas em uma unidade reutilizavel.",
    codeExamples: [{ title: "Defina uma ferramenta" }],
  },
  knowledge: {
    title: "Conhecimento e memoria",
    description: "Knowledge indexa textos e arquivos em uma implementacao VectorDb. SessionMemory mantem o historico de uma conversa em um armazenamento de sessao em memoria ou SQLite. Sao capacidades separadas que podem ser combinadas em um Agent.",
    codeExamples: [{ title: "Persista uma sessao" }],
  },
  guardrails: {
    title: "Guardrails e aprovacoes",
    description: "Os guardrails integrados podem mascarar informacoes de identificacao pessoal, bloquear injecao de prompt e limitar as ferramentas permitidas. Requisitos de execucao pausam tarefas sensiveis ate que um armazenamento de aprovacoes as resolva.",
    codeExamples: [{ title: "Ative a protecao de entrada integrada" }],
  },
  workflow: {
    title: "Workflows",
    description: "Workflow executa manipuladores Python nomeados em uma ordem deterministica de dependencias. As etapas podem depender de resultados anteriores, repetir falhas e usar uma condicao para pular trabalho com base no estado compartilhado.",
    codeExamples: [{ title: "Um workflow com dependencias" }],
  },
  team: {
    title: "Times",
    description: "Team coordena Agents membros nos modos coordinate, route, broadcast ou tasks. No modo coordinate, um modelo lider recebe as descricoes dos membros e delega por uma ferramenta interna.",
    codeExamples: [{ title: "Coordene dois especialistas" }],
  },
  observability: {
    title: "Observabilidade",
    description: "Cada execucao pode emitir spans no estilo OpenTelemetry. WolfpackObserver envia traces, chamadas de modelo, chamadas de ferramentas, uso e custo em lotes para o endpoint publico do AMP, sem interromper o processo do agente se o endpoint estiver indisponivel.",
    codeExamples: [{ title: "Envie uma execucao para o AMP" }],
  },
};

const controlPlanePt: Record<string, Partial<ControlPlaneSection>> = {
  "first-steps": { title: "Primeiros passos", description: "Implante a pilha AMP de produção com Docker Compose, conecte um agente Wolfpack e inspecione seus traces no Control Plane." },
  overview: { title: "Painel", description: "O painel do AMP resume o volume de traces, a latencia, o uso de tokens, o custo, os alertas e a atividade recente no escopo de ambiente e runtime selecionado." },
  traces: { title: "Traces e sessoes", description: "Trace Explorer armazena execucoes de agentes, spans aninhados, chamadas de ferramentas, uso de modelo, custo e erros. Sessoes agrupam traces relacionados por um identificador de sessao estavel." },
  mesh: { title: "Mesh", description: "Mesh registra definicoes versionadas de agentes e times nos ambientes. Ele acompanha registros, heartbeats de runtime, interacoes observadas e contexto de trace." },
  chat: { title: "Chat", description: "Chat persiste conversas e envia requisicoes a runtimes registrados e habilitados com endpoint de chat configurado. Server-Sent Events informa eventos do ciclo de vida e do resultado final." },
  approvals: { title: "Aprovacoes", description: "A fila de aprovacoes resolve requisitos duraveis com participacao humana. Cada decisao fica vinculada a sua execucao, escopo de trace e contexto de auditoria." },
  guardrails: { title: "Guardrails e alertas", description: "Eventos de guardrail e regras gerenciadas de alerta oferecem uma visao operacional dos sinais de seguranca, das falhas de ingestao e do ciclo de resolucao." },
  scores: { title: "Scores e avaliacoes", description: "Configuracoes de score, scores manuais e execucoes de avaliacao vinculam evidencias de qualidade aos traces e exibem a cobertura e as tendencias." },
  schedules: { title: "Agendamentos", description: "Agendamentos executam runtimes registrados em um horario, intervalo ou cadencia cron. Politicas controlam as mudancas e o historico registra tentativas e resultados." },
  channels: { title: "Canais", description: "Conexoes com Telegram, Slack e Discord encaminham webhooks de provedores suportados para agentes registrados. Credenciais sao armazenadas como segredos de projeto criptografados." },
  privacy: { title: "Privacidade", description: "As configuracoes de privacidade removem informacoes de identificacao pessoal antes da persistencia de telemetria e permitem solicitacoes de exportacao ou exclusao de dados." },
  resilience: { title: "Resiliencia", description: "A visao de resiliencia exibe a saude da fila de ingestao, tentativas, falhas e alertas operacionais. Metricas Prometheus ficam disponiveis no endpoint de metricas do backend." },
  settings: { title: "Configuracoes e governanca", description: "Projetos configuram retencao, chaves de API baseadas em papeis e politicas de governanca. Credenciais administrativas criam organizacoes, projetos e chaves de API de projeto." },
  secrets: { title: "Segredos de provedores", description: "O cofre de segredos de provedores criptografa credenciais externas em repouso. Conexoes de canal referenciam um identificador de segredo em vez de armazenar seu valor." },
};

const categoryPt: Record<string, string> = {
  Basic: "Basico", Tools: "Ferramentas", RAG: "RAG", Observability: "Observabilidade",
  Guardrails: "Guardrails", Workflows: "Workflows", Teams: "Times", MCP: "MCP",
  Evals: "Avaliacoes", Privacy: "Privacidade", Resilience: "Resiliencia", Hardening: "Reforco",
  Schedules: "Agendamentos", "Personal Agent": "Agente pessoal", "Coding Agent": "Agente de codigo", Channels: "Canais",
};

export function getFrameworkSections(lang: Language) {
  if (lang === "en") return frameworkSections;
  return frameworkSections.map((section) => {
    const translation = frameworkPt[section.id];
    return {
      ...section,
      ...translation,
      codeExamples: section.codeExamples?.map((example, index) => ({ ...example, ...translation?.codeExamples?.[index] })),
    };
  });
}

export function getControlPlaneSections(lang: Language) {
  if (lang === "en") return controlPlaneSections;
  return controlPlaneSections.map((section) => ({ ...section, ...controlPlanePt[section.id] }));
}

export function getCategoryLabel(category: string, lang: Language) {
  return lang === "pt-BR" ? categoryPt[category] ?? category : category;
}

export function getLocalizedExample(example: Example, lang: Language): Example {
  if (lang === "en") return example;
  return {
    ...example,
    category: getCategoryLabel(example.category, lang),
    description: `Exemplo executavel de ${example.sourcePath}.`,
    steps: ["Instale as dependencias com uv sync.", `Execute: ${example.command}`],
    explanation: "Esta pagina apresenta o arquivo-fonte canonico executado durante a verificacao da documentacao.",
    prerequisites: ["Python 3.10+ e uv", "Execute a partir de framework/: uv run python examples/...", "Configure OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY ou OLLAMA_BASE_URL."],
    verificationClass: example.verificationClass === "LLM integration" ? "Integracao com LLM" : example.verificationClass,
    validationStatus: example.validationStatus,
  };
}
