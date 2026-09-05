import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { fetchApprovals, resolveApproval } from '../lib/api'
import type { Approval, ApprovalStatus } from '../lib/types'
import ContextCombobox from '../components/ContextCombobox'
import { formatDateTime, formatNumber } from '../i18n/format'

const statuses: ApprovalStatus[] = ['pending', 'approved', 'rejected', 'resolved']

export default function Approvals() {
  const { t } = useTranslation()
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [status, setStatus] = useState<ApprovalStatus>('pending')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    void fetchApprovals(status).then((items) => active && setApprovals(items)).catch(() => active && setError(t('approvals.requestFailed'))).finally(() => active && setLoading(false))
    return () => { active = false }
  }, [status, t])

  async function resolve(approval: Approval, action: 'approve' | 'reject') {
    const note = action === 'reject' ? window.prompt(t('approvals.rejectNote')) || undefined : undefined
    setWorking(approval.approval_id); setError('')
    try {
      const resolved = await resolveApproval(approval.approval_id, action, note)
      setApprovals((items) => items.map((item) => item.id === resolved.id ? resolved : item).filter((item) => status !== 'pending' || item.status === 'pending'))
    } catch { setError(t('approvals.resolveFailed')) } finally { setWorking(null) }
  }

  return <main className="operations-console">
    <header className="operations-hero approvals-hero"><div className="operations-hero-grid" /><div className="operations-hero-copy"><p className="operations-eyebrow"><span className="operations-pulse" /> {t('approvals.eyebrow')}</p><h1>{t('approvals.title')}<span>{' '}{t('approvals.titleSuffix')}</span></h1><p>{t('approvals.subtitle')}</p></div><div className="operations-kpis" aria-label={t('approvals.queueSummary')}><Kpi label={t('approvals.requestsInView')} value={approvals.length} note={t('approvals.queueForStatus', { status: t(`approvals.status.${status}`) })} /><Kpi label={t('approvals.humanGates')} value={approvals.filter((approval) => approval.confirmation !== null).length} note={t('approvals.confirmationState')} /><Kpi label={t('approvals.traceEvidence')} value={approvals.filter((approval) => approval.trace_id).length} note={t('approvals.executionContext')} /></div></header>
    {error && <p role="alert" className="operations-feedback is-error">{error}</p>}
    <section className="operations-section"><div className="operations-section-heading"><div><p>{t('approvals.sectionIndex')}</p><h2>{t('approvals.sectionTitle')}</h2></div><div className="operations-filter"><span>{t('approvals.queueStatus')}</span><ContextCombobox label={t('approvals.queueStatus')} value={status} options={statuses.map((value) => ({ value, label: t(`approvals.status.${value}`) }))} onChange={(value) => setStatus(value as ApprovalStatus)} /></div></div><div className="operations-ledger"><div className="operations-ledger-head approval-row"><span>{t('approvals.tool')}</span><span>{t('approvals.requirement')}</span><span>{t('approvals.trace')}</span><span>{t('approvals.created')}</span><span>{t('approvals.actions')}</span></div>{loading ? <State label={t('approvals.loading')} /> : approvals.length === 0 ? <State label={t('approvals.empty')} /> : approvals.map((approval) => <article className="operations-ledger-row approval-row" key={approval.id}><div data-label={t('approvals.tool')}><strong className="operations-tool">{approval.tool_name}</strong>{approval.tool_arguments && <code className="operations-code">{JSON.stringify(approval.tool_arguments)}</code>}</div><div data-label={t('approvals.requirement')} className="operations-message">{approval.requirement}</div><ApprovalContext approval={approval} /><time data-label={t('approvals.created')} className="operations-time">{formatDateTime(approval.created_at)}</time><div data-label={t('approvals.actions')} className="operations-actions">{approval.status === 'pending' ? <><button disabled={working === approval.approval_id} onClick={() => void resolve(approval, 'approve')} className="operations-approve">{working === approval.approval_id ? t('approvals.working') : t('approvals.approve')}</button><button disabled={working === approval.approval_id} onClick={() => void resolve(approval, 'reject')} className="operations-reject">{t('approvals.reject')}</button></> : <span className={`operations-status is-${approval.status}`}>{t(`approvals.status.${approval.status}`)}</span>}</div></article>)}</div></section>
  </main>
}

function ApprovalContext({ approval }: { approval: Approval }) {
  const { t } = useTranslation()
  const context = approval.trace_context
  const trace = context?.trace ? { ...context.trace, name: context.trace.name || context.trace.id } : (approval.trace_id ? { id: approval.trace_id, name: approval.trace_id } : null)
  return <div data-label={t('approvals.trace')} className="approval-context">{trace ? <Link to={`/traces/${trace.id}`} className="approval-context-trace" aria-label={t('approvals.traceContext.viewTrace', trace)}><ContextIcon name="trace" /><span><strong>{trace.name}</strong><code>{trace.id}</code></span></Link> : <span className="operations-muted">{t('approvals.notLinked')}</span>}{(context?.session_id || context?.environment || context?.definition || context?.registration) && <div className="approval-context-details">{context?.session_id && <ContextItem icon="session" label={t('approvals.traceContext.session')}><Link to={`/sessions/${context.session_id}`} className="operations-link">{context.session_id}</Link></ContextItem>}{context?.environment && <ContextItem icon="environment" label={t('approvals.traceContext.environment')}><Link to="/mesh" className="approval-context-badge">{context.environment.name}<span>{context.environment.slug}</span></Link></ContextItem>}{context?.definition && <ContextItem icon="agent" label={t('approvals.traceContext.agent')}><Link to="/mesh" className="operations-link">{context.definition.name}</Link><span className="approval-context-badge">{t('approvals.traceContext.version')} {context.definition.version}</span></ContextItem>}{context?.registration && <ContextItem icon="registration" label={t('approvals.traceContext.registration')}><Link to="/mesh" className="operations-link">{context.registration.id}</Link></ContextItem>}</div>}</div>
}

function ContextItem({ icon, label, children }: { icon: ContextIconName; label: string; children: ReactNode }) { return <div className="approval-context-item"><ContextIcon name={icon} /><span className="approval-context-label">{label}</span><span className="approval-context-value">{children}</span></div> }
type ContextIconName = 'trace' | 'session' | 'environment' | 'agent' | 'registration'
function ContextIcon({ name }: { name: ContextIconName }) { const paths: Record<ContextIconName, ReactNode> = { trace: <><path d="M4 5h16v14H4z" /><path d="M8 9h8M8 13h5" /></>, session: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 9h8M8 13h8M8 17h4" /></>, environment: <><circle cx="12" cy="12" r="8" /><path d="M4 12h16M12 4c2 2.2 3 5 3 8s-1 5.8-3 8c-2-2.2-3-5-3-8s1-5.8 3-8Z" /></>, agent: <><rect x="5" y="6" width="14" height="12" rx="2" /><path d="M9 3v3M15 3v3M9 12h.01M15 12h.01M9 16h6" /></>, registration: <><path d="m12 3 7 4v10l-7 4-7-4V7z" /><path d="m8.5 10 3.5 2 3.5-2M12 12v5" /></> }; return <svg className="approval-context-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{paths[name]}</svg> }
function Kpi({ label, value, note }: { label: string; value: number; note: string }) { return <div><span>{label}</span><strong>{formatNumber(value)}</strong><small>{note}</small></div> }
function State({ label }: { label: string }) { return <div className="operations-state">{label}</div> }
