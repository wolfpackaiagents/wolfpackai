export interface SectionContent {
  id: string;
  title: string;
  description: string;
  parameters?: { name: string; type: string; required?: boolean; default?: string; description: string }[];
  codeExamples?: { title: string; language: string; code: string }[];
}

export const controlPlaneSections: SectionContent[] = [
  {
    id: "overview",
    title: "Dashboard & Overview",
    description:
      "The Dashboard is the main operational hub of the AMP. It provides a real-time summary of all agent activity, including throughput, latency, errors, cost, guardrail alerts, and active schedules. KPIs are displayed at the top, followed by execution analytics charts and a detailed execution register showing recent traces with session, environment, latency, and cost information. The dashboard respects the global context selector, allowing you to filter by environment and agent registration.",
  },
  {
    id: "mesh",
    title: "Mesh Registry",
    description:
      "The Mesh Registry is the agent inventory and runtime management surface of the AMP. It organizes agents and teams into controlled environments (development, staging, production) with versioned definitions. Each environment shows which agents or teams are registered, their health status (online, degraded, offline, unknown), and the number of active runtime replicas. The Mesh also displays an observed communication graph (Flow view) showing agent-to-agent interactions, delegation patterns, and tool calls with trace drill-down. Operators can create, edit, enable, disable, and delete environments, definitions, and registrations. Each registration can be configured with a chat_endpoint for external runtime dispatch.",
  },
  {
    id: "chat",
    title: "Chat",
    description:
      "The Chat interface provides a persistent multi-session conversation workspace. Users can create multiple conversations, rename them, delete them, and select different registered runtimes (agents or teams) as targets. Each conversation maintains a stable session_id across turns, preserving agent memory and context. The run inspector panel shows status, scope, and trace links. The composer supports real-time streaming via SSE (Server-Sent Events). When a registration has a chat_endpoint configured, the AMP dispatches the message to the external agent runtime and returns the response. If no chat_endpoint is configured, the target is shown as unavailable in the selector.",
  },
  {
    id: "channels",
    title: "Channels",
    description:
      "Channels connect external messaging platforms to the AMP, enabling users to interact with agents through Telegram, Slack, Discord, and the built-in Web Chat. Each channel connection is configured with a specific agent registration, provider credentials stored in the encrypted vault, and an allowlist of authorized chat IDs or workspaces. The Channels page lists all configured connections with health status, last delivery information, and enables/disables connections. A provider setup guide is available for each credential field, showing the webhook path, required credentials, and verification checklist. The delivery receipts section shows all inbound/outbound message history with trace links.",
  },
  {
    id: "schedules",
    title: "Schedules",
    description:
      "Schedules provide durable, governed task execution for agents. Users can create schedules with at, interval, or cron triggers with timezone support. Each schedule specifies a registration target and a structured payload containing an execution instruction and parameters. The schedule editor supports retry policies, misfire handling, and maximum attempts. Schedule lifecycle includes pause, resume, cancel, and run-now actions. Execution history shows each run with status, timing, retry count, and trace links. Policies control which API keys can create, update, or cancel schedules, with optional approval gate for mutating operations.",
  },
  {
    id: "traces",
    title: "Traces & Sessions",
    description:
      "Traces provide end-to-end observability of every agent run. Each trace captures the complete execution tree including root span, generation calls (LLM), tool invocations, delegation spans (for teams), and approval events. The trace detail view shows a Flow visualization, Timeline, Tree, and Inspector with input/output, model, usage, cost, and duration for each observation. Sessions group related traces by a shared session_id, providing conversation-level observability. The traces list supports filtering by name, session, environment, agent registration, and time range. Scores are displayed on each trace for quality evaluation.",
  },
  {
    id: "scores",
    title: "Scores & Quality",
    description:
      "The Scores page provides quality intelligence for agent runs. It displays KPIs for scored evidence count, numeric coverage, mean quality, and metric definitions. A quality trend chart shows score values over time, and a coverage-by-metric breakdown shows sample distribution. The recent evidence table lists individual scores with trace links, values, sources, and comments. Scores are auto-generated by the AMP ingestion pipeline (AUTO_EVAL source) and can also be created manually or via eval runs (EVAL source). Quality overview aggregates are available per metric with average and count.", 
  },
  {
    id: "guardrails",
    title: "Guardrails & Alerts",
    description:
      "Guardrails and Alerts provide safety monitoring for agent operations. The Guardrails page shows policy-blocked events with severity levels, source, event type, trace links, and lifecycle actions (acknowledge, resolve). Alert rules can be created to classify incoming events by source and event type with configurable severity. The Resilience view shows ingestion queue health with processing metrics, an event stream of operational alerts, and managed alert rules with enable/disable, edit, and delete controls. Alert rules support a typed taxonomy of sources and event types.",
  },
  {
    id: "approvals",
    title: "Approvals",
    description:
      "The Approvals page provides a centralized human-in-the-loop (HITL) review queue. Each approval request shows the tool name, arguments, trace context with session, environment, agent registration, and definition details. Operators can approve, reject, or provide user input/feedback for pending approvals. The resolution is recorded with the operator's identity and timestamp, forming a complete compliance audit trail. Approvals are linked to their originating traces, enabling drill-down from an approval decision to the full agent execution context.",
  },
  {
    id: "resilience",
    title: "Resilience & Queue",
    description:
      "The Resilience page monitors the AMP ingestion pipeline health. It shows queue processing metrics (pending, processing, failed, completed counts, retries, and latency percentiles). The event stream lists operational alerts from ingestion failures, guardrail violations, and other system events with severity, source, and lifecycle actions. Managed alert rules allow operators to configure event classification rules that determine alert severity based on event source and type.",
  },
  {
    id: "privacy",
    title: "Privacy & PII",
    description:
      "The Privacy page provides data protection controls for the AMP. Operators can configure PII redaction settings including email, phone, CPF, and credit card pattern masking, plus custom regex patterns. The data subject request section supports user data export and deletion with audit logging. All redaction is applied before telemetry persistence, ensuring sensitive data never reaches the database. The privacy audit log records all data subject requests with hashed identifiers for accountability without storing raw PII.",
  },
  {
    id: "settings",
    title: "Settings & Governance",
    description:
      "The Settings page provides governance and administration controls. Operators can configure retention policies for trace data, manage API keys with role-based access (read_only, editor, admin), and view organization and project information. The governance section supports role-permission matrices that define what each role can read, write, and manage. Bootstrap actions for creating organizations and projects are available.",
  },
  {
    id: "secrets",
    title: "Provider Secrets & Vault",
    description:
      "The Provider Secrets Vault provides encrypted storage for external service credentials. Secrets are encrypted at rest using envelope encryption with a configurable master key, and are never returned in plaintext after creation. The vault supports creating, rotating, and deleting secrets with version tracking and audit logging. Channel connections reference secrets by ID rather than storing credential values directly. Each secret is scoped to a project and provider type (telegram, slack, discord).",
  },
];