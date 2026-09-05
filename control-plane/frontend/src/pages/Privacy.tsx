import { type FormEvent, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { deleteDataSubject, exportDataSubject, fetchPrivacyAuditLog, fetchPrivacySettings, isFeatureUnavailable, updatePrivacySettings } from '../lib/api'
import type { PrivacyAuditRecord, PrivacySettings } from '../lib/types'
import ConfirmationDialog from '../components/ConfirmationDialog'
import { formatDateTime } from '../i18n/format'

const defaultSettings: PrivacySettings = { enabled: false, redact_email: true, redact_phone: true, redact_cpf: true, redact_credit_card: true, custom_patterns: [] }

function patternError(pattern: string): 'empty' | 'invalid' | null {
  if (!pattern.trim()) return 'empty'
  try { new RegExp(pattern); return null } catch { return 'invalid' }
}

export default function Privacy() {
  const { t } = useTranslation()
  const [settings, setSettings] = useState(defaultSettings)
  const [settingsAvailable, setSettingsAvailable] = useState<boolean | null>(null)
  const [saving, setSaving] = useState(false)
  const [userId, setUserId] = useState('')
  const [action, setAction] = useState<'export' | 'delete' | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [auditRecords, setAuditRecords] = useState<PrivacyAuditRecord[]>([])
  const [subjectPendingDeletion, setSubjectPendingDeletion] = useState<string | null>(null)

  function refreshAuditLog() { return fetchPrivacyAuditLog().then(setAuditRecords) }

  useEffect(() => {
    let alive = true
    void fetchPrivacySettings().then((nextSettings) => {
      if (!alive) return
      setSettings(nextSettings)
      setSettingsAvailable(true)
    }).catch((requestError: unknown) => {
      if (!alive) return
      setSettingsAvailable(false)
      if (!isFeatureUnavailable(requestError)) setError(t('privacy.requestFailed'))
    })
    void refreshAuditLog().catch(() => undefined)
    return () => { alive = false }
  }, [t])

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!settingsAvailable) return
    if (settings.custom_patterns.some(patternError)) { setError(t('privacy.patternsFixErrors')); return }
    setError(''); setNotice(''); setSaving(true)
    try { setSettings(await updatePrivacySettings(settings)); setNotice(t('privacy.saved')) } catch (requestError) { setError(isFeatureUnavailable(requestError) ? t('privacy.featureUnavailable') : t('privacy.requestFailed')) } finally { setSaving(false) }
  }

  async function exportSubject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const subject = userId.trim()
    if (!subject) return
    setError(''); setNotice(''); setAction('export')
    try {
      const data = await exportDataSubject(subject)
      const url = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      link.download = `user-${subject}-export.json`
      link.click()
      URL.revokeObjectURL(url)
      setNotice(t('privacy.exportReady'))
      void refreshAuditLog().catch(() => undefined)
    } catch (requestError) { setError(isFeatureUnavailable(requestError) ? t('privacy.featureUnavailable') : t('privacy.requestFailed')) } finally { setAction(null) }
  }

  async function deleteSubject() {
    const subject = userId.trim()
    if (!subject) return
    setError(''); setNotice(''); setAction('delete')
    try { await deleteDataSubject(subject); setUserId(''); setNotice(t('privacy.deleted')); void refreshAuditLog().catch(() => undefined) } catch (requestError) { setError(isFeatureUnavailable(requestError) ? t('privacy.featureUnavailable') : t('privacy.requestFailed')) } finally { setAction(null) }
  }

  const settingsDisabled = settingsAvailable !== true || saving
  const customPatterns = settings.custom_patterns ?? []
  const endpointStatus = settingsAvailable === true ? t('privacy.endpointConnected') : settingsAvailable === null ? t('privacy.endpointChecking') : t('privacy.endpointUnavailable')

  return <div className="policy-console">
    <header className="policy-hero"><div className="policy-hero-grid" /><div className="policy-eyebrow"><span className="policy-pulse" /> {t('privacy.eyebrow')}</div><div className="policy-hero-copy"><h1>{t('privacy.heroTitle')}<br /><span>{t('privacy.heroAccent')}</span></h1><p>{t('privacy.heroSubtitle')}</p></div><div className="policy-hero-status"><span>{t('privacy.endpoint')}</span><strong className={settingsAvailable === true ? 'is-live' : 'is-muted'}>{endpointStatus}</strong></div></header>
    {error && <p role="alert" className="policy-feedback is-error">{error}</p>}
    {notice && <p role="status" className="policy-feedback">{notice}</p>}
    <section className="policy-section-heading"><div><span>{t('privacy.redactionIndex')}</span><h2>{t('privacy.redactionTitle')}</h2></div><p>{t('privacy.redactionHint')}</p></section>
    <form onSubmit={saveSettings} className="policy-panel">
      {settingsAvailable === false ? <CapabilityUnavailable label={t('privacy.configUnavailable')} /> : <div className="policy-toggle-list">
        <SettingToggle label={t('privacy.enableRedaction')} description={t('privacy.enableRedactionHint')} checked={settings.enabled ?? false} disabled={settingsDisabled} onChange={(enabled) => setSettings((current) => ({ ...current, enabled }))} />
        <SettingToggle label={t('privacy.emailAddresses')} description={t('privacy.emailAddressesHint')} checked={settings.redact_email ?? true} disabled={settingsDisabled} onChange={(redact_email) => setSettings((current) => ({ ...current, redact_email }))} />
        <SettingToggle label={t('privacy.phoneNumbers')} description={t('privacy.phoneNumbersHint')} checked={settings.redact_phone ?? true} disabled={settingsDisabled} onChange={(redact_phone) => setSettings((current) => ({ ...current, redact_phone }))} />
        <SettingToggle label={t('privacy.cpf')} description={t('privacy.cpfHint')} checked={settings.redact_cpf ?? true} disabled={settingsDisabled} onChange={(redact_cpf) => setSettings((current) => ({ ...current, redact_cpf }))} />
        <SettingToggle label={t('privacy.creditCards')} description={t('privacy.creditCardsHint')} checked={settings.redact_credit_card ?? true} disabled={settingsDisabled} onChange={(redact_credit_card) => setSettings((current) => ({ ...current, redact_credit_card }))} />
        <fieldset className="policy-patterns" disabled={settingsDisabled} aria-describedby="custom-patterns-help"><div className="policy-patterns-heading"><div><legend>{t('privacy.customPatterns')}</legend><p id="custom-patterns-help">{t('privacy.customPatternsHint')}</p></div><button type="button" className="policy-secondary" onClick={() => setSettings((current) => ({ ...current, custom_patterns: [...(current.custom_patterns ?? []), ''] }))}>{t('privacy.addPattern')}</button></div>{customPatterns.length === 0 ? <p className="policy-patterns-empty">{t('privacy.noPatterns')}</p> : <div className="policy-pattern-list">{customPatterns.map((pattern, index) => { const validationError = patternError(pattern); const inputId = `custom-pattern-${index}`; const errorId = `${inputId}-error`; return <div className="policy-pattern-row" key={inputId}><label htmlFor={inputId}><span>{t('privacy.patternNumber', { count: index + 1 })}</span><input id={inputId} value={pattern} aria-invalid={Boolean(validationError)} aria-describedby={validationError ? errorId : undefined} onChange={(event) => setSettings((current) => ({ ...current, custom_patterns: (current.custom_patterns ?? []).map((value, patternIndex) => patternIndex === index ? event.target.value : value) }))} placeholder={t('privacy.patternPlaceholder')} spellCheck={false} /></label><button type="button" className="policy-icon-button" onClick={() => setSettings((current) => ({ ...current, custom_patterns: (current.custom_patterns ?? []).filter((_, patternIndex) => patternIndex !== index) }))} aria-label={t('privacy.removePattern', { count: index + 1 })}>{t('privacy.removePatternShort')}</button>{validationError && <p id={errorId} className="policy-inline-error" role="alert">{t(`privacy.pattern${validationError === 'empty' ? 'Empty' : 'Invalid'}`)}</p>}</div> })}</div>}</fieldset>
      </div>}
      <div className="policy-panel-footer"><small>{t('privacy.configurationFooter')}</small><button disabled={settingsDisabled} className="policy-primary">{saving ? t('privacy.saving') : t('meta.save')} <span>+</span></button></div>
    </form>
    <section className="policy-section-heading"><div><span>{t('privacy.rightsIndex')}</span><h2>{t('privacy.rightsTitle')}</h2></div><p>{t('privacy.rightsHint')}</p></section>
    <section className="policy-panel policy-rights-panel"><div className="policy-rights-intro"><span className="policy-index">{t('privacy.rightsAbbreviation')}</span><div><h3>{t('privacy.subjectTitle')}</h3><p>{t('privacy.subjectHint')}</p></div></div><form onSubmit={exportSubject} className="policy-rights-form"><label htmlFor="data-subject-id">{t('privacy.userId')}<input id="data-subject-id" value={userId} onChange={(event) => setUserId(event.target.value)} placeholder={t('privacy.userIdPlaceholder')} /></label><div className="policy-action-row"><button disabled={!userId.trim() || action !== null} className="policy-secondary">{action === 'export' ? t('privacy.exporting') : t('privacy.export')}</button><button type="button" onClick={() => setSubjectPendingDeletion(userId.trim())} disabled={!userId.trim() || action !== null} className="policy-danger">{action === 'delete' ? t('privacy.deleting') : t('privacy.delete')}</button></div></form></section>
    <section className="policy-section-heading"><div><span>{t('privacy.auditIndex')}</span><h2>{t('privacy.auditTitle')}</h2></div><p>{t('privacy.auditHint')}</p></section>
    <section className="policy-panel">{auditRecords.length === 0 ? <p className="operations-muted">{t('privacy.auditEmpty')}</p> : <div className="operations-ledger">{auditRecords.map((record) => <article className="operations-ledger-row" key={record.id}><strong>{t(`privacy.auditActions.${record.action}`, { defaultValue: record.action })}</strong><span className="operations-source">{record.subject_hash}</span><span className="operations-source">{record.details ? JSON.stringify(record.details) : t('privacy.noDetails')}</span><time className="operations-time">{formatDateTime(record.created_at)}</time></article>)}</div>}</section>
    {subjectPendingDeletion && <ConfirmationDialog title={t('meta.confirmDestructiveAction')} description={t('privacy.deleteConfirm', { userId: subjectPendingDeletion })} cancelLabel={t('meta.cancel')} confirmLabel={t('privacy.delete')} onCancel={() => setSubjectPendingDeletion(null)} onConfirm={() => { setSubjectPendingDeletion(null); void deleteSubject() }} />}
  </div>
}

function CapabilityUnavailable({ label }: { label: string }) {
  const { t } = useTranslation()
  return <div className="policy-unavailable"><span>{t('privacy.capabilityUnavailable')}</span><p>{label}</p><small>{t('privacy.capabilityUnavailableHint')}</small></div>
}

function SettingToggle({ label, description, checked, disabled, onChange }: { label: string; description: string; checked: boolean; disabled: boolean; onChange: (checked: boolean) => void }) {
  const { t } = useTranslation()
  return <label className="policy-toggle"><input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /><span className="policy-switch" /><span><strong>{label}</strong><small>{description}</small></span><em>{checked ? t('privacy.enabled') : t('privacy.disabled')}</em></label>
}
