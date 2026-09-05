import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatDuration, formatNumber, formatTime } from '../i18n/format'
import { combineReportedCosts, formatCost, formatCostCoverage, reportedCost } from '../lib/cost'
import { useAuthStore } from '../stores/auth'
import { useDashboardStore } from '../stores/dashboard'

export default function Dashboard() {
  const { t } = useTranslation()
  const { traces, metrics, total, guardrailAlerts, activeSchedules, loading, error, load } = useDashboardStore()
  const key = useAuthStore((state) => state.apiKey)
  useEffect(() => { if (key) load() }, [key, load])
  const latencies = metrics.flatMap((metric) => [metric.latency_p50, metric.latency_p95]).filter((value): value is number => value !== null)
  const p95 = latencies.length ? Math.max(...latencies) : null
  const errors = metrics.reduce((totalErrors, metric) => totalErrors + metric.errors, 0)
  const tokens = metrics.reduce((totalTokens, metric) => totalTokens + (metric.total_tokens || 0), 0)
  const cost = combineReportedCosts(metrics.map((metric) => reportedCost(metric.total_cost, metric.total_cost_currency ?? metric.cost_currency, metric.cost_coverage)))
  const peakBucket = metrics.reduce((peak, metric) => metric.count > peak.count ? metric : peak, metrics[0])

  return <main className="operations-console">
    <header className="operations-hero dashboard-hero">
      <div className="operations-hero-grid" />
      <div className="operations-hero-copy">
        <p className="operations-eyebrow"><span className="operations-pulse" />{t('dashboard.eyebrow')}</p>
        <h1>{t('dashboard.title')}</h1>
        <p className="dashboard-hero-subtitle">{t('dashboard.subtitle')}</p>
      </div>
      <div className="operations-hero-action">
        <span>{loading ? t('dashboard.synchronizing') : t('dashboard.systemsNominal')}</span>
      </div>
      <div className="operations-kpis" aria-label="Operational KPIs">
        <Kpi label={t('dashboard.throughput')} value={formatNumber(total)} note={t('dashboard.totalObservedRuns')} />
        <Kpi label={t('dashboard.p95Latency')} value={formatDuration(p95) || '—'} note={t('dashboard.tailExecutionTime')} />
        <Kpi label={t('dashboard.errorSignals')} value={formatNumber(errors)} note={t('dashboard.recordedFailedRuns')} tone={errors > 0 ? 'danger' : undefined} />
        <Kpi label={t('dashboard.providerReportedCost')} value={formatCost(cost) || '—'} note={cost ? t('dashboard.costCoverage', { coverage: formatCostCoverage(cost.coverage) }) : t('dashboard.costCoverageUnknown')} />
        <Kpi label={t('dashboard.guardrailAlerts')} value={formatNumber(guardrailAlerts)} note={t('dashboard.guardrailAlertsNote')} tone={guardrailAlerts > 0 ? 'warning' : undefined} />
        <Kpi label={t('dashboard.activchedules')} value={formatNumber(activeSchedules)} note={t('dashboard.activchedulesNote')} tone={activeSchedules > 0 ? undefined : 'muted'} />
      </div>
    </header>
    {error && <p role="alert" className="operations-feedback is-error">{error}</p>}
    <section className="operations-section">
      <div className="operations-section-heading">
        <div><p>01 / EXECUTION ANALYTICS</p><h2>{t('dashboard.executionThroughput')}</h2></div>
        <span className="operations-count">{metrics.length} {t('dashboard.observedBuckets')}</span>
      </div>
      <div className="throughput-summary" aria-label={t('dashboard.executionThroughput')}>
        <div><span>{t('dashboard.totalExecutions')}</span><strong>{formatNumber(total)}</strong></div>
        <div><span>{t('dashboard.peakBucket')}</span><strong>{peakBucket ? formatNumber(peakBucket.count) : '—'}</strong><small>{peakBucket ? formatTime(peakBucket.bucket) : t('meta.notAvailable')}</small></div>
        <div><span>{t('dashboard.tokenVolume')}</span><strong>{tokens ? formatNumber(tokens) : '—'}</strong><small>{t('dashboard.reportedModelUsage')}</small></div>
      </div>
      <div className="dashboard-charts">
        <div className="dashboard-chart">
          <p className="dashboard-chart-label">{t('dashboard.runsByTimeBucket')}</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={metrics}>
              <CartesianGrid stroke="#294038" vertical={false} />
              <XAxis dataKey="bucket" tickFormatter={formatTime} stroke="#789087" fontSize={10} />
              <YAxis stroke="#789087" fontSize={10} />
              <Tooltip labelFormatter={(value) => formatTime(String(value))} formatter={(value: number) => [formatNumber(value), t('dashboard.executions')]} contentStyle={{ background: '#10201c', border: '1px solid #365047', borderRadius: '8px', color: '#eff9f4' }} />
              <Bar dataKey="count" fill="#ff6b35" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="dashboard-chart">
          <p className="dashboard-chart-label">{t('dashboard.latencyHint')}</p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={metrics}>
              <CartesianGrid stroke="#294038" vertical={false} />
              <XAxis dataKey="bucket" tickFormatter={formatTime} stroke="#789087" fontSize={10} />
              <YAxis stroke="#789087" fontSize={10} />
              <Tooltip labelFormatter={(value) => formatTime(String(value))} formatter={(value: number, name) => [formatDuration(value) || '—', name === 'latency_p50' ? t('dashboard.p50Latency') : t('dashboard.p95Latency')]} contentStyle={{ background: '#10201c', border: '1px solid #365047', borderRadius: '8px', color: '#eff9f4' }} />
              <Line type="monotone" dataKey="latency_p50" stroke="#c7f36b" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="latency_p95" stroke="#ff6b35" strokeWidth={2} dot={false} />
              <Legend formatter={(value) => value === 'latency_p50' ? t('dashboard.p50Latency') : t('dashboard.p95Latency')} wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
    <section className="operations-section">
      <div className="operations-section-heading">
        <div><p>02 / EXECUTION REGISTER</p><h2>{t('dashboard.recentExecutions')}</h2></div>
        <span className="operations-count">{traces.length} {t('dashboard.latestObservedRuns')}</span>
      </div>
      <div className="operations-ledger">
        <div className="operations-ledger-head trace-ledger-head">
          <span>{t('dashboard.execution')}</span>
          <span>{t('dashboard.session')}</span>
          <span>{t('dashboard.environment')}</span>
          <span>{t('meta.status')}</span>
          <span>{t('dashboard.started')}</span>
          <span>{t('dashboard.latency')}</span>
          <span>{t('dashboard.cost')}</span>
        </div>
        {traces.length === 0
          ? <div className="operations-state">{t('dashboard.noExecutions')}</div>
          : traces.map((trace) => {
            const hasIssue = trace.observations.some((observation) => Boolean(observation.status_message))
            const traceCost = reportedCost(trace.cost, trace.cost_currency, trace.cost_coverage)
            return <Link key={trace.id} to={`/traces/${trace.id}`} className="operations-ledger-row trace-ledger-row">
            <div data-label={t('dashboard.execution')} className="operations-tool"><strong>{trace.name || t('dashboard.unnamedRuntime')}</strong><code>{trace.id}</code></div>
            <div data-label={t('dashboard.session')}><code>{trace.session_id?.slice(0, 16) || '—'}</code></div>
            <div data-label={t('dashboard.environment')}>{trace.environment || '—'}</div>
            <div data-label={t('meta.status')}><span className={`operations-status is-${hasIssue ? 'rejected' : 'approved'}`}>{t(hasIssue ? 'dashboard.issueRecorded' : 'dashboard.recorded')}</span></div>
            <time data-label={t('dashboard.started')} className="operations-time">{formatTime(trace.start_time || trace.timestamp)}</time>
            <div data-label={t('dashboard.latency')}>{formatDuration(trace.latency_ms) || '—'}</div>
            <div data-label={t('dashboard.cost')} className="dashboard-cost">{formatCost(traceCost) || '—'}</div>
          </Link>
          })}
      </div>
    </section>
  </main>
}

function Kpi({ label, value, note, tone }: { label: string; value: string | number; note: string; tone?: 'warning' | 'danger' | 'muted' }) {
  return <article className={tone ? `is-${tone}` : ''}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>
}
