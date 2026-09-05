import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { formatDateTime, formatDuration, formatNumber } from '../i18n/format'
import { formatCost, formatCostCoverage, reportedCost } from '../lib/cost'
import { fetchTraces } from '../lib/api'
import type { TraceSummary } from '../lib/types'
import { useScopeStore } from '../stores/context'

const PAGE_SIZE = 20

export default function Traces() {
  const { t } = useTranslation()
  const [data, setData] = useState<{ traces: TraceSummary[]; total: number }>({ traces: [], total: 0 })
  const [params, setParams] = useSearchParams()
  const page = Number(params.get('page') || 0)
  const name = params.get('name') || ''
  const session = params.get('session_id') || ''
  const [loading, setLoading] = useState(true)
  const environmentId = useScopeStore((state) => state.environmentId)
  const registrationId = useScopeStore((state) => state.registrationId)
  useEffect(() => { let alive = true; setLoading(true); void fetchTraces({ page, per_page: PAGE_SIZE, name: name || undefined, session_id: session || undefined, environment_id: environmentId || undefined, registration_id: registrationId || undefined }).then((value) => alive && setData(value)).finally(() => alive && setLoading(false)); return () => { alive = false } }, [page, name, session, environmentId, registrationId])
  const update = (next: Record<string, string>) => { const updated = new URLSearchParams(params); Object.entries(next).forEach(([key, value]) => value ? updated.set(key, value) : updated.delete(key)); if (!('page' in next)) updated.delete('page'); setParams(updated) }
  return <section className="ops-console"><header className="ops-header"><div><p>{t('traces.eyebrow')}</p><h1>{t('traces.title')}</h1><span>{t('traces.subtitle')}</span></div><strong>{formatNumber(data.total)} {t('traces.runs')}</strong></header><div className="ops-filterbar"><input value={name} onChange={(event) => update({ name: event.target.value })} placeholder={t('traces.filterByAgent')} /><input value={session} onChange={(event) => update({ session_id: event.target.value })} placeholder={t('traces.filterBySession')} /><span>{environmentId ? t('traces.environmentScoped') : t('traces.allEnvironments')}</span><span>{registrationId ? t('traces.agentScoped') : t('traces.allAgents')}</span></div><section className="ops-table">{loading ? <div className="ops-empty">{t('traces.loading')}</div> : data.traces.length ? <table><thead><tr><th>{t('traces.execution')}</th><th>{t('traces.session')}</th><th>{t('traces.environment')}</th><th>{t('traces.started')}</th><th>{t('traces.latency')}</th><th>{t('traces.cost')}</th><th>{t('traces.costCoverage')}</th><th /></tr></thead><tbody>{data.traces.map((trace) => { const cost = reportedCost(trace.cost, trace.cost_currency, trace.cost_coverage); return <tr key={trace.id}><td><Link to={`/traces/${trace.id}`}><b>{trace.name || t('traces.unnamedRuntime')}</b><small>{trace.id}</small></Link></td><td>{trace.session_id || t('meta.notAvailable')}</td><td>{trace.environment || t('meta.notAvailable')}</td><td>{formatDateTime(trace.start_time || trace.timestamp)}</td><td>{formatDuration(trace.latency_ms)}</td><td>{formatCost(cost) ?? t('meta.notAvailable')}</td><td>{formatCostCoverage(cost?.coverage ?? null) ?? t('traces.costCoverageUnknown')}</td><td><Link className="ops-open" to={`/traces/${trace.id}`}>{t('traces.open')}</Link></td></tr>})}</tbody></table> : <div className="ops-empty">{t('traces.noExecutions')}</div>}</section></section>
}
