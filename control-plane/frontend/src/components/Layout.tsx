import { Link, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../stores/auth'
import LanguageSwitcher from './LanguageSwitcher'
import { fetchMeshCatalog } from '../lib/api'
import type { MeshCatalog } from '../lib/types'
import { useScopeStore } from '../stores/context'
import ContextCombobox from './ContextCombobox'

export default function Layout() {
  const location = useLocation()
  const { clear } = useAuthStore()
  const { t } = useTranslation()

  const NAV = [{ label: t('nav.operate'), items: [{ to: '/', label: t('nav.dashboard') }, { to: '/chat', label: t('nav.chat') }, { to: '/channels', label: t('nav.channels') }, { to: '/schedules', label: t('nav.schedules') }, { to: '/traces', label: t('nav.traces') }, { to: '/sessions', label: t('nav.sessions') }] }, { label: t('nav.quality'), items: [{ to: '/scores', label: t('nav.scores') }, { to: '/guardrails', label: t('nav.guardrails') }, { to: '/approvals', label: t('nav.approvals') }] }, { label: t('nav.reliability'), items: [{ to: '/resilience', label: t('nav.resilience') }] }, { label: t('nav.registry'), items: [{ to: '/mesh', label: t('nav.mesh') }] }, { label: t('nav.administration'), items: [{ to: '/privacy', label: t('nav.privacy') }, { to: '/settings', label: t('nav.settings') }] }]
  const [catalog, setCatalog] = useState<MeshCatalog | null>(null)
  const environmentId = useScopeStore((state) => state.environmentId)
  const registrationId = useScopeStore((state) => state.registrationId)
  const range = useScopeStore((state) => state.range)
  const setEnvironment = useScopeStore((state) => state.setEnvironment)
  const setRegistration = useScopeStore((state) => state.setRegistration)
  const setRange = useScopeStore((state) => state.setRange)
  useEffect(() => { void fetchMeshCatalog().then(setCatalog).catch(() => setCatalog(null)) }, [])
  const registrations = catalog?.environments.find((environment) => environment.id === environmentId)?.registrations.filter((registration) => (registration.definition_kind === 'agent' || registration.definition_kind === 'team') && registration.enabled) ?? []

  return (
    <div className="app-shell">
      <aside className="app-sidebar"><Link to="/" className="app-brand"><span>W</span><strong>WOLFPACK</strong><small>CONTROL</small></Link><nav>{NAV.map((group) => <div className="nav-group" key={group.label}><p>{group.label}</p>{group.items.map((item) => <Link key={item.to} to={item.to} className={location.pathname === item.to || (item.to !== '/' && location.pathname.startsWith(`${item.to}/`)) ? 'is-active' : ''}>{item.label}</Link>)}</div>)}</nav><div className="sidebar-footer"><span className="status-dot" /> {t('layout.systemsNominal')}</div></aside>
      <div className="app-main"><header className="context-bar"><div className="context-label">{t('layout.context')}</div><ContextCombobox label={t('layout.environment')} value={environmentId} options={catalog?.environments.map((environment) => ({ value: environment.id, label: `${environment.name} / ${environment.slug}` })) ?? []} allLabel={t('layout.allEnvironments')} emptyLabel={t('layout.noMatchingOptions')} searchable onChange={setEnvironment} /><ContextCombobox label={t('layout.agent')} value={registrationId} options={registrations.map((registration) => ({ value: registration.id, label: `${registration.definition_name} v${registration.definition_version}`, healthStatus: registration.health_status, healthLabel: t(`mesh.health.${registration.health_status}`), detail: `${registration.definition_kind === 'team' ? t('mesh.team') : t('mesh.agent')} · ${t('mesh.replicaCount', { count: registration.online_replicas })}` }))} allLabel={t('layout.allAgents')} emptyLabel={t('layout.noMatchingOptions')} disabled={!environmentId} searchable onChange={setRegistration} /><ContextCombobox label={t('layout.range')} value={range} options={[{ value: '1h', label: t('layout.lastHour') }, { value: '24h', label: t('layout.last24Hours') }, { value: '7d', label: t('layout.last7Days') }, { value: '30d', label: t('layout.last30Days') }]} onChange={setRange} /><div className="context-actions"><LanguageSwitcher /><button onClick={clear}>{t('meta.logout')}</button></div></header><main className="app-content"><Outlet key={`${environmentId}:${registrationId}:${range}`} /></main></div>
    </div>
  )
}
