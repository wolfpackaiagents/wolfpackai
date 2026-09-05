import { create } from 'zustand'
import { fetchAlerts, fetchMetrics, fetchSchedules, fetchTraces, type ScopeParams } from '../lib/api'
import type { MetricPoint, TraceSummary } from '../lib/types'

interface DashboardState {
  traces: TraceSummary[]
  metrics: MetricPoint[]
  total: number
  guardrailAlerts: number
  activeSchedules: number
  loading: boolean
  error: string | null
  load: (params?: ScopeParams) => Promise<void>
}

export const useDashboardStore = create<DashboardState>((set) => ({
  traces: [],
  metrics: [],
  total: 0,
  guardrailAlerts: 0,
  activeSchedules: 0,
  loading: false,
  error: null,
  load: async (params) => {
    set({ loading: true, error: null })
    const [traceResult, metricResult, alertResult, scheduleResult] = await Promise.allSettled([
      fetchTraces({ per_page: 10, ...params }),
      fetchMetrics(params),
      fetchAlerts({ source: 'guardrail' }),
      fetchSchedules('active'),
    ])
    const traces = traceResult.status === 'fulfilled' ? traceResult.value : null
    const metrics = metricResult.status === 'fulfilled' ? metricResult.value : []
    const guardrailAlerts = alertResult.status === 'fulfilled' ? alertResult.value.length : 0
    const activeSchedules = scheduleResult.status === 'fulfilled' ? scheduleResult.value.length : 0
    const failures = [traceResult, metricResult, alertResult, scheduleResult]
      .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
      .map((result) => String(result.reason))
    set({
      traces: traces?.traces ?? [],
      metrics,
      total: traces?.total ?? 0,
      guardrailAlerts,
      activeSchedules,
      loading: false,
      error: failures.length ? failures.join(' · ') : null,
    })
  },
}))
