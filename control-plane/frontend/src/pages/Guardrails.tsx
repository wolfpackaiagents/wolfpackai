import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { fetchAlerts } from '../lib/api'
import type { AlertSeverity, ResilienceAlert } from '../lib/types'
import { formatDateTime } from '../i18n/format'

export default function Guardrails() {
  const { t } = useTranslation()
  const [alerts, setAlerts] = useState<ResilienceAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    void fetchAlerts({ source: 'guardrail' })
      .then((items) => active && setAlerts(items))
      .catch(() => active && setError(t('guardrails.requestFailed')))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [t])

  const critical = alerts.filter((alert) => alert.severity === 'critical').length
  const traced = alerts.filter((alert) => alert.trace_id).length

  return <main className="operations-console">
    <header className="operations-hero">
      <div className="operations-hero-grid" />
      <div className="operations-hero-copy">
        <p className="operations-eyebrow"><span className="operations-pulse" /> {t('guardrails.eyebrow')}</p>
        <h1>{t('guardrails.title')}<span> {t('guardrails.titleSuffix')}</span></h1>
        <p>{t('guardrails.subtitle')}</p>
      </div>
      <div className="operations-kpis" aria-label="Guardrail alert summary">
        <Kpi label="Recorded alerts" value={alerts.length} note="policy events in view" />
        <Kpi label="Critical signals" value={critical} note="requires investigation" tone={critical ? 'danger' : undefined} />
        <Kpi label="Trace coverage" value={traced} note="events linked to evidence" />
      </div>
    </header>

    {error && <Feedback tone="error" message={error} />}
    <section className="operations-section">
      <div className="operations-section-heading">
        <div><p>01 / POLICY EVENTS</p><h2>Safety event ledger</h2></div>
        <span className="operations-count">{loading ? 'SYNCING' : `${alerts.length} EVENTS`}</span>
      </div>
      <div className="operations-ledger">
        <div className="operations-ledger-head guardrail-row"><span>{t('guardrails.severity')}</span><span>{t('guardrails.event')}</span><span>{t('guardrails.alert')}</span><span>{t('guardrails.trace')}</span><span>{t('guardrails.when')}</span></div>
        {loading ? <State label={t('guardrails.loading')} /> : alerts.length === 0 ? <State label={t('guardrails.empty')} /> : alerts.map((alert) => <article className="operations-ledger-row guardrail-row" key={alert.id}>
          <div data-label={t('guardrails.severity')}><Severity severity={alert.severity} /></div>
          <div data-label={t('guardrails.event')} className="operations-event">{alert.event_type || t('guardrails.policyEvent')}</div>
          <div data-label={t('guardrails.alert')} className="operations-message">{alert.message}</div>
          <div data-label={t('guardrails.trace')}>{alert.trace_id ? <Link to={`/traces/${alert.trace_id}`} className="operations-link">{alert.trace_id}</Link> : <span className="operations-muted">{t('guardrails.notLinked')}</span>}</div>
          <time data-label={t('guardrails.when')} className="operations-time">{formatDateTime(alert.created_at)}</time>
        </article>)}
      </div>
    </section>
  </main>
}

function Kpi({ label, value, note, tone }: { label: string; value: number; note: string; tone?: 'danger' }) { return <div className={tone ? `is-${tone}` : ''}><span>{label}</span><strong>{String(value).padStart(2, '0')}</strong><small>{note}</small></div> }
function Feedback({ message, tone }: { message: string; tone: 'error' }) { return <p role="alert" className={`operations-feedback is-${tone}`}>{message}</p> }
function State({ label }: { label: string }) { return <div className="operations-state">{label}</div> }
function Severity({ severity }: { severity: AlertSeverity }) { return <span className={`operations-severity is-${severity}`}>{severity}</span> }
