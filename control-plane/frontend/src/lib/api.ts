import axios from 'axios'
import { useScopeStore } from '../stores/context'
import type {
  CreateScoreConfigInput,
  CreateScoreInput,
  Approval,
  ApprovalStatus,
  GovernanceSettings,
  MetricPoint,
  PrivacySettings,
  PrivacyAuditRecord,
  ResilienceAlert,
  ResilienceOverview,
  AlertRule,
  AlertRuleInput,
  AlertRuleTaxonomy,
  AlertStatus,
  AlertDestination,
  AlertDestinationInput,
  Score,
  ScoreConfig,
  SessionSummary,
  SessionDetail,
  TraceListResponse,
  TraceSummary,
  MeshCatalog,
  MeshGraph,
  MeshInteraction,
  MeshDefinition,
  MeshEnvironment,
  MeshRegistration,
  MeshKind,
  Schedule,
  ScheduleInput,
  ScheduleRun,
  ScheduleStatus,
  ChannelConnection,
  ChannelConnectionInput,
  ChannelDelivery,
  ChannelProvider,
  ProviderSecret,
  ProviderSecretInput,
  ChatConversation,
  ChatRun,
  ChatRunEvent,
} from './types'

const api = axios.create({ baseURL: '/api' })

const AUTH_KEY = 'wolfpack_api_key'

export type ScopeParams = {
  environment_id?: string
  registration_id?: string
  from?: string
  to?: string
}

export function scopeParams(environmentId: string, registrationId: string, range: string): ScopeParams {
  const hours = { '1h': 1, '24h': 24, '7d': 24 * 7, '30d': 24 * 30 }[range] ?? 24
  const to = new Date()
  return {
    environment_id: environmentId || undefined,
    registration_id: registrationId || undefined,
    from: new Date(to.getTime() - hours * 60 * 60 * 1000).toISOString(),
    to: to.toISOString(),
  }
}

export function getApiKey(): string {
  return localStorage.getItem(AUTH_KEY) || ''
}

export function setApiKey(key: string): void {
  localStorage.setItem(AUTH_KEY, key)
}

api.interceptors.request.use((config) => {
  const key = getApiKey()
  if (key) config.headers['X-API-Key'] = key
  if (config.method?.toLowerCase() === 'get' && config.url?.startsWith('/public/') && !config.url.startsWith('/public/chat/')) {
    const { environmentId, registrationId, range } = useScopeStore.getState()
    const explicitParams = Object.fromEntries(Object.entries(config.params ?? {}).filter(([, value]) => value !== undefined))
    config.params = { ...scopeParams(environmentId, registrationId, range), ...explicitParams }
  }
  return config
})

export async function fetchTraces(params?: {
  name?: string
  env?: string
  session_id?: string
  page?: number
  per_page?: number
  environment_id?: string
  registration_id?: string
  from?: string
  to?: string
}): Promise<TraceListResponse> {
  const { data } = await api.get<TraceListResponse>('/public/traces', { params })
  return data
}

export async function fetchTrace(id: string): Promise<TraceSummary> {
  const { data } = await api.get<TraceSummary>(`/public/traces/${id}`)
  return data
}

export async function fetchMetrics(params?: ScopeParams): Promise<MetricPoint[]> {
  const { data } = await api.get<MetricPoint[]>('/public/metrics', { params: { group_by: 'hour', ...params } })
  return data
}

export async function fetchSessions(params?: ScopeParams): Promise<SessionSummary[]> {
  const { data } = await api.get<SessionSummary[]>('/public/sessions', { params })
  return data
}

export async function fetchSession(id: string): Promise<SessionDetail> {
  const { data } = await api.get<SessionDetail>(`/public/sessions/${encodeURIComponent(id)}`)
  return data
}

export async function fetchApprovals(status?: ApprovalStatus): Promise<Approval[]> {
  const { data } = await api.get<Approval[]>('/public/approvals', { params: { status } })
  return data
}

export async function resolveApproval(approvalId: string, action: 'approve' | 'reject', note?: string): Promise<Approval> {
  const { data } = await api.post<Approval>(`/public/approvals/${encodeURIComponent(approvalId)}/resolve`, { action, note: note || undefined })
  return data
}

export async function fetchAlerts(params?: { source?: string; limit?: number }): Promise<ResilienceAlert[]> {
  const { data } = await api.get<ResilienceAlert[]>('/public/alerts', { params })
  return data
}

export async function updateAlertLifecycle(alertId: string, status: Exclude<AlertStatus, 'open'>): Promise<ResilienceAlert> {
  const { data } = await api.patch<ResilienceAlert>(`/public/alerts/${encodeURIComponent(alertId)}`, { status })
  return data
}

export async function fetchAlertRules(): Promise<AlertRule[]> {
  const { data } = await api.get<AlertRule[]>('/public/alert-rules')
  return data
}

export async function fetchAlertRuleTaxonomy(): Promise<AlertRuleTaxonomy> {
  const { data } = await api.get<AlertRuleTaxonomy>('/public/alert-rules/taxonomy')
  return data
}

export async function createAlertRule(input: AlertRuleInput): Promise<AlertRule> {
  const { data } = await api.post<AlertRule>('/public/alert-rules', input)
  return data
}

export async function updateAlertRule(ruleId: string, input: Partial<AlertRuleInput>): Promise<AlertRule> {
  const { data } = await api.patch<AlertRule>(`/public/alert-rules/${encodeURIComponent(ruleId)}`, input)
  return data
}

export async function deleteAlertRule(ruleId: string): Promise<void> {
  await api.delete(`/public/alert-rules/${encodeURIComponent(ruleId)}`)
}

export async function fetchAlertDestinations(): Promise<AlertDestination[]> {
  const { data } = await api.get<AlertDestination[]>('/public/alert-destinations')
  return data
}

export async function createAlertDestination(input: AlertDestinationInput): Promise<AlertDestination> {
  const { data } = await api.post<AlertDestination>('/public/alert-destinations', input)
  return data
}

export async function updateAlertDestination(id: string, input: Partial<AlertDestinationInput & { name: string }>): Promise<AlertDestination> {
  const { data } = await api.patch<AlertDestination>(`/public/alert-destinations/${encodeURIComponent(id)}`, input)
  return data
}

export async function deleteAlertDestination(id: string): Promise<void> {
  await api.delete(`/public/alert-destinations/${encodeURIComponent(id)}`)
}

export async function testAlertDestination(id: string): Promise<void> {
  await api.post(`/public/alert-destinations/${encodeURIComponent(id)}/test`)
}

export async function fetchGovernanceSettings(): Promise<GovernanceSettings> {
  const { data } = await api.get<GovernanceSettings>('/public/governance/settings')
  return data
}

export async function updateGovernanceSettings(input: GovernanceSettings): Promise<GovernanceSettings> {
  const { data } = await api.put<GovernanceSettings>('/public/governance/settings', input)
  return data
}

export async function fetchScoreConfigs(): Promise<ScoreConfig[]> {
  const { data } = await api.get<ScoreConfig[]>('/public/score-configs')
  return data
}

export async function createScoreConfig(input: CreateScoreConfigInput): Promise<ScoreConfig> {
  const { data } = await api.post<ScoreConfig>('/public/score-configs', input)
  return data
}

export async function fetchScores(params?: ScopeParams): Promise<Score[]> {
  const { data } = await api.get<Score[]>('/public/scores', { params })
  return data
}

export async function createScore(input: CreateScoreInput): Promise<Score> {
  const { data } = await api.post<Score>('/public/scores', input)
  return data
}

export async function fetchPrivacySettings(): Promise<PrivacySettings> {
  const { data } = await api.get<PrivacySettings>('/public/privacy/config')
  return data
}

export async function updatePrivacySettings(input: PrivacySettings): Promise<PrivacySettings> {
  const { data } = await api.put<PrivacySettings>('/public/privacy/config', input)
  return data
}

export async function fetchPrivacyAuditLog(): Promise<PrivacyAuditRecord[]> {
  const { data } = await api.get<PrivacyAuditRecord[]>('/public/privacy/audit')
  return data
}

export async function fetchResilienceOverview(): Promise<ResilienceOverview> {
  const [metrics, alerts] = await Promise.all([
    api.get<ResilienceOverview['queue']>('/public/observability/ingestion-metrics'),
    api.get<ResilienceOverview['alerts']>('/public/alerts'),
  ])
  return { queue: metrics.data, alerts: alerts.data }
}

export async function exportDataSubject(userId: string): Promise<Blob> {
  const { data } = await api.get<Blob>(`/public/users/${encodeURIComponent(userId)}/export`, {
    responseType: 'blob',
  })
  return data
}

export async function deleteDataSubject(userId: string): Promise<void> {
  await api.delete(`/public/users/${encodeURIComponent(userId)}`)
}

export function isFeatureUnavailable(error: unknown): boolean {
  return axios.isAxiosError(error) && [404, 405, 501].includes(error.response?.status ?? 0)
}

export async function healthCheck(): Promise<boolean> {
  try {
    const { data } = await api.get('/health')
    return data.status === 'ok'
  } catch {
    return false
  }
}

export async function fetchMeshCatalog(params?: Pick<ScopeParams, 'environment_id' | 'registration_id'>): Promise<MeshCatalog> {
  const { data } = await api.get<MeshCatalog>('/public/mesh/catalog', { params })
  return data
}

export async function fetchMeshGraph(params?: ScopeParams): Promise<MeshGraph> {
  const { data } = await api.get<MeshGraph>('/public/mesh/graph', { params })
  return data
}

export async function fetchMeshInteractions(params?: ScopeParams): Promise<MeshInteraction[]> {
  const { data } = await api.get<MeshInteraction[]>('/public/mesh/interactions', { params: { ...params, limit: 500 } })
  return data
}

export async function fetchSchedules(status?: ScheduleStatus, registration_id?: string): Promise<Schedule[]> {
  const { data } = await api.get<Schedule[]>('/public/schedules', { params: { status, registration_id } })
  return data
}

export async function createSchedule(input: ScheduleInput): Promise<Schedule> {
  const { data } = await api.post<Schedule>('/public/schedules', input)
  return data
}

export async function updateSchedule(id: string, input: Partial<ScheduleInput>): Promise<Schedule> {
  const { data } = await api.patch<Schedule>(`/public/schedules/${encodeURIComponent(id)}`, input)
  return data
}

export async function scheduleAction(id: string, action: 'pause' | 'resume' | 'cancel' | 'run-now'): Promise<void> {
  if (action === 'cancel') { await api.delete(`/public/schedules/${encodeURIComponent(id)}`); return }
  await api.post(`/public/schedules/${encodeURIComponent(id)}/${action}`, action === 'run-now' ? { idempotency_key: crypto.randomUUID() } : undefined)
}

export async function fetchScheduleRuns(id: string): Promise<ScheduleRun[]> {
  const { data } = await api.get<ScheduleRun[]>(`/public/schedules/${encodeURIComponent(id)}/runs`)
  return data
}

export async function fetchChannelConnections(): Promise<ChannelConnection[]> {
  const { data } = await api.get<ChannelConnection[]>('/public/channels/connections')
  return data
}

export async function fetchProviderSecrets(): Promise<ProviderSecret[]> {
  const { data } = await api.get<ProviderSecret[]>('/public/provider-secrets')
  return data
}

export async function createProviderSecret(input: ProviderSecretInput): Promise<ProviderSecret> {
  const { data } = await api.post<ProviderSecret>('/public/provider-secrets', input)
  return data
}

export async function rotateProviderSecret(id: string, value: string): Promise<ProviderSecret> {
  const { data } = await api.patch<ProviderSecret>(`/public/provider-secrets/${encodeURIComponent(id)}`, { value })
  return data
}

export async function createChannelConnection(input: ChannelConnectionInput): Promise<ChannelConnection> {
  const { data } = await api.post<ChannelConnection>('/public/channels/connections', input)
  return data
}

export async function updateChannelConnection(id: string, input: Partial<ChannelConnectionInput>): Promise<ChannelConnection> {
  const { data } = await api.patch<ChannelConnection>(`/public/channels/connections/${encodeURIComponent(id)}`, input)
  return data
}

export async function deleteChannelConnection(id: string): Promise<void> {
  await api.delete(`/public/channels/connections/${encodeURIComponent(id)}`)
}

export async function fetchChannelDeliveries(channel?: ChannelProvider): Promise<ChannelDelivery[]> {
  const { data } = await api.get<ChannelDelivery[]>('/public/channels/deliveries', { params: { channel } })
  return data
}

export async function createMeshEnvironment(input: { slug: string; name: string; description?: string }): Promise<MeshEnvironment> {
  const { data } = await api.post<MeshEnvironment>('/public/mesh/environments', input)
  return data
}

export async function updateMeshEnvironment(id: string, input: { name?: string; description?: string; labels?: Record<string, string>; status?: 'active' | 'inactive' }): Promise<MeshEnvironment> {
  const { data } = await api.patch<MeshEnvironment>(`/public/mesh/environments/${encodeURIComponent(id)}`, input)
  return data
}

export async function deleteMeshEnvironment(id: string): Promise<void> {
  await api.delete(`/public/mesh/environments/${encodeURIComponent(id)}`)
}

export async function createMeshDefinition(input: { key: string; kind: MeshKind; name: string; version: string; description?: string; summary?: Record<string, unknown> }): Promise<MeshDefinition> {
  const { data } = await api.post<MeshDefinition>('/public/mesh/definitions', input)
  return data
}

export async function createMeshRegistration(input: { environment_id: string; definition_id: string }): Promise<MeshRegistration> {
  const { data } = await api.post<MeshRegistration>('/public/mesh/registrations', input)
  return data
}

export async function updateMeshRegistration(id: string, input: { enabled?: boolean; tags?: string[] }): Promise<MeshRegistration> {
  const { data } = await api.patch<MeshRegistration>(`/public/mesh/registrations/${encodeURIComponent(id)}`, input)
  return data
}

export async function deleteMeshRegistration(id: string): Promise<void> {
  await api.delete(`/public/mesh/registrations/${encodeURIComponent(id)}`)
}

export async function fetchChatConversations(): Promise<ChatConversation[]> {
  const { data } = await api.get<ChatConversation[]>('/public/chat/conversations')
  return data
}

export async function fetchChatConversation(id: string): Promise<ChatConversation> {
  const { data } = await api.get<ChatConversation>(`/public/chat/conversations/${encodeURIComponent(id)}`)
  return data
}

export async function createChatConversation(registrationId: string): Promise<ChatConversation> {
  const { data } = await api.post<ChatConversation>('/public/chat/conversations', { registration_id: registrationId })
  return data
}

export async function renameChatConversation(id: string, title: string): Promise<ChatConversation> {
  const { data } = await api.patch<ChatConversation>(`/public/chat/conversations/${encodeURIComponent(id)}`, { title })
  return data
}

export async function deleteChatConversation(id: string): Promise<void> {
  await api.delete(`/public/chat/conversations/${encodeURIComponent(id)}`)
}

export async function startChatRun(input: { conversation_id: string; message: string }): Promise<ChatRun> {
  const { data } = await api.post<ChatRun>(`/public/chat/conversations/${encodeURIComponent(input.conversation_id)}/runs`, { message: input.message, idempotency_key: crypto.randomUUID() })
  return data
}

export async function streamChatRun(runId: string, onEvent: (event: ChatRunEvent) => void): Promise<void> {
  const response = await fetch(`/api/public/chat/runs/${encodeURIComponent(runId)}/events`, { headers: { 'X-API-Key': getApiKey() } })
  if (!response.ok || !response.body) throw new Error('Unable to stream the selected runtime.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false

  function consumeEvent(rawEvent: string) {
    const lines = rawEvent.split('\n')
    const eventName = lines.find((line) => line.startsWith('event: '))?.slice(7)
    const dataLines = lines.filter((line) => line.startsWith('data: ')).map((line) => line.slice(6))
    if (!eventName || !dataLines.length) return
    const payload = JSON.parse(dataLines.join('\n')) as Omit<ChatRunEvent, 'type'>
    onEvent({ type: eventName as ChatRunEvent['type'], ...payload })
    completed ||= eventName === 'message.completed' || eventName === 'run.completed'
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''
    events.forEach(consumeEvent)
    if (done) break
  }
  if (buffer.trim()) consumeEvent(buffer)
}

export { api }
