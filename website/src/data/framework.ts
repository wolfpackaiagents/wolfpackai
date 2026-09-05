export interface CodeExample {
  title: string;
  code: string;
  language: string;
  description?: string;
}

export interface Parameter {
  name: string;
  type: string;
  required: boolean;
  default?: string;
  description: string;
}

export interface SectionContent {
  id: string;
  title: string;
  description: string;
  sections?: SectionContent[];
  parameters?: Parameter[];
  codeExamples?: CodeExample[];
}

export const frameworkSections: SectionContent[] = [
  {
    id: "agent",
    title: "Agent",
    description:
      "The core building block of Wolfpack AI. An Agent wraps a language model with tools, memory, guardrails, and observers to create an autonomous reasoning loop. The agent repeatedly observes its environment, reasons about the next action, executes tools, and incorporates results until it reaches a final answer.",
    parameters: [
      { name: "model", type: "BaseModel", required: true, description: "The model instance (e.g. get_model('openai/gpt-4o'), get_model('anthropic/claude-sonnet-4')). Provider prefix selects the correct implementation." },
      { name: "tools", type: "list[Function | Toolkit]", required: false, default: "[]", description: "List of callables or Functions the agent can invoke. Typed via @tool decorator with JSON schema inferred from type hints + docstring." },
      { name: "knowledge", type: "Knowledge | None", required: false, default: "None", description: "Knowledge base for RAG. When set, a search_knowledge tool is automatically injected into the agent." },
      { name: "pre_hooks", type: "list[BaseGuardrail | Callable]", required: false, default: "[]", description: "Guardrails and hooks that run on user input before the model sees it. PII masking, prompt-injection shield, and tool allowlist are auto-installed when enabled." },
      { name: "post_hooks", type: "list[BaseGuardrail | Callable]", required: false, default: "[]", description: "Guardrails that run on model output before returning to the caller." },
      { name: "pii_guardrail", type: "bool | PIIGuardrail", required: false, default: "False", description: "When True, masks PII (email, phone, SSN, credit card) in input/output. Can be a custom PIIGuardrail instance." },
      { name: "prompt_injection_guardrail", type: "bool", required: false, default: "False", description: "When True, blocks prompt injection attempts in user input." },
      { name: "tool_allowlist", type: "list[str] | None", required: false, default: "None", description: "If set, only these tool names may be called. Enforced at the execution boundary." },
      { name: "output_schema", type: "Pydantic BaseModel | None", required: false, default: "None", description: "Pydantic model schema for structured output validation. Parses final content and retries with feedback on failure." },
      { name: "telemetry", type: "Tracker | None", required: false, default: "None", description: "Tracker instance (WolfpackObserver, ConsoleTracker, etc.) for OpenTelemetry-compatible tracing." },
      { name: "session_id", type: "str | None", required: false, default: "None", description: "Session identifier for multi-turn conversations. When set, messages are persisted via session_store." },
      { name: "session_store", type: "SessionStore | None", required: false, default: "None", description: "Storage backend for session memory. Defaults to SQLiteSessionStore when session_id is set." },
      { name: "instructions", type: "str | list[str]", required: false, default: "''", description: "System-level instructions that define the agent's persona, behavior constraints, and response format." },
      { name: "role", type: "str | None", required: false, default: "None", description: "The agent's role description. Combined with goal and backstory to form the system prompt." },
      { name: "goal", type: "str | None", required: false, default: "None", description: "The agent's goal, used in system prompt construction." },
      { name: "max_iterations", type: "int", required: false, default: "20", description: "Maximum number of tool-calling iterations before the agent must produce a final answer." },
      { name: "disable_hitl", type: "bool", required: false, default: "False", description: "When True, skips HITL gates on tools that require confirmation or user input." },
    ],
    codeExamples: [
      {
        title: "Basic Agent",
        language: "python",
        code: `from wolfpack import Agent, get_model

model = get_model("openai/gpt-4o")
agent = Agent(
    model=model,
    instructions="You are a helpful assistant specialized in data analysis.",
)

response = agent.run("Analyze this CSV data and find trends")
print(response.content)`,
      },
      {
        title: "Agent with Tools and Session Memory",
        language: "python",
        code: `from wolfpack import Agent, get_model, tool

@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for information.
    Args:
        query: the search query.
        max_results: max results to return.
    """
    return f"Results for {query}: ..."

agent = Agent(
    model=get_model("anthropic/claude-sonnet-4"),
    tools=[search_web],
    session_id="my-session",
    instructions="You are a research assistant. Search the web and read files to answer questions.",
)

# Session persists context across calls
agent.run("Find recent papers on transformer architectures")
agent.run("Summarize the key findings")`,
      },
      {
        title: "Agent with Guardrails",
        language: "python",
        code: `from wolfpack import Agent, get_model, PIIGuardrail, PromptInjectionGuardrail, ToolAllowlistGuardrail

agent = Agent(
    model=get_model("openai/gpt-4o"),
    pii_guardrail=True,                          # masks emails, phones, SSNs, credit cards
    prompt_injection_guardrail=True,              # blocks prompt injection
    tool_allowlist=["get_weather", "get_stock"],  # only these tools may be called
    instructions="You are a customer support agent.",
)`,
      },
    ],
  },
  {
    id: "tools",
    title: "Tools",
    description:
      "Tools are callable functions with JSON schemas inferred from Python type hints via the @tool decorator. Each Tool wraps a function and exposes its parameters to the model. The framework also supports Toolkit grouping and factory functions for RAG search tools.",
    parameters: [
      { name: "name", type: "str", required: false, default: "function name", description: "Tool name, inferred from the function name by default. Used by the model to reference the tool." },
      { name: "description", type: "str", required: false, default: "docstring", description: "Description, inferred from the function's docstring. The model uses this to decide which tool to invoke." },
    ],
    codeExamples: [
      {
        title: "Creating a Custom Tool",
        language: "python",
        code: `from wolfpack import tool

@tool(
    name="github_search",
    description="Search GitHub repositories by keyword. Returns repo name, stars, description, and URL.",
    parameters={
        "query": {"type": "string", "description": "Search keyword or phrase"},
        "language": {"type": "string", "description": "Filter by programming language", "default": None},
        "max_results": {"type": "integer", "description": "Number of results", "default": 5},
    },
)
def github_search(query: str, language: str = None, max_results: int = 5) -> str:
    import requests
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "per_page": max_results}
    if language:
        params["q"] += f"+language:{language}"
    resp = requests.get(url, params=params)
    repos = resp.json().get("items", [])
    return "\\n".join(
        f"{r['full_name']} ({r['stargazers_count']}⭐) - {r['description']}"
        for r in repos
    )`,
      },
      {
        title: "Built-in Tools",
        language: "python",
        code: `from wolfpack import Agent
from wolfpack.tools import (
    WebSearchTool,
    WebScrapeTool,
    PythonExecutorTool,
    ShellTool,
    FileReaderTool,
    FileWriterTool,
    DatabaseQueryTool,
    EmailTool,
    SlackTool,
    GitHubTool,
    JiraTool,
    WeatherTool,
    CalculatorTool,
    DateTimeTool,
)

agent = Agent(
    model="openai/gpt-4o",
    tools=[
        WebSearchTool(search_engine="tavily", api_key_env="TAVILY_API_KEY"),
        PythonExecutorTool(timeout=30),
        DatabaseQueryTool(connection_string="postgresql://localhost:5432/mydb"),
        FileReaderTool(allow_paths=["/workspace"]),
        GitHubTool(
            token_env="GITHUB_TOKEN",
            repos=["alvaro-brito-products/wolfpack-ai"],
        ),
    ],
)`,
      },
      {
        title: "Tool Categories",
        language: "text",
        code: `# @tool decorator — wrap any function
@tool
def my_tool(param1: str, param2: int = 10) -> str:
    \"\"\"Description for the model.
    Args:
        param1: description of param1.
        param2: description of param2, defaults to 10.
    \"\"\"
    return result

# Toolkit — group related tools
from wolfpack import Toolkit
calc = Toolkit(name="calculator", functions=[add, multiply, sqrt])

# RAG search tool — auto-created from Knowledge
knowledge = Knowledge(...)
search_tool = create_knowledge_search_tool(knowledge)`,
      },
    ],
  },
  {
    id: "team",
    title: "Team",
    description:
      "Teams enable hierarchical multi-agent collaboration. A Team consists of a leader Agent and one or more member Agents, each with specialized capabilities. The leader receives the user's request, decomposes it into subtasks, delegates each subtask to the most qualified member, collects results, and synthesizes the final response. The Team class manages agent communication, task routing, and result aggregation.",
    parameters: [
      { name: "leader", type: "Agent", required: true, description: "The orchestrator agent that manages delegation. The leader must have a model capable of reasoning about which team member to assign to each subtask. Typically uses a stronger model like gpt-4o or claude-sonnet-4." },
      { name: "members", type: "list[Agent]", required: true, description: "List of specialist agents available for task execution. Each member typically has specific tools, instructions, and knowledge bases tailored to their domain." },
      { name: "max_delegations", type: "int", required: false, default: "10", description: "Maximum number of delegations per user request. Prevents runaway delegation chains." },
      { name: "delegation_mode", type: "str", required: false, default: '"auto"', description: 'How tasks are assigned: "auto" (leader decides), "round_robin" (sequential assignment), "broadcast" (all members receive the task), or "manual" (explicit routing by the developer).' },
      { name: "shared_memory", type: "Memory | None", required: false, default: "None", description: "Shared memory accessible by all team members. Useful for maintaining conversation context, shared state, and accumulated knowledge across the team." },
      { name: "shared_tools", type: "list[Tool]", required: false, default: "[]", description: "Tools available to all team members. Useful for infrastructure tools like logging, database access, or monitoring that any agent might need." },
      { name: "result_aggregator", type: "str", required: false, default: '"leader"', description: 'How results are combined: "leader" (leader synthesizes), "concatenate" (all results appended), "vote" (majority voting), or a custom callable.' },
      { name: "consensus", type: "bool", required: false, default: "False", description: "When enabled, members debate and reach consensus before producing a final answer. Useful for tasks requiring high accuracy or multiple perspectives." },
      { name: "max_rounds", type: "int", required: false, default: "1", description: "Number of debate rounds when consensus mode is enabled. More rounds allow deeper discussion but cost more tokens." },
    ],
    codeExamples: [
      {
        title: "Multi-Agent Research Team",
        language: "python",
        code: `from wolfpack import Agent, Team

leader = Agent(
    model="openai/gpt-4o",
    instructions="You are a research team lead. Delegate tasks to your specialists and synthesize their findings.",
)

researcher = Agent(
    model="anthropic/claude-sonnet-4",
    tools=[WebSearchTool(), WebScrapeTool()],
    instructions="You are a research specialist. Find detailed information on assigned topics.",
)

analyst = Agent(
    model="openai/gpt-4o",
    tools=[PythonExecutorTool(), DataVisualizationTool()],
    instructions="You are a data analyst. Process data and create visualizations.",
)

writer = Agent(
    model="anthropic/claude-sonnet-4",
    instructions="You are a technical writer. Produce clear, well-structured reports.",
)

research_team = Team(
    leader=leader,
    members=[researcher, analyst, writer],
    delegation_mode="auto",
    shared_memory=ConversationMemory(),
)

result = research_team.run(
    "Research the impact of LLMs on software development, analyze adoption trends, "
    "and write a comprehensive report with charts."
)`,
      },
      {
        title: "Consensus Team",
        language: "python",
        code: `from wolfpack import Agent, Team

agents = [
    Agent(model="openai/gpt-4o", instructions="You are an AI safety reviewer."),
    Agent(model="anthropic/claude-sonnet-4", instructions="You are an AI ethics specialist."),
    Agent(model="google/gemini-pro", instructions="You are a domain expert."),
]

review_team = Team(
    leader=agents[0],
    members=agents[1:],
    delegation_mode="broadcast",
    consensus=True,
    max_rounds=3,
    result_aggregator="vote",
)

result = review_team.run("Review this AI system design for potential risks.")`,
      },
    ],
  },
  {
    id: "memory",
    title: "Memory & Knowledge",
    description:
      "Memory and Knowledge systems give agents persistent context across sessions. Memory stores conversation history, user preferences, and learned information. Knowledge provides RAG (Retrieval-Augmented Generation) capabilities by indexing documents, code, and data for semantic search. Together they transform agents from stateless question-answerers into systems that learn and remember.",
    parameters: [
      { name: "storage", type: "str", required: false, default: '"local"', description: 'Storage backend: "local" (SQLite), "postgres", "redis", "chroma", "pinecone", or "custom".' },
      { name: "embedding_model", type: "str", required: false, default: '"text-embedding-3-small"', description: "Model used to generate vector embeddings for semantic search and retrieval." },
      { name: "max_messages", type: "int", required: false, default: "100", description: "Maximum number of messages retained in short-term conversation buffer. Oldest messages are dropped when limit is reached using LRU eviction." },
      { name: "summarization", type: "bool", required: false, default: "False", description: "When True, the agent periodically summarizes old conversation history to preserve context while reducing token usage. Summaries are stored in long-term memory." },
      { name: "summarization_model", type: "str", required: false, default: "None", description: "Optional specific model for summarization. Uses the agent's model if not specified." },
      { name: "summarization_threshold", type: "int", required: false, default: "50", description: "Number of messages after which summarization triggers." },
    ],
    codeExamples: [
      {
        title: "Conversation Memory",
        language: "python",
        code: `from wolfpack import Agent
from wolfpack.memory import ConversationMemory

agent = Agent(
    model="openai/gpt-4o",
    memory=ConversationMemory(
        storage="postgres",
        max_messages=100,
        summarization=True,
        summarization_threshold=30,
    ),
)

# Memory persists across calls
agent.run("My name is Alice and I work at Acme Corp.")
agent.run("What's my name and where do I work?")
# → "Your name is Alice and you work at Acme Corp."`,
      },
      {
        title: "Knowledge Base with RAG",
        language: "python",
        code: `from wolfpack import Agent
from wolfpack.knowledge import KnowledgeBase, Document

kb = KnowledgeBase(
    storage="chroma",
    embedding_model="text-embedding-3-small",
)

# Index documents
kb.add_documents([
    Document(
        content="Wolfpack AI is an open-source agent framework...",
        metadata={"source": "docs", "version": "1.0"},
    ),
    Document(
        content="The Agent class supports tools, memory, and guardrails...",
        metadata={"source": "api", "topic": "agent"},
    ),
])

# Or index a directory
kb.index_directory("./docs/", glob="**/*.md")

agent = Agent(
    model="openai/gpt-4o",
    knowledge=kb,
    instructions="Answer questions using the knowledge base. Cite your sources.",
)

agent.run("What is Wolfpack AI?")`,
      },
      {
        title: "Memory Types",
        language: "text",
        code: `# Short-Term Memory (Conversation Buffer)
- Stores recent messages in FIFO buffer
- Configurable max_messages (default: 100)
- Supports summarization to compress older content
- LRU eviction when limit exceeded

# Long-Term Memory (Vector Store)
- Embedding-based semantic storage
- Supports Chroma, Pinecone, Weaviate, Qdrant
- Automatic consolidation of related memories
- Time-decay relevance scoring

# Episodic Memory
- Stores specific past events and interactions
- Rich metadata (timestamp, context, emotional valence)
- Used for personalized responses

# Semantic Memory
- Stores facts, concepts, and general knowledge
- Deduplication and conflict resolution
- Confidence scoring for retrieved facts`,
      },
    ],
  },
  {
    id: "guardrails",
    title: "Guardrails & Human-in-the-Loop",
    description:
      "Guardrails enforce safety, compliance, and quality constraints on agent behavior. They act as filters that validate, transform, or block inputs and outputs at various stages of the agent pipeline. Human-in-the-Loop (HITL) mechanisms allow humans to review, approve, modify, or reject agent actions before execution, ensuring appropriate oversight for high-stakes operations.",
    parameters: [
      { name: "stage", type: "str", required: false, default: '"output"', description: 'When the guardrail fires: "input" (before model), "output" (after model), or "tool_call" (before tool execution).' },
      { name: "action", type: "str", required: false, default: '"block"', description: 'Action on violation: "block" (reject), "warn" (log warning), "transform" (modify content), "mask" (redact PII), or "flag" (mark for review).' },
      { name: "severity", type: "str", required: false, default: '"error"', description: 'Severity level: "info", "warning", "error", or "critical". Determines logging and alerting behavior.' },
    ],
    codeExamples: [
      {
        title: "Input and Output Guardrails",
        "language": "python",
        code: `from wolfpack import Agent
from wolfpack.guardrails import (
    InputGuardrail,
    OutputGuardrail,
    ToxicityFilter,
    PIIFilter,
    KeywordBlocker,
    RegexValidator,
    JSONSchemaValidator,
    TokenLimitGuardrail,
)

agent = Agent(
    model="openai/gpt-4o",
    guardrails=[
        InputGuardrail(
            max_length=8000,
            block_topics=["politics", "nsfw"],
            block_languages=["sql_injection", "prompt_injection"],
        ),
        OutputGuardrail(
            validate_json_schema=response_schema,
            allowed_domains=["docs.wolfpack.ai"],
        ),
        ToxicityFilter(threshold=0.8, action="warn"),
        PIIFilter(redact=["email", "phone", "credit_card"], action="mask"),
        TokenLimitGuardrail(max_input_tokens=128000, max_output_tokens=4096),
    ],
)`,
      },
      {
        title: "Human-in-the-Loop Approval",
        language: "python",
        code: `from wolfpack import Agent
from wolfpack.guardrails import HITLGuardrail, ApprovalPolicy

agent = Agent(
    model="openai/gpt-4o",
    tools=[EmailTool(), SlackTool(), GitHubTool()],
    guardrails=[
        HITLGuardrail(
            policies=[
                ApprovalPolicy(
                    action="send_email",
                    require_approval=True,
                    approvers=["manager@company.com"],
                    timeout_minutes=60,
                    rationale_required=True,
                ),
                ApprovalPolicy(
                    action="create_pr",
                    require_approval=True,
                    approvers=["lead@company.com"],
                ),
            ],
            fallback_action="queue",
            notification_channel="slack",
        ),
    ],
)

# Actions requiring approval will pause and notify approvers
agent.run("Send an email to the team about the deployment schedule")`,
      },
    ],
  },
  {
    id: "workflow",
    title: "Workflow",
    description:
      "Workflows define structured, multi-step processes that orchestrate agents, tools, and human interactions. Unlike the free-form agent loop, workflows provide explicit control flow with steps, transitions, branching, and error handling. Workflows are defined using a Python DSL or YAML configuration and support patterns like chains, routing, parallel execution, and human review gates.",
    parameters: [
      { name: "name", type: "str", required: true, description: "Unique workflow identifier." },
      { name: "steps", type: "list[Step]", required: true, description: "Ordered list of workflow steps. Each step can be an agent call, tool invocation, human review, conditional branch, or parallel group." },
      { name: "max_retries", type: "int", required: false, default: "3", description: "Maximum retry attempts for failed steps before the workflow enters error state." },
      { name: "timeout", type: "int", required: false, default: "3600", description: "Maximum workflow execution time in seconds." },
      { name: "on_error", type: "str", required: false, default: '"fail"', description: 'Error handling: "fail" (stop and report), "skip" (skip failed step), "retry" (retry with backoff), "fallback" (execute alternative step).' },
    ],
    codeExamples: [
      {
        title: "Document Processing Workflow",
        language: "python",
        code: `from wolfpack import Agent, Workflow
from wolfpack.workflow import Step, Branch, Parallel, HumanReview

wf = Workflow(
    name="document_processing",
    steps=[
        Step(
            name="classify",
            agent=classifier_agent,
            input="{{input.document}}",
        ),
        Branch(
            condition="classify.category == 'invoice'",
            if_true=[
                Step(name="extract_data", agent=invoice_agent),
                Step(name="validate", agent=validation_agent),
                HumanReview(
                    name="approve_payment",
                    approvers=["finance@company.com"],
                ),
            ],
            if_false=[
                Step(name="general_processing", agent=general_agent),
            ],
        ),
        Step(name="archive", tool=archive_tool),
    ],
    max_retries=2,
    on_error="retry",
)

result = wf.run(document="invoice_2024_001.pdf")`,
      },
      {
        title: "Customer Support Workflow",
        language: "yaml",
        code: `name: customer_support_pipeline
steps:
  - name: triage
    agent: triage_agent
    input: "{{ticket.description}}"

  - name: route
    branch:
      condition: "triage.priority == 'high'"
      if_true:
        - name: escalate
          agent: senior_support_agent
        - name: notify_manager
          tool: slack_notify
          params:
            channel: "#support-critical"
      if_false:
        - name: resolve
          agent: support_agent
          tools: [kb_search, ticket_update]

  - name: summarize
    agent: summary_agent
    input: "{{steps}}"

  - name: close_ticket
    tool: jira_update
    params:
      status: resolved

max_retries: 2
timeout: 1800
on_error: skip`,
      },
    ],
  },
  {
    id: "observability",
    title: "Observability",
    description:
      "Wolfpack AI provides comprehensive observability through OpenTelemetry-compatible tracing, metrics collection, and logging. The Observer class monitors agent execution, captures detailed telemetry (latency, token usage, tool calls, errors), and forwards data to the AMP control plane. Teams can visualize traces, set up alerts, and analyze performance dashboards through the AMP web interface or any OpenTelemetry-compatible backend.",
    parameters: [
      { name: "exporter", type: "str", required: false, default: '"amp"', description: 'Telemetry destination: "amp" (Wolfpack control plane), "otlp" (OpenTelemetry), "console" (stdout logging), or "custom".' },
      { name: "endpoint", type: "str", required: false, default: "None", description: "Exporter endpoint URL. For OTLP exporters, typically an HTTP/gRPC endpoint. For AMP, the AMP API URL." },
      { name: "sampling_rate", type: "float", required: false, default: "1.0", description: "Trace sampling rate between 0.0 and 1.0. Lower rates reduce volume for high-throughput systems. 1.0 captures all traces." },
      { name: "service_name", type: "str", required: false, default: '"wolfpack-agent"', description: "Service name identifier for distinguishing traces from different agent deployments." },
      { name: "capture_inputs", type: "bool", required: false, default: "True", description: "When True, captures agent inputs (prompts, messages) in traces. Disable for sensitive data." },
      { name: "capture_outputs", type: "bool", required: false, default: "True", description: "When True, captures agent outputs (responses) in traces. Disable for sensitive data." },
      { name: "metrics_interval", type: "int", required: false, default: "60", description: "Interval in seconds for aggregating and exporting metrics." },
    ],
    codeExamples: [
      {
        title: "Observer Setup",
        language: "python",
        code: `from wolfpack import Agent
from wolfpack.observability import Observer, MetricsConfig

observer = Observer(
    exporter="amp",
    endpoint="https://amp.wolfpack.ai/api/v1/traces",
    service_name="prod-customer-support",
    sampling_rate=0.5,
    capture_inputs=True,
    capture_outputs=True,
    metrics_config=MetricsConfig(
        collect_token_usage=True,
        collect_tool_latency=True,
        collect_error_rates=True,
        interval_seconds=30,
    ),
)

agent = Agent(
    model="openai/gpt-4o",
    instructions="Customer support agent.",
    observer=observer,
)`,
      },
    ],
  },
];