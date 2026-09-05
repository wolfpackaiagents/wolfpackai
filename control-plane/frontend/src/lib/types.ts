export interface TraceSummary {
  id: string
  name: string
  timestamp: string
  start_time: string | null
  end_time: string | null
  session_id: string | null
  environment: string | null
  input: unknown
  output: unknown
  latency_ms: number | null
  cost: CostValue | null
  cost_currency?: string | null
  cost_coverage?: CostCoverage | null
  observations: Observation[]
  scores: Score[]
}

export type ObservationType =
  | 'TRACE'
  | 'SPAN'
  | 'GENERATION'
  | 'TOOL'
  | 'EVENT'
  | 'RETRIEVER'
  | 'AGENT'
  | 'CHAIN'

export interface Observation {
  id: string
  type: ObservationType
  name: string
  parent_observation_id: string | null
  start_time: string | null
  end_time: string | null
  model: string | null
  usage: { input_tokens?: number; output_tokens?: number } | null
  input: unknown
  output: unknown
  level: string
  status_message: string | null
  cost: CostValue | null
  cost_currency?: string | null
  cost_coverage?: CostCoverage | null
  metadata: Record<string, unknown> | null
}

export interface Score {
  id: string
  trace_id?: string
  name: string
  data_type: string
  value: number | null
  string_value: string | null
  source: string
  comment: string | null
}

export interface ScoreConfig {
  id: string
  name: string
  data_type: string
  description: string | null
  config: Record<string, unknown> | null
}

export interface CreateScoreConfigInput {
  name: string
  data_type: string
  description?: string
  config?: Record<string, unknown>
}

export interface CreateScoreInput {
  trace_id: string
  name: string
  value?: number
  string_value?: string
  comment?: string
  source?: string
}

export interface MetricPoint {
  bucket: string
  count: number
  latency_p50: number | null
  latency_p95: number | null
  total_tokens: number | null
  total_cost: CostValue | null
  cost_currency?: string | null
  total_cost_currency?: string | null
  cost_coverage?: CostCoverage | null
  errors: number
}

export interface TraceListResponse {
  traces: TraceSummary[]
  page: number
  per_page: number
  total: number
}

export type CostCoverage = { reported?: number; total?: number; reported_count?: number; total_count?: number; with_cost?: number; observations?: number }
export type CostValue = number | { amount?: number; total?: number; total_cost?: number; value?: number; currency?: string; coverage?: CostCoverage; cost_coverage?: CostCoverage }

export interface SessionSummary {
  session_id: string
  trace_count: number
  last_trace_at: string | null
  user_id: string | null
}

export interface SessionDetail {
  session_id: string
  user_id: string | null
  traces: Array<{
    id: string
    name: string
    timestamp: string | null
    input: unknown
    output: unknown
    error: string | null
  }>
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'resolved' | 'unauthorized'

export interface Approval {
  id: string
  approval_id: string
  trace_id: string | null
  trace_context: {
    trace: { id: string; name: string } | null
    session_id: string | null
    environment: { id: string; slug: string; name: string } | null
    registration: { id: string } | null
    definition: { id: string; key: string; name: string; version: string } | null
  } | null
  tool_name: string
  tool_arguments: Record<string, unknown> | null
  requirement: string
  tool_call_id: string | null
  status: ApprovalStatus
  confirmation: boolean | null
  confirmation_note: string | null
  created_at: string | null
  resolved_at: string | null
  resolved_by: string | null
}

export interface GovernanceSettings {
  retention_days: number
  roles: Record<'read_only' | 'editor' | 'admin', Array<'read' | 'write' | 'manage'>>
}

export interface PrivacySettings {
  enabled: boolean
  redact_email: boolean
  redact_phone: boolean
  redact_cpf: boolean
  redact_credit_card: boolean
  custom_patterns: string[]
}

export interface PrivacyAuditRecord {
  id: string
  action: string
  subject_hash: string
  details: Record<string, unknown> | null
  created_at: string
}

export type AlertSeverity = 'critical' | 'error' | 'warning' | 'info'
export type AlertStatus = 'open' | 'acknowledged' | 'resolved'

export interface QueueMetrics {
  pending: number
  processing: number
  failed: number
  completed: number
  retries: number
  latency_ms: {
    average: number | null
    p50: number | null
    p95: number | null
  }
}

export interface ResilienceAlert {
  id: string
  severity: AlertSeverity
  message: string
  source: string
  event_type?: string
  trace_id?: string | null
  metadata?: Record<string, unknown> | null
  status: AlertStatus
  acknowledged_at?: string | null
  resolved_at?: string | null
  resolved_by?: string | null
  created_at: string
}

export interface AlertRule {
  id: string
  name: string
  source: string | null
  event_type: string | null
  severity: Exclude<AlertSeverity, 'critical'>
  enabled: boolean
  created_at: string | null
  updated_at: string | null
}

export interface AlertRuleInput {
  name: string
  source?: string | null
  event_type?: string | null
  severity: AlertRule['severity']
  enabled?: boolean
}

export type AlertRuleTaxonomy = Record<string, string[]>

export type AlertDestinationType = 'slack_webhook' | 'discord_webhook' | 'smtp'

export interface AlertDestination {
  id: string
  name: string
  destination_type: AlertDestinationType
  config: Record<string, unknown>
  enabled: boolean
  last_notified_at: string | null
  last_error: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AlertDestinationInput {
  name: string
  destination_type: AlertDestinationType
  config: Record<string, unknown>
  enabled: boolean
}

export interface ResilienceOverview {
  queue: QueueMetrics
  alerts: ResilienceAlert[]
}

export type MeshKind = 'agent' | 'team' | 'workflow'

export interface MeshDefinition {
  id: string
  key: string
  kind: MeshKind
  name: string
  version: string
  description: string | null
  summary: Record<string, unknown>
  artifact_digest: string | null
  policy_hash: string | null
  created_at: string
}

export interface MeshRegistration {
  id: string
  environment_id: string
  environment_slug: string
  definition_id: string
  definition_key: string
  definition_kind: MeshKind
  definition_name: string
  definition_version: string
  enabled: boolean
  online_replicas: number
  last_seen_at: string | null
  health_status: 'online' | 'degraded' | 'offline' | 'unknown'
  chat_endpoint: string | null
  tags: string[]
  created_at: string
  updated_at?: string
}

export interface MeshEnvironment {
  id: string
  slug: string
  name: string
  description: string | null
  status: string
  labels: Record<string, string>
  created_at: string
  updated_at?: string
  registrations: MeshRegistration[]
}

export interface MeshCatalog {
  summary: { environments: number; registrations: number; active_registrations: number }
  environments: MeshEnvironment[]
  definitions: MeshDefinition[]
}

export interface MeshGraph {
  nodes: Array<{ id: string; label: string }>
  edges: Array<{ source: string; target: string; source_display_name: string | null; target_display_name: string | null; interaction_type: string; operation: string | null; tool_name: string | null; count: number; last_seen: string }>
}

export interface MeshInteraction {
  id: string
  source: string
  target: string
  source_display_name: string | null
  target_display_name: string | null
  interaction_type: string
  operation: string | null
  tool_name: string | null
  trace_id: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export type ChannelProvider = 'telegram' | 'slack' | 'discord'
export interface ProviderSecret {
  id: string
  provider: ChannelProvider
  name: string
  value_masked: string
  version: number
  rotation_interval_days: number | null
  expires_at: string | null
  last_rotated_at: string | null
  created_at: string
  updated_at: string
}

export interface ProviderSecretInput {
  provider: ChannelProvider
  name: string
  value: string
  rotation_interval_days?: number | null
  expires_at?: string | null
}

export interface ChannelDelivery {
  id: string
  channel: ChannelProvider
  session_id: string
  status: 'pending' | 'delivered' | 'failed'
  attempts: number
  provider_message_id: string | null
  error: string | null
  created_at: string
  trace_id?: string | null
  trace_context?: { id: string; name: string } | null
}

export interface ChannelConnection {
  id: string
  channel: ChannelProvider
  name: string
  enabled: boolean
  secret_refs: Record<string, string>
  allowlist: string[]
  health: 'healthy' | 'degraded' | 'disabled' | 'unknown'
  registration: { id: string; enabled: boolean; environment_id: string; environment_name: string; definition_name: string; definition_version: string }
  last_delivery: ChannelDelivery | null
}

export interface ChannelConnectionInput {
  channel: ChannelProvider
  name: string
  registration_id: string
  enabled: boolean
  secret_refs: Record<string, string>
  allowlist: string[]
}

export type ScheduleStatus = 'active' | 'paused' | 'cancelled' | 'completed'
export type ScheduleRunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'retrying' | 'cancelled' | 'missed' | 'deadline_exceeded'
export interface Schedule {
  id: string
  registration_id: string
  name: string
  schedule_type: 'at' | 'interval' | 'cron'
  timezone: string
  at: string | null
  interval_seconds: number | null
  cron: string | null
  payload: Record<string, unknown>
  status: ScheduleStatus
  next_run_at: string | null
  last_run_at: string | null
  retry: { max_attempts: number; delay_seconds: number }
}
export interface ScheduleRun {
  id: string
  status: ScheduleRunStatus
  trigger: string
  scheduled_for: string
  attempt: number
  max_attempts: number
  retry_at: string | null
  error: string | null
  trace_id: string | null
  trace_context: { id: string; name: string } | null
}
export type ScheduleInput = Pick<Schedule, 'registration_id' | 'name' | 'schedule_type' | 'timezone' | 'at' | 'interval_seconds' | 'cron' | 'payload'> & { max_attempts: number; retry_delay_seconds: number }

export type ChatMessageRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: ChatMessageRole
  content: string
  created_at: string
  run_id?: string | null
  trace_id?: string | null
}

export interface ChatConversation {
  id: string
  title: string
  registration_id: string
  created_at: string
  updated_at: string
  messages?: ChatMessage[]
}

export interface ChatRun {
  run_id: string
  conversation_id: string
  warning: boolean
  health_status: 'online' | 'degraded' | 'offline' | 'unknown'
}

export interface ChatRunEvent {
  type: 'message.delta' | 'message.completed' | 'run.status' | 'run.failed' | 'run.started' | 'run.completed' | 'run.pending'
  content?: string
  trace_id?: string
  status?: string
  error?: string
}
