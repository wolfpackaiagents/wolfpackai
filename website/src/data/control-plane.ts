export interface SectionContent {
  id: string;
  title: string;
  description: string;
}

export const controlPlaneSections: SectionContent[] = [
  { id: "overview", title: "Dashboard", description: "The AMP dashboard summarizes trace volume, latency, token usage, cost, alerts, and recent activity within the selected environment and runtime scope." },
  { id: "traces", title: "Traces and Sessions", description: "Trace Explorer stores agent runs, nested spans, tool calls, model usage, cost, and errors. Sessions group related traces with a stable session identifier." },
  { id: "mesh", title: "Mesh", description: "Mesh registers versioned agent and team definitions in environments. It tracks registrations, runtime heartbeats, observed interactions, and trace context." },
  { id: "chat", title: "Chat", description: "Chat persists conversations and dispatches requests to enabled registered runtimes with a configured chat endpoint. Server-Sent Events report run lifecycle and final-result events." },
  { id: "approvals", title: "Approvals", description: "The approval queue resolves durable human-in-the-loop requirements. Each decision is linked to its run, trace scope, and audit context." },
  { id: "guardrails", title: "Guardrails and Alerts", description: "Guardrail events and managed alert rules provide an operational view of safety signals, ingestion failures, and their resolution lifecycle." },
  { id: "scores", title: "Scores and Evals", description: "Score configurations, manual scores, and evaluation runs attach quality evidence to traces and expose coverage and trend views." },
  { id: "schedules", title: "Schedules", description: "Schedules run registered runtimes at a time, interval, or cron cadence. Policies govern changes and execution history records retries and outcomes." },
  { id: "channels", title: "Channels", description: "Telegram, Slack, and Discord connections route supported provider webhooks to registered agents. Provider credentials are stored as encrypted project secrets." },
  { id: "privacy", title: "Privacy", description: "Privacy settings redact personally identifiable information before telemetry persistence and support export or deletion requests for a data subject." },
  { id: "resilience", title: "Resilience", description: "The resilience view exposes ingestion queue health, retries, failures, and operational alerts. Prometheus metrics are available at the backend metrics endpoint." },
  { id: "settings", title: "Settings and Governance", description: "Projects configure retention, role-based API keys, and governance policies. Administrative credentials create organizations, projects, and project API keys." },
  { id: "secrets", title: "Provider Secrets", description: "The provider secrets vault encrypts external credentials at rest. Channel connections reference a secret identifier instead of storing the credential value." },
];
