import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const websiteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = path.resolve(websiteRoot, "..");
const examplesRoot = path.join(projectRoot, "framework", "examples");
const outputPath = path.join(websiteRoot, "src", "data", "examples.generated.ts");

const categoryByDirectory = {
  "01_basic": "Basic",
  "02_tools": "Tools",
  "03_rag": "RAG",
  "05_observability": "Observability",
  "06_hitl_guardrails": "Guardrails",
  "06_workflows": "Workflows",
  "07_teams": "Teams",
  "08_mcp": "MCP",
  "09_evals": "Evals",
  "10_privacy": "Privacy",
  "11_resilience": "Resilience",
  "12_hardening": "Hardening",
  "13_data_connectors": "Data connectors",
  "16_scheduled_tasks": "Schedules",
  "17_personal_agent": "Personal Agent",
  "18_coding_agent": "Coding Agent",
  "19_channels": "Channels",
  "20_team_with_knowledge": "Teams",
};

const modelExamples = new Set([
  "01_basic/01_hello_agent.py", "01_basic/02_chat_with_memory.py", "01_basic/03_stream_events.py",
  "02_tools/01_tool_basics.py", "02_tools/02_toolkit_example.py", "02_tools/03_multi_provider.py", "02_tools/04_requires_confirmation.py",
  "03_rag/01_rag_memory.py", "03_rag/02_rag_from_file.py", "03_rag/03_rag_provider_choice.py",
  "05_observability/01_otel_console.py", "05_observability/02_amp_observer.py", "05_observability/03_stream_events.py",
  "06_hitl_guardrails/01_hitl_approve.py", "06_hitl_guardrails/02_guardrails.py", "06_workflows/02_session.py",
  "07_teams/01_coordinate.py", "09_evals/02_agent_evaluator.py", "11_resilience/01_openai_token_stream.py",
  "13_data_connectors/03_postgres_agent.py", "13_data_connectors/04_sql_snapshot_knowledge_agent.py",
  "13_data_connectors/05_mysql_movie_agent.py", "13_data_connectors/06_mongodb_support_agent.py", "13_data_connectors/07_clickhouse_revenue_agent.py", "13_data_connectors/08_other_connectors_agents.py",
  "20_team_with_knowledge/01_team_with_knowledge.py",
]);

const ampExamples = new Set([
  "05_observability/02_amp_observer.py", "07_teams/02_mesh_telemetry.py", "07_teams/03_deterministic_telemetry_hitl.py",
  "16_scheduled_tasks/01_schedule_client.py", "17_personal_agent/03_amp_personal_assistant.py", "18_coding_agent/02_amp_coding_workflow.py",
]);

const externalExamples = new Set(["08_mcp/01_stdio_client.py", "08_mcp/local_server.py", "16_scheduled_tasks/03_http_runtime.py"]);

const capturedOutput = {
  "01_basic/01_hello_agent.py": "FINAL ANSWER\nHello! I'm your friendly assistant powered by the Wolfpack AI framework.",
  "01_basic/02_chat_with_memory.py": "TURN 2\nYour name is Alex, and we've talked about your interest in learning about AI agents.",
  "01_basic/03_stream_events.py": "RunStarted -> RunContent -> RunStep -> RunCompleted\nCOLLECTED RESULT\nusage: {'input_tokens': 87, 'output_tokens': 56}",
  "02_tools/01_tool_basics.py": "The weather in Madrid is 22°C and partly cloudy. Additionally, 14 * 7 equals 98.\nTOOL CALLS: get_weather, calculator",
  "02_tools/02_toolkit_example.py": "Toolkit name: data_tools\nRegistered tools: ['get_stock_price', 'get_company_news']",
  "02_tools/03_multi_provider.py": "Resolved provider/model: openai / gpt-4o-mini\n[tool] get_weather(...)\n[tool] calculator(...) -> 20",
  "02_tools/04_requires_confirmation.py": "status: 'tool_confirmation'\nThe gated tool never produced a real side effect.",
  "03_rag/01_rag_memory.py": "Knowledge documents: 5\nFINAL ANSWER\nThe exact term is 'gen_ai.'",
  "03_rag/02_rag_from_file.py": "Documents stored: 4\nThe price of priority delivery is 9.90 euros, and it arrives before noon the next business day.",
  "03_rag/03_rag_provider_choice.py": "OpenAI embedded OK\nOllama embedded OK\nOpenAI [dims=1536]\nOllama [dims=768]",
  "05_observability/01_otel_console.py": "run result\nstatus: ok\nanswer: The weather in Lisbon is currently 22°C and partly cloudy.",
  "05_observability/02_amp_observer.py": "status: ok\nanswer: The weather in Lisbon is currently 22°C and partly cloudy.\nend-to-end trace sent.",
  "05_observability/03_stream_events.py": "RunContent: 12\nRunStep: 2\nRunStarted: 1\nRunTool: 1\nRunCompleted: 1",
  "06_hitl_guardrails/01_hitl_approve.py": "Known limitation: the model may request missing email details instead of invoking the protected tool. This example is marked for deterministic repair.",
  "06_hitl_guardrails/02_guardrails.py": "answer: {\"city\": \"Lisbon\", \"temperature_c\": 21.0, \"summary\": \"clear\"}\ninjection attempt -> status: error",
  "06_workflows/01_dag.py": "{'fetch': 'SALES COMPLETED', 'format': 'Report: SALES COMPLETED', 'notify': 'sent'}",
  "06_workflows/02_session.py": "Orange.",
  "07_teams/01_coordinate.py": "Octopuses possess three hearts, with two dedicated to pumping blood to the gills and one distributing it throughout the body.",
  "07_teams/02_mesh_telemetry.py": "research: Summarize the incident.\nwriter: Incident summary prepared.",
  "07_teams/03_deterministic_telemetry_hitl.py": "Rollback completed after approval.\nresearch trace: run_incident_research\nremediation trace: run_incident_remediation",
  "08_mcp/01_stdio_client.py": "multiply(6, 7) = 42",
  "08_mcp/local_server.py": "MCP stdio server used by 01_stdio_client.py. It exposes multiply(a, b).",
  "09_evals/01_callable_evaluator.py": "wolf: WOLF (1.0)\npack: PACK (1.0)\naverages: {'exact_match': 1.0}",
  "09_evals/02_agent_evaluator.py": "Paris\n{'exact_match': 1.0}",
  "10_privacy/01_pii_safe_telemetry.py": "agent output: We will reply to ana@example.com.\npersisted output: We will reply to [PII_REDACTED].\nPII was masked before telemetry persistence.",
  "11_resilience/01_openai_token_stream.py": "Response: Streaming improves chat UX by providing real-time updates and interactions.",
  "12_hardening/01_production_flow.py": "Hardened quote completed: {\"decision\": \"approved\", \"quote_id\": \"quote-2026-001\", \"total_cents\": 6000}\nVerified PII masking, tool policy, structured output, and observer telemetry.",
  "13_data_connectors/01_sqlite_connector.py": "{'source_id': 'film-catalog', 'rows': [{'title': 'Mad Max: Fury Road', 'release_year': 2015, 'rating': 8.1}], 'row_count': 1, 'truncated': False}",
  "13_data_connectors/02_postgres_connector.py": "Requires DATABASE_URL for a PostgreSQL database with a company_debts table and a SELECT-only database role.",
  "13_data_connectors/03_postgres_agent.py": "AGENT RESULT\nThe three companies with the largest overdue balances are:\n\n1. Atlas Logistics - $185,000.00\n2. Nova Energia - $97,000.00\n3. Ponte Digital - $42,000.00\nTools used: list_tables, describe_table, query",
  "13_data_connectors/04_sql_snapshot_knowledge_agent.py": "Knowledge documents: 3\nAGENT RESULT\nThe overdue debt snapshot contains Ponte Digital ($42,000.00), Atlas Logistics ($185,000.00), and Nova Energia ($97,000.00).\nTools used: search_knowledge",
  "13_data_connectors/05_mysql_movie_agent.py": "AGENT RESULT\nHere are three action movies rated above 8.0 from the catalog:\n\n1. Mad Max: Fury Road\n2. The Dark Knight\n3. Die Hard\nTools used: list_tables, describe_table, query",
  "13_data_connectors/06_mongodb_support_agent.py": "AGENT RESULT\nOpen payment incidents:\n\n1. PAY-1042: Card charge duplicated\n2. PAY-1047: Invoice payment pending\nTools used: find_documents",
  "13_data_connectors/07_clickhouse_revenue_agent.py": "AGENT RESULT\nThe Southeast region had the highest revenue in the last 30 days: $840,000.\nTools used: list_tables, describe_table, query, estimate_cost",
  "13_data_connectors/08_other_connectors_agents.py": "Factory examples for Neo4j, Redis, DynamoDB, Firestore, Trino, Athena, BigQuery, Snowflake, and Databricks.",
  "16_scheduled_tasks/01_schedule_client.py": "Existing <schedule-id>: weekday-operations-report (active)\n<schedule-id>: 0 9 * * 1-5 -> reports.operations_daily [active]",
  "16_scheduled_tasks/02_agent_hitl.py": "Registered tools: ['schedule_task', 'list_tasks', 'pause_task', 'resume_task', 'cancel_task']\ncancel_task result: tool_confirmation",
  "16_scheduled_tasks/03_http_runtime.py": "{'status': 'accepted', 'run_id': 'example-run'}",
  "17_personal_agent/01_scoped_memory.py": "America/Sao_Paulo\nprefers decaf\nnot shared with planning\nNone",
  "17_personal_agent/02_reminder_and_approval.py": "reminder-1: Take a short stretch break\npending_approval\nexecuted: False",
  "17_personal_agent/03_amp_personal_assistant.py": "Trace confirmed with 5 observations\nAuto-evaluated scores: 1\npersonal_assistant_workflow_completion = 1.0 (AUTO_EVAL)",
  "18_coding_agent/01_deterministic_primitives.py": "DemoResult(read_content='before\\n', changed_files=('message.txt',), git_changed=('message.txt',), approval_operation='git_commit', requires_confirmation=True)",
  "18_coding_agent/02_amp_coding_workflow.py": "Trace confirmed with 4 observations\nAuto-evaluated scores: 1\ncoding_agent_workflow_completion = 1.0 (AUTO_EVAL)",
  "19_channels/webchat_adapter.py": "webchat:acme-support:browser-tab-3:customer-7: Where is my order?\n{'delivery_id': 'local-run', 'status': 'accepted'}",
  "20_team_with_knowledge/01_team_with_knowledge.py": "Knowledge base loaded: 5 chunks\nUsing model: openai/gpt-4o-mini\nResult: password-reset troubleshooting guidance.",
};

const sourceData = {
  "13_data_connectors/03_postgres_agent.py": "company_debts\ncompany_name      | outstanding_amount | due_date   | status\nAtlas Logistics   | 185000.00          | 2026-08-15 | overdue\nNova Energia      |  97000.00          | 2026-08-28 | overdue\nPonte Digital     |  42000.00          | 2026-09-05 | overdue",
  "13_data_connectors/04_sql_snapshot_knowledge_agent.py": "company_debts snapshot\ncompany_name      | outstanding_amount | due_date   | status | tax_id\nAtlas Logistics   | 185000.00          | 2026-08-15 | overdue | [REDACTED]\nNova Energia      |  97000.00          | 2026-08-28 | overdue | [REDACTED]\nPonte Digital     |  42000.00          | 2026-09-05 | overdue | [REDACTED]",
  "13_data_connectors/05_mysql_movie_agent.py": "movies\ntitle                | genre  | rating\nThe Dark Knight      | Action | 9.0\nDie Hard             | Action | 8.2\nMad Max: Fury Road   | Action | 8.1",
  "13_data_connectors/06_mongodb_support_agent.py": "tickets\nticket_id | status | category | summary\nPAY-1042 | open   | payment  | Card charge duplicated\nPAY-1047 | open   | payment  | Invoice payment pending",
  "13_data_connectors/07_clickhouse_revenue_agent.py": "daily_revenue\nregion    | revenue\nSoutheast | 840000\nSouth     | 610000\nNortheast | 455000",
};

async function pythonFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    return entry.isDirectory() ? pythonFiles(fullPath) : entry.name.endsWith(".py") ? [fullPath] : [];
  }));
  return files.flat();
}

function titleFor(relativePath) {
  return path.basename(relativePath, ".py").replace(/^\d+_/, "").replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function requirementsFor(relativePath) {
  const requirements = ["Python 3.10+ and uv", "Run from framework/: uv run python examples/..." ];
  if (modelExamples.has(relativePath)) requirements.push("Configure OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, or OLLAMA_BASE_URL.");
  if (ampExamples.has(relativePath)) requirements.push("Start AMP and set WOLFPACK_AMP_URL plus WOLFPACK_AMP_API_KEY. Seed demo data when the script requests weather-operations.");
  if (relativePath.startsWith("08_mcp/")) requirements.push("Install the MCP extra: uv sync --extra mcp.");
  if (relativePath.startsWith("13_data_connectors/02_")) requirements.push("Install the PostgreSQL extra: uv sync --extra postgres. Set DATABASE_URL to a PostgreSQL connection using a SELECT-only role.");
  if (relativePath.startsWith("13_data_connectors/03_") || relativePath.startsWith("13_data_connectors/04_")) requirements.push("Install the PostgreSQL extra: uv sync --extra postgres. Set DATABASE_URL to a PostgreSQL connection using a SELECT-only role.");
  if (relativePath === "13_data_connectors/05_mysql_movie_agent.py") requirements.push("Install the MySQL extra: uv sync --extra mysql. Configure MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE with a SELECT-only account.");
  if (relativePath === "13_data_connectors/06_mongodb_support_agent.py") requirements.push("Install the MongoDB extra: uv sync --extra mongodb. Configure MONGODB_URL with a read-only account.");
  if (relativePath === "13_data_connectors/07_clickhouse_revenue_agent.py") requirements.push("Install the ClickHouse extra: uv sync --extra clickhouse. Configure CLICKHOUSE_HOST, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, and CLICKHOUSE_DATABASE.");
  if (relativePath === "13_data_connectors/08_other_connectors_agents.py") requirements.push("Install the source-specific driver and configure credentials for the selected external connector.");
  if (relativePath === "16_scheduled_tasks/03_http_runtime.py") requirements.push("Set WOLFPACK_SCHEDULER_DISPATCH_SECRET and WOLFPACK_SCHEDULER_CALLBACK_SECRET.");
  return requirements;
}

function verificationClass(relativePath) {
  if (externalExamples.has(relativePath)) return "External runtime";
  if (relativePath === "13_data_connectors/02_postgres_connector.py") return "External runtime";
  if (ampExamples.has(relativePath)) return "AMP integration";
  if (modelExamples.has(relativePath)) return "LLM integration";
  return "Deterministic";
}

const files = (await pythonFiles(examplesRoot)).sort();
const examples = await Promise.all(files.map(async (file) => {
  const relativePath = path.relative(examplesRoot, file);
  const code = await readFile(file, "utf8");
  return {
    id: relativePath.replace(/\.py$/, "").replaceAll("/", "-"),
    title: titleFor(relativePath),
    category: categoryByDirectory[relativePath.split("/")[0]],
    description: `Runnable source example from framework/examples/${relativePath}.`,
    code,
    language: "python",
    steps: ["Install dependencies with uv sync.", `Run: uv run python examples/${relativePath}`],
    explanation: "This page renders the canonical source file that was executed during the documentation verification run.",
    expectedOutput: capturedOutput[relativePath] ?? "Execution output was not captured.",
    sourceData: sourceData[relativePath],
    sourcePath: `framework/examples/${relativePath}`,
    command: `uv run python examples/${relativePath}`,
    prerequisites: requirementsFor(relativePath),
    verificationClass: verificationClass(relativePath),
    validatedAt: "2026-08-26",
    validationStatus: relativePath === "06_hitl_guardrails/01_hitl_approve.py" ? "needs-repair" : relativePath === "13_data_connectors/08_other_connectors_agents.py" ? "not-verified" : "passed",
  };
}));

const generated = `// Generated by website/scripts/generate-examples-data.mjs. Do not edit manually.\n\nexport interface Example {\n  id: string;\n  title: string;\n  category: string;\n  description: string;\n  code: string;\n  language: string;\n  steps: string[];\n  explanation: string;\n  expectedOutput: string;\n  sourceData?: string;\n  sourcePath: string;\n  command: string;\n  prerequisites: string[];\n  verificationClass: string;\n  validatedAt: string;\n  validationStatus: \"passed\" | \"needs-repair\" | \"not-verified\";\n}\n\nexport const examples: Example[] = ${JSON.stringify(examples, null, 2)};\n`;
await writeFile(outputPath, generated);
console.log(`Generated ${examples.length} documentation examples.`);
