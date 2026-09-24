import {
  Activity,
  CalendarClock,
  ChartNoAxesCombined,
  ChevronRight,
  ClipboardCheck,
  GitBranch,
  LayoutDashboard,
  LockKeyhole,
  MessageSquare,
  Network,
  PanelsTopLeft,
  Radio,
  Settings,
  ShieldCheck,
  Shield,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../stores/auth'
import LanguageSwitcher from './LanguageSwitcher'
import { fetchMeshCatalog } from '../lib/api'
import type { MeshCatalog } from '../lib/types'
import { useScopeStore } from '../stores/context'
import ContextCombobox from './ContextCombobox'

export default function Layout() {
  const { clear } = useAuthStore()
  const { t } = useTranslation()

  const NAV = [
    {
      label: t('nav.operate'),
      items: [
        { to: '/', label: t('nav.dashboard'), Icon: LayoutDashboard, end: true },
        { to: '/chat', label: t('nav.chat'), Icon: MessageSquare },
        { to: '/channels', label: t('nav.channels'), Icon: Radio },
        { to: '/schedules', label: t('nav.schedules'), Icon: CalendarClock },
        { to: '/traces', label: t('nav.traces'), Icon: GitBranch },
        { to: '/sessions', label: t('nav.sessions'), Icon: PanelsTopLeft },
        { to: '/predictions', label: t('nav.predictions'), Icon: ChartNoAxesCombined },
      ],
    },
    { label: t('nav.quality'), items: [{ to: '/scores', label: t('nav.scores'), Icon: Activity }, { to: '/guardrails', label: t('nav.guardrails'), Icon: Shield }, { to: '/approvals', label: t('nav.approvals'), Icon: ClipboardCheck }] },
    { label: t('nav.reliability'), items: [{ to: '/resilience', label: t('nav.resilience'), Icon: ShieldCheck }] },
    { label: t('nav.registry'), items: [{ to: '/mesh', label: t('nav.mesh'), Icon: Network }] },
    { label: t('nav.administration'), items: [{ to: '/privacy', label: t('nav.privacy'), Icon: LockKeyhole }, { to: '/settings', label: t('nav.settings'), Icon: Settings }] },
  ]
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
      <a className="skip-link" href="#content">{t('layout.skipToContent')}</a>
      <aside className="app-sidebar">
        <Link to="/" className="app-brand" aria-label={t('layout.productName')}>
          <span>W</span><strong>Wolfpack</strong><small>{t('layout.control')}</small>
        </Link>
        <nav aria-label={t('layout.mainNavigation')}>
          {NAV.map((group) => (
            <div className="nav-group" key={group.label}>
              <p>{group.label}</p>
              {group.items.map(({ to, label, Icon, end }) => (
                <NavLink key={to} to={to} end={end} aria-label={label} className={({ isActive }) => isActive ? 'is-active' : undefined}>
                  <Icon className="nav-icon" aria-hidden="true" size={18} />
                  <span className="nav-label">{label}</span>
                  <ChevronRight className="nav-label ml-auto" aria-hidden="true" size={14} />
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer"><span className="status-dot" /> {t('layout.systemsNominal')}</div>
      </aside>
      <div className="app-main">
        <header className="context-bar">
          <div className="context-label">{t('layout.context')}</div>
          <ContextCombobox label={t('layout.environment')} value={environmentId} options={catalog?.environments.map((environment) => ({ value: environment.id, label: `${environment.name} / ${environment.slug}` })) ?? []} allLabel={t('layout.allEnvironments')} emptyLabel={t('layout.noMatchingOptions')} searchable onChange={setEnvironment} />
          <ContextCombobox label={t('layout.agent')} value={registrationId} options={registrations.map((registration) => ({ value: registration.id, label: `${registration.definition_name} v${registration.definition_version}`, healthStatus: registration.health_status, healthLabel: t(`mesh.health.${registration.health_status}`), detail: `${registration.definition_kind === 'team' ? t('mesh.team') : t('mesh.replicaCount', { count: registration.online_replicas })}` }))} allLabel={t('layout.allAgents')} emptyLabel={t('layout.noMatchingOptions')} disabled={!environmentId} searchable onChange={setRegistration} />
          <ContextCombobox label={t('layout.range')} value={range} options={[{ value: '1h', label: t('layout.lastHour') }, { value: '24h', label: t('layout.last24Hours') }, { value: '7d', label: t('layout.last7Days') }, { value: '30d', label: t('layout.last30Days') }]} onChange={setRange} />
          <div className="context-actions"><LanguageSwitcher /><button type="button" onClick={clear}>{t('meta.logout')}</button></div>
        </header>
        <main id="content" className="app-content"><Outlet key={`${environmentId}:${registrationId}:${range}`} /></main>
      </div>
    </div>
  )
}
