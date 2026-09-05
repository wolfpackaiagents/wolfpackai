import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../stores/auth'
import { api, fetchGovernanceSettings, isFeatureUnavailable, updateGovernanceSettings } from '../lib/api'
import type { GovernanceSettings } from '../lib/types'

const roles = ['read_only', 'editor', 'admin'] as const
const permissions = ['read', 'write', 'manage'] as const

export default function Settings() {
  const { apiKey, setApiKey, clear } = useAuthStore()
  const { t } = useTranslation()
  const [key, setKey] = useState(apiKey === '' ? 'pk-wp-dev:dev-secret' : apiKey)
  const [org, setOrg] = useState('')
  const [project, setProject] = useState('')
  const [result, setResult] = useState('')
  const [health, setHealth] = useState('')
  const [governance, setGovernance] = useState<GovernanceSettings | null>(null)
  const [governanceAvailable, setGovernanceAvailable] = useState<boolean | null>(null)
  const [governanceError, setGovernanceError] = useState('')

  useEffect(() => {
    void fetchGovernanceSettings().then((settings) => {
      setGovernance(settings)
      setGovernanceAvailable(true)
    }).catch((error: unknown) => {
      setGovernanceAvailable(false)
      if (!isFeatureUnavailable(error)) setGovernanceError(t('settings.governanceFailed'))
    })
  }, [t])

  async function saveGovernance() {
    if (!governance || !governanceAvailable) return
    try {
      setGovernance(await updateGovernanceSettings(governance))
      setGovernanceError('')
    } catch (error) {
      setGovernanceError(isFeatureUnavailable(error) ? t('settings.governanceEndpointUnavailable') : t('settings.governanceFailed'))
    }
  }

  function togglePermission(role: typeof roles[number], permission: typeof permissions[number]) {
    if (!governance) return
    const rolePermissions = governance.roles[role]
    const nextPermissions = rolePermissions.includes(permission)
      ? rolePermissions.filter((value) => value !== permission)
      : [...rolePermissions, permission]
    setGovernance({ ...governance, roles: { ...governance.roles, [role]: nextPermissions } })
  }

  async function checkHealth() {
    const ok = await api.get('/health').then(() => true).catch(() => false)
    setHealth(ok ? t('settings.connected') : t('settings.disconnected'))
  }

  async function createOrg() {
    try {
      const { data } = await api.post('/admin/organizations', { name: org || t('settings.defaultOrganizationName') })
      setResult(JSON.stringify(data))
      setGovernanceError('')
    } catch {
      setGovernanceError(t('settings.adminRequestFailed'))
    }
  }

  async function createProject() {
    try {
      const [organizationId, name] = project.split('|')
      const { data } = await api.post('/admin/projects', { organization_id: organizationId, name: name || t('settings.defaultProjectName') })
      setResult(JSON.stringify(data))
      setGovernanceError('')
    } catch {
      setGovernanceError(t('settings.adminRequestFailed'))
    }
  }

  const endpointStatus = governanceAvailable === true ? t('settings.endpointConnected') : governanceAvailable === null ? t('settings.endpointChecking') : t('settings.endpointUnavailable')

  return <div className="policy-console settings-console">
    <header className="policy-hero settings-hero">
      <div className="policy-hero-grid" />
      <div className="policy-eyebrow"><span className="policy-pulse" /> {t('settings.eyebrow')}</div>
      <div className="policy-hero-copy"><h1>{t('settings.heroTitle')}<br /><span>{t('settings.heroAccent')}</span></h1><p>{t('settings.heroSubtitle')}</p></div>
      <div className="policy-hero-status"><span>{t('settings.endpoint')}</span><strong className={governanceAvailable === true ? 'is-live' : 'is-muted'}>{endpointStatus}</strong></div>
    </header>

    <section className="policy-section-heading"><div><span>{t('settings.accessIndex')}</span><h2>{t('settings.accessTitle')}</h2></div><p>{t('settings.accessHint')}</p></section>
    <section className="policy-panel settings-access"><label>{t('settings.apiKey')}<div className="settings-key-row"><input value={key} onChange={(event) => setKey(event.target.value)} placeholder="pk-...:secret" /><button onClick={() => setApiKey(key.trim())} className="policy-primary">{t('meta.save')} <span>+</span></button><button onClick={clear} className="policy-secondary">{t('meta.logout')}</button></div></label><div className="policy-panel-footer"><small>{t('settings.apiKeyHint')}</small><button onClick={checkHealth} className="policy-text-button">{health || t('settings.checkBackend')}</button></div></section>

    <section className="policy-section-heading"><div><span>{t('settings.governanceIndex')}</span><h2>{t('settings.governanceTitle')}</h2></div><p>{t('settings.governanceHint')}</p></section>
    <form className="policy-panel" onSubmit={(event) => { event.preventDefault(); void saveGovernance() }}>
      {governanceAvailable === false ? <CapabilityUnavailable label={t('settings.governanceUnavailable')} /> : governance && <div className="settings-governance"><label>{t('settings.retentionDays')}<input type="number" min="1" value={governance.retention_days} onChange={(event) => setGovernance({ ...governance, retention_days: Number(event.target.value) })} /></label><fieldset className="settings-role-matrix"><legend>{t('settings.rolePermissions')}</legend><p>{t('settings.rolePermissionsHint')}</p><div className="settings-permission-header"><span>{t('settings.role')}</span>{permissions.map((permission) => <span key={permission}>{t(`settings.permissions.${permission}`)}</span>)}</div>{roles.map((role) => <div className="settings-permission-row" key={role}><strong>{t(`settings.roles.${role}`)}</strong>{permissions.map((permission) => <label key={permission}><input type="checkbox" checked={governance.roles[role].includes(permission)} onChange={() => togglePermission(role, permission)} /><span className="sr-only">{t('settings.permissionForRole', { permission: t(`settings.permissions.${permission}`), role: t(`settings.roles.${role}`) })}</span></label>)}</div>)}</fieldset><p className="settings-auth-note">{t('settings.rolePermissionsNote')}</p></div>}
      <div className="policy-panel-footer"><small>{t('settings.governanceFooter')}</small><button type="submit" disabled={!governanceAvailable || !governance} className="policy-primary">{t('meta.save')} <span>+</span></button></div>
    </form>
    {governanceError && <p role="alert" className="policy-feedback is-error">{governanceError}</p>}

    <section className="policy-section-heading"><div><span>{t('settings.adminIndex')}</span><h2>{t('settings.adminTitle')}</h2></div><p>{t('settings.adminHint')}</p></section>
    <section className="policy-panel settings-admin"><label>{t('settings.orgNamePlaceholder')}<input value={org} onChange={(event) => setOrg(event.target.value)} placeholder={t('settings.orgNamePlaceholder')} /></label><button onClick={() => void createOrg()} className="policy-secondary">{t('settings.createOrgBtn')}</button><label>{t('settings.projectPlaceholder')}<input value={project} onChange={(event) => setProject(event.target.value)} placeholder={t('settings.projectPlaceholder')} /></label><button onClick={() => void createProject()} className="policy-secondary">{t('settings.createProjectBtn')}</button>{result && <pre>{result}</pre>}</section>
  </div>
}

function CapabilityUnavailable({ label }: { label: string }) {
  const { t } = useTranslation()
  return <div className="policy-unavailable"><span>{t('settings.capabilityUnavailable')}</span><p>{label}</p><small>{t('settings.capabilityUnavailableHint')}</small></div>
}
