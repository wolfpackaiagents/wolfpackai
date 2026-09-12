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
    id: "data-connectors",
    title: "Governed Data Connectors",
    description: "Data connectors expose scoped, read-only access to approved relational, document, graph, key-value, and analytics sources. Pass a live SqlToolkit through Agent.tools, not Agent.knowledge. DataAccessPolicy restricts source objects, masks sensitive fields, and caps returned rows before data reaches the agent.",
    codeExamples: [{
      title: "Query PostgreSQL through a scoped connector",
      language: "python",
      code: `import os
import psycopg

from wolfpack import Agent, DataAccessPolicy, SqlToolkit, get_model_from_env

policy = DataAccessPolicy(
    source_id="production-customers",
    allowed_tables={"customers"},
    sensitive_columns={"email", "phone"},
    max_rows=100,
)

connection = psycopg.connect(os.environ["DATABASE_URL"])
customer_data = SqlToolkit(connection, policy=policy, dialect="postgres")

agent = Agent(
    name="customer-analyst",
    model=get_model_from_env(),
    tools=[customer_data],
    tool_allowlist=["list_tables", "describe_table", "query"],
)

print(agent.run("How many customers signed up this month?").content)`,
      description: "A live SqlToolkit belongs in tools. Use a database role with SELECT-only privileges; the application opens the connection and the model never receives the DSN or credentials.",
    }, {
      title: "Use SQLite for a local, governed dataset",
      language: "python",
      code: `import sqlite3

from wolfpack import DataAccessPolicy, SqlToolkit

connection = sqlite3.connect("analytics.db")
policy = DataAccessPolicy(
    source_id="local-analytics",
    allowed_tables={"daily_sales"},
    max_rows=50,
)
data = SqlToolkit(connection, policy=policy, dialect="sqlite")

print(data.query("SELECT day, total FROM daily_sales ORDER BY day DESC"))`,
      description: "The same policy blocks writes and access to tables outside the approved scope.",
    }, {
      title: "Combine live SQL with a Knowledge snapshot",
      language: "python",
      code: `from wolfpack import Agent, get_model_from_env, ingest_rows
from wolfpack.knowledge.knowledge import Knowledge

# customer_data is the governed SqlToolkit from the prior example.
snapshot = customer_data.query("SELECT id, name, email FROM customers")
knowledge = Knowledge(vector_db=vector_db, embedding_model=embedding_model)
ingest_rows(knowledge, snapshot["rows"], source_id="production-customers")

agent = Agent(
    name="customer-researcher",
    model=get_model_from_env(),
    tools=[customer_data],             # live, governed database access
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
];
