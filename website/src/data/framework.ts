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
  parameters?: Parameter[];
  codeExamples?: CodeExample[];
}

export const frameworkSections: SectionContent[] = [
  {
    id: "agent",
    title: "Agent",
    description: "Agent is the core execution loop. It combines a provider model, typed tools, optional knowledge retrieval, session memory, guardrails, structured output, approvals, and telemetry.",
    parameters: [
      { name: "name", type: "str", required: true, description: "Stable agent name used in runs and telemetry." },
      { name: "model", type: "BaseModel", required: true, description: "Model created with get_model() or get_model_from_env()." },
      { name: "tools", type: "list", required: false, default: "[]", description: "Functions decorated with @tool or Toolkit instances." },
      { name: "knowledge", type: "Knowledge", required: false, description: "Knowledge instance that injects a search tool." },
      { name: "telemetry", type: "Tracker", required: false, description: "OpenTelemetry-compatible tracker or WolfpackObserver." },
      { name: "session_id", type: "str", required: false, description: "Enables persisted multi-turn session memory." },
      { name: "max_iterations", type: "int", required: false, default: "20", description: "Maximum tool-calling iterations for one run." },
    ],
    codeExamples: [{
      title: "A typed tool-calling agent",
      language: "python",
      code: `from wolfpack import Agent, get_model_from_env, tool

@tool
def get_weather(city: str) -> str:
    """Return a weather summary for a city."""
    return f"{city}: 22 C, cloudy."

agent = Agent(
    name="weather-assistant",
    model=get_model_from_env(),
    tools=[get_weather],
)

result = agent.run("What is the weather in Lisbon?")
print(result.content)`,
    }],
  },
  {
    id: "tools",
    title: "Tools and Toolkits",
    description: "The @tool decorator turns a typed Python function into a model-callable tool. Wolfpack derives its JSON schema from type hints and the function docstring. Toolkit groups related functions under one reusable unit.",
    codeExamples: [{
      title: "Define a tool",
      language: "python",
      code: `from wolfpack import Toolkit, tool

@tool
def add(left: int, right: int) -> int:
    """Add two integers."""
    return left + right

math_tools = Toolkit(name="math", functions=[add])`,
    }],
  },
  {
    id: "model-routing",
    title: "Model Routing",
    description: "ModelPolicy routes reasoning and simple tasks through explicit model chains. ModelRouter retries only retryable failures on configured fallbacks, records every attempt, and compares actual cost with a baseline using equivalent token counts. Use task_selector=\"simple\" to opt an Agent into the task route only for short, tool-free requests.",
    parameters: [
      { name: "ModelPolicy.reasoning", type: "ModelRoute", required: true, description: "Primary route for reasoning, tool use, and complex work." },
      { name: "ModelPolicy.task", type: "ModelRoute", required: false, description: "Route for explicitly selected simple tasks." },
      { name: "ModelRoute.primary", type: "ModelTarget", required: true, description: "First model attempted for the route." },
      { name: "ModelRoute.fallbacks", type: "list[ModelTarget]", required: false, default: "[]", description: "Ordered alternatives used only after retryable provider failures." },
      { name: "ModelTarget", type: "BaseModel | ModelSpec", required: true, description: "A concrete model or declarative provider configuration with optional token prices." },
      { name: "Agent.model_policy", type: "ModelPolicy", required: false, description: "Creates a ModelRouter for the Agent instead of passing model directly." },
      { name: "Agent.task_selector", type: "str", required: false, default: "None", description: "Set to simple to use the task route for short requests without tools." },
    ],
    codeExamples: [{
      title: "Route OpenAI reasoning to Ollama tasks",
      language: "python",
      description: "The primary route uses gpt-4.1-mini. Short tool-free requests use the Ollama model selected by OLLAMA_MODEL, and routing metadata records the selected model, attempts, costs, baseline, and estimated savings.",
      code: `import os

from wolfpack import Agent, ModelPolicy, ModelRoute, ModelTarget, get_model

policy = ModelPolicy(
    reasoning=ModelRoute(
        primary=ModelTarget(get_model("openai:gpt-4.1-mini"), 0.40, 1.60),
    ),
    task=ModelRoute(
        primary=ModelTarget(get_model(f"ollama:{os.environ['OLLAMA_MODEL']}"), 0.0, 0.0),
    ),
)

agent = Agent(
    name="routed-assistant",
    model_policy=policy,
    task_selector="simple",
)

result = agent.run("Reply with the word ready.")
print(result.content)
print(agent.model.last_routing["selected"])`,
    }],
  },
  {
    id: "knowledge",
    title: "Knowledge and Memory",
    description: "Knowledge indexes text and files in a VectorDb implementation. SessionMemory keeps a conversation history through an in-memory or SQLite session store. These are separate capabilities that can be combined in an Agent.",
    codeExamples: [{
      title: "Persist a session",
      language: "python",
      code: `from wolfpack import Agent, SQLiteSessionStore, get_model_from_env

agent = Agent(
    name="support",
    model=get_model_from_env(),
    session_id="customer-42",
    session_store=SQLiteSessionStore("sessions.db"),
)

agent.run("My name is Ada.")
print(agent.run("What is my name?").content)`,
    }],
  },
  {
    id: "skills",
    title: "Skills",
    description: "Skills are reusable Agent capabilities. A Skill without context is included in every system prompt. A contextual Skill stays lightweight until the model calls activate_skill(name), which adds its instructions as a system message for the rest of the run. SkillKnowledge keeps specialised retrieval separate from the prompt by registering a context-aware search tool. Configured skill names are recorded in trace metadata, while activations and searches are recorded as tool spans.",
    parameters: [
      { name: "skills", type: "list[Skill | SkillKnowledge]", required: false, default: "[]", description: "Capabilities configured on an Agent in declaration order." },
      { name: "Skill.name", type: "str", required: true, description: "Unique name used for activation, tool calls, and trace metadata." },
      { name: "Skill.content", type: "str", required: false, description: "Instructions supplied inline. Required when path is not provided." },
      { name: "Skill.path", type: "str | Path", required: false, description: "Path to a Markdown file whose contents become the skill instructions." },
      { name: "Skill.context", type: "str", required: false, description: "When provided, makes the Skill contextual instead of always active." },
      { name: "SkillKnowledge.knowledge", type: "Knowledge", required: true, description: "Specialised knowledge base exposed through search_knowledge_{name}." },
      { name: "SkillKnowledge.context", type: "str", required: true, description: "Describes when the model should search the specialised knowledge base." },
    ],
    codeExamples: [{
      title: "Combine always-active and contextual instructions",
      language: "python",
      description: "The writing skill is included in every run. The risk skill remains available by name until the model activates it with the generated tool.",
      code: `from wolfpack import Agent, Skill, get_model_from_env

clear_writing = Skill(
    name="clear-writing",
    content="Use concise language and state assumptions explicitly.",
)
risk_analysis = Skill(
    name="risk-analysis",
    content="Use a probability by impact matrix. Classify risk as low, medium, high, or critical.",
    context="Activate when the user asks for project or financial risk analysis.",
)

agent = Agent(
    name="project-advisor",
    model=get_model_from_env(),
    skills=[clear_writing, risk_analysis],
)

result = agent.run("What is the delivery risk for this project?")
print(result.tool_calls)  # activate_skill({"name": "risk-analysis"})
print(result.content)`,
    }, {
      title: "Attach specialised knowledge on demand",
      language: "python",
      description: "SkillKnowledge does not add document content to the system prompt. It makes a named search tool available only when its context is relevant.",
      code: `from wolfpack import Agent, SkillKnowledge, get_model_from_env

# regulatory_knowledge is a Knowledge instance loaded with approved source documents.
regulatory = SkillKnowledge(
    name="telecom-regulations",
    knowledge=regulatory_knowledge,
    context="Use when the user asks about telecom regulations or ANATEL standards.",
)

agent = Agent(
    name="compliance-advisor",
    model=get_model_from_env(),
    skills=[regulatory],
)

result = agent.run("Which ANATEL rules apply to this network change?")
print(result.tool_calls)  # search_knowledge_telecom-regulations(...)`,
    }],
  },
  {
    id: "data-connectors",
    title: "Governed Data Connectors",
    description: "Data connectors expose scoped, read-only access to approved relational, document, graph, key-value, and analytics sources. Pass a live SqlToolkit through Agent.tools, not Agent.knowledge. DataAccessPolicy restricts source objects, masks sensitive fields, and caps returned rows before data reaches the agent.",
    codeExamples: [{
      title: "Prioritize overdue corporate debt in PostgreSQL",
      language: "python",
      code: `import os
import psycopg

from wolfpack import Agent, DataAccessPolicy, SqlToolkit, get_model_from_env

policy = DataAccessPolicy(
    source_id="corporate-debts",
    allowed_tables={"company_debts"},
    sensitive_columns={"tax_id"},
    max_rows=100,
)

connection = psycopg.connect(os.environ["DATABASE_URL"])
debt_data = SqlToolkit(connection, policy=policy, dialect="postgres")

agent = Agent(
    name="collections-analyst",
    model=get_model_from_env(),
    tools=[debt_data],
    tool_allowlist=["list_tables", "describe_table", "query"],
)

print(agent.run("Which companies have the largest overdue balances?").content)`,
      description: "A live SqlToolkit belongs in tools. Use a database role with SELECT-only privileges; the application opens the connection and the model never receives the DSN or credentials.",
    }, {
      title: "Search action movies in a local SQLite catalog",
      language: "python",
      code: `import sqlite3

from wolfpack import DataAccessPolicy, SqlToolkit

connection = sqlite3.connect("analytics.db")
policy = DataAccessPolicy(
    source_id="film-catalog",
    allowed_tables={"movies"},
    max_rows=50,
)
data = SqlToolkit(connection, policy=policy, dialect="sqlite")

print(data.query("SELECT title, rating FROM movies WHERE genre = 'Action' ORDER BY rating DESC"))`,
      description: "The same policy blocks writes and access to tables outside the approved scope.",
    }, {
      title: "Combine live SQL with a Knowledge snapshot",
      language: "python",
      code: `from wolfpack import Agent, get_model_from_env, ingest_rows
from wolfpack.knowledge.knowledge import Knowledge

# debt_data is the governed SqlToolkit from the prior example.
snapshot = debt_data.query("SELECT company_name, outstanding_amount, due_date FROM company_debts WHERE status = 'overdue'")
knowledge = Knowledge(vector_db=vector_db, embedding_model=embedding_model)
ingest_rows(knowledge, snapshot["rows"], source_id="production-customers")

agent = Agent(
    name="collections-researcher",
    model=get_model_from_env(),
    tools=[debt_data],                 # live, governed database access
    knowledge=knowledge,               # an explicit, point-in-time RAG snapshot
    tool_allowlist=["query", "search_knowledge"],
)`,
      description: "Use Knowledge only for explicitly ingested snapshots. It remains distinct from the live connector and carries no source credentials.",
    }],
  },
  {
    id: "guardrails",
    title: "Guardrails and Approvals",
    description: "Built-in guardrails can mask personally identifiable information, block prompt injection, and constrain the tool allowlist. Run requirements pause sensitive work until an approval store resolves it.",
    codeExamples: [{
      title: "Enable built-in input protection",
      language: "python",
      code: `from wolfpack import Agent, get_model_from_env

agent = Agent(
    name="safe-assistant",
    model=get_model_from_env(),
    pii_guardrail=True,
    prompt_injection_guardrail=True,
    tool_allowlist=["get_weather"],
)`,
    }],
  },
  {
    id: "workflow",
    title: "Workflows",
    description: "Workflow executes named Python handlers in deterministic dependency order. Steps may depend on prior output, retry failures, and use a condition to skip work from the shared state.",
    codeExamples: [{
      title: "A dependency-aware workflow",
      language: "python",
      code: `from wolfpack import Workflow

workflow = Workflow("daily-report")
workflow.add_step("fetch", lambda state: state["source"].upper(), retries=1)
workflow.add_step("format", lambda state: f"Report: {state['fetch']}", depends_on=["fetch"])
workflow.add_step("notify", lambda state: "sent", depends_on=["format"], condition=lambda state: state["send"])

result = workflow.run({"source": "sales completed", "send": True})
print(result.outputs)`,
    }],
  },
  {
    id: "team",
    title: "Teams",
    description: "Team coordinates member Agents in coordinate, route, broadcast, or tasks mode. In coordinate mode, a leader model receives member descriptions and delegates through an internal tool.",
    codeExamples: [{
      title: "Coordinate two specialists",
      language: "python",
      code: `from wolfpack import Agent, Team, get_model_from_env

model = get_model_from_env()
researcher = Agent(name="researcher", model=model, description="Find concise facts.")
editor = Agent(name="editor", model=model, description="Edit research into one clear sentence.")

team = Team("research-team", [researcher, editor], leader_model=model)
print(team.run("Give one fact about octopuses.").content)`,
    }],
  },
  {
    id: "observability",
    title: "Observability",
    description: "Every run can emit OpenTelemetry-style spans. WolfpackObserver batches traces, model calls, tool calls, usage, and cost to the AMP public ingestion endpoint while allowing the agent process to continue if the endpoint is unavailable.",
    codeExamples: [{
      title: "Send a run to AMP",
      language: "python",
      code: `from wolfpack import Agent, get_model_from_env
from wolfpack.observer.client import WolfpackObserver

tracker = WolfpackObserver(
    base_url="http://localhost:8000",
    api_key="pk-...:secret",
)
agent = Agent(name="observed-agent", model=get_model_from_env(), telemetry=tracker)
agent.run("Summarize this request.")
tracker.flush()`,
    }],
  },
  {
    id: "ai-prediction",
    title: "AIPrediction",
    description: "AIPrediction orchestrates a panel of persona agents to generate structured forecasts from seed materials. Each persona receives the scenario and seed context, debates with other agents, and the results are synthesized into a prediction report with convergence analysis, a social simulation graph with typed entities and evidence from the source material, and optional observed-outcome evaluation for accuracy scoring.",
    parameters: [
      { name: "name", type: "str", required: true, description: "Prediction run name used in AMP reports." },
      { name: "model", type: "BaseModel", required: true, description: "Model created with get_model() or get_model_from_env()." },
      { name: "personas", type: "list[dict]", required: false, description: "List of persona definitions with name, role, bias, and expertise. Auto-generated from the seed when omitted." },
      { name: "horizon", type: "str", required: false, description: "Prediction horizon date (ISO format)." },
      { name: "knowledge", type: "Knowledge", required: false, description: "Knowledge instance with seed documents loaded." },
      { name: "auto_create_personas", type: "bool", required: false, default: "False", description: "When True, generates personas from the seed context via LLM." },
      { name: "persona_count", type: "int", required: false, default: "4", description: "Number of personas to auto-generate." },
      { name: "debate_rounds", type: "int", required: false, default: "3", description: "Critique and revision rounds between personas." },
    ],
    codeExamples: [{
      title: "Predict with auto personas and outcome evaluation",
      language: "python",
      code: `from wolfpack import AIPrediction, get_model_from_env

model = get_model_from_env()
predictor = AIPrediction(
    name="election-prediction",
    model=model,
    auto_create_personas=True,
    persona_count=4,
    debate_rounds=3,
    horizon="2026-10-04",
)
predictor.ingest_seed(text=seed_text)

# observed_outcome is optional; omitting it skips evaluation
report = predictor.run(scenario, observed_outcome=observed_result)
print(f"Accuracy: {report.accuracy_score}")
print(report.evaluation_reason)

# Sync to AMP for visualization and persistence
pred_id = predictor.sync_to_amp(report, "http://localhost:8000", "pk-...:secret")`,
    }],
  },
  {
    id: "okf",
    title: "Open Knowledge Format (OKF)",
    description: "OKF is a portable, vendor-neutral format for agent knowledge using markdown files with YAML frontmatter. A bundle is a directory of concepts where file paths = identities and markdown links = a navigable graph. Three backends are supported: local directory, .tar.gz archive, and S3/MinIO.",
    codeExamples: [{
      title: "Create and query an OKF bundle",
      language: "python",
      code: `from wolfpack.knowledge.okf import LocalOKFStorage, OKFBundle, Concept

async def example():
    storage = LocalOKFStorage("./bundle")
    bundle = OKFBundle(storage)

    await bundle.add(Concept(
        path="tables/orders.md",
        type="BigQuery Table",
        title="Orders",
        description="One row per completed order.",
        tags=["sales"],
        body="See [customers](tables/customers.md).",
    ))

    results = await bundle.search("revenue")
    for c in results:
        print(c.title, c.type)

    ctx = await bundle.to_context(query="orders")
    print(ctx)`,
    }],
  },
];
