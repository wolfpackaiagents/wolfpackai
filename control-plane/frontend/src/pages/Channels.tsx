import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import ConfirmationDialog from '../components/ConfirmationDialog'
import ContextCombobox from '../components/ContextCombobox'
import { createChannelConnection, createProviderSecret, deleteChannelConnection, fetchChannelConnections, fetchChannelDeliveries, fetchMeshCatalog, fetchProviderSecrets, rotateProviderSecret, updateChannelConnection } from '../lib/api'
import type { ChannelConnection, ChannelConnectionInput, ChannelDelivery, ChannelProvider, MeshCatalog, ProviderSecret } from '../lib/types'

const requirements: Record<ChannelProvider, string[]> = { telegram: ['bot_token', 'webhook_secret'], slack: ['bot_token', 'signing_secret'], discord: ['bot_token', 'public_key'] }
const blank = (): ChannelConnectionInput => ({ channel: 'telegram', name: '', registration_id: '', enabled: true, secret_refs: { bot_token: '', webhook_secret: '' }, allowlist: [] })

type RegistrationOption = { value: string; label: string; environment: string; agent: string; version: string }

export default function Channels() {
  const { t } = useTranslation()
  const [connections, setConnections] = useState<ChannelConnection[]>([])
  const [deliveries, setDeliveries] = useState<ChannelDelivery[]>([])
  const [catalog, setCatalog] = useState<MeshCatalog | null>(null)
  const [editor, setEditor] = useState<ChannelConnection | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<ChannelConnection | null>(null)
  const [error, setError] = useState('')
  const load = async () => {
    try {
      const [items, receiptItems] = await Promise.all([fetchChannelConnections(), fetchChannelDeliveries()])
      setConnections(items)
      setDeliveries(receiptItems)
      setError('')
    } catch {
      setError(t('channels.requestFailed'))
    }
  }
  useEffect(() => { void load(); void fetchMeshCatalog().then(setCatalog) }, [])
  const registrations: RegistrationOption[] = catalog?.environments.flatMap((environment) => environment.registrations.map((registration) => ({ value: registration.id, label: `${environment.name} / ${registration.definition_name} v${registration.definition_version}`, environment: environment.name, agent: registration.definition_name, version: registration.definition_version }))) ?? []
  const setEnabled = async (connection: ChannelConnection, enabled: boolean) => {
    try { await updateChannelConnection(connection.id, { enabled }); await load() } catch { setError(t('channels.saveFailed')) }
  }
  const remove = async () => {
    if (!deleting) return
    try { await deleteChannelConnection(deleting.id); setDeleting(null); await load() } catch { setDeleting(null); setError(t('channels.deleteFailed')) }
  }

  return <main className="operations-console channels-page">
    <header className="operations-hero"><div className="operations-hero-grid" /><div className="operations-hero-copy"><p className="operations-eyebrow">OPERATE / CHANNEL BOUNDARIES</p><h1>{t('channels.title')}</h1><p>{t('channels.subtitle')}</p></div><div className="operations-hero-action"><button className="primary-hero-action" onClick={() => setEditor(null)}>{t('channels.add')} <b>+</b></button></div></header>
    {error && <p role="alert" className="operations-feedback is-error">{error}</p>}
    <section className="operations-section"><div className="operations-section-heading"><div><p>01 / CONNECTIONS</p><h2>{t('channels.connections')}</h2></div></div><div className="operations-ledger"><div className="operations-ledger-head schedule-row"><span>{t('channels.provider')}</span><span>{t('channels.mapping')}</span><span>{t('channels.health')}</span><span>{t('channels.lastDelivery')}</span><span>{t('meta.actions')}</span></div>{connections.length === 0 ? <div className="operations-state">{t('channels.empty')}</div> : connections.map((item) => <article className="operations-ledger-row schedule-row" key={item.id}><div data-label={t('channels.provider')}><strong className="operations-tool">{item.name}</strong><span>{item.channel}</span></div><div data-label={t('channels.mapping')}>{item.registration.environment_name} / {item.registration.definition_name} v{item.registration.definition_version}<small>{item.allowlist.length} {t('channels.allowlist').toLowerCase()}</small></div><div data-label={t('channels.health')}><span className={`operations-status is-${item.health === 'healthy' ? 'approved' : item.health === 'degraded' ? 'rejected' : 'pending'}`}>{t(`channels.healthStates.${item.health}`)}</span></div><div data-label={t('channels.lastDelivery')} className="operations-time">{item.last_delivery ? <>{t(`channels.deliveryStates.${item.last_delivery.status}`)} · {item.last_delivery.attempts}x<br />{new Date(item.last_delivery.created_at).toLocaleString()}</> : t('meta.notAvailable')}</div><div data-label={t('meta.actions')} className="operations-actions"><button onClick={() => setEditor(item)}>{t('channels.configure')}</button><button onClick={() => void setEnabled(item, !item.enabled)}>{t(item.enabled ? 'channels.disable' : 'channels.enable')}</button><button className="confirmation-destructive" onClick={() => setDeleting(item)}>{t('channels.delete')}</button></div></article>)}</div></section>
    <section className="operations-section"><div className="operations-section-heading"><div><p>02 / DELIVERY RECEIPTS</p><h2>{t('channels.receipts')}</h2></div></div><div className="operations-ledger"><div className="operations-ledger-head schedule-run-row"><span>{t('channels.provider')}</span><span>{t('meta.status')}</span><span>{t('channels.retries')}</span><span>{t('channels.lastDelivery')}</span><span>{t('channels.trace')}</span></div>{deliveries.map((item) => <article className="operations-ledger-row schedule-run-row" key={item.id}><div data-label={t('channels.provider')}>{item.channel}</div><div data-label={t('meta.status')}><span className={`operations-status is-${item.status === 'delivered' ? 'approved' : item.status === 'failed' ? 'rejected' : 'pending'}`}>{t(`channels.deliveryStates.${item.status}`)}</span>{item.error && <small>{item.error}</small>}</div><div data-label={t('channels.retries')}>{item.attempts}x</div><time data-label={t('channels.lastDelivery')} className="operations-time">{new Date(item.created_at).toLocaleString()}</time><div data-label={t('channels.trace')}>{item.trace_context ? <Link className="operations-link" to={`/traces/${item.trace_context.id}`}>{item.trace_context.name}</Link> : item.trace_id ? <Link className="operations-link" to={`/traces/${item.trace_id}`}>{item.trace_id}</Link> : t('channels.noTrace')}</div></article>)}</div></section>
    {editor !== undefined && <ConnectionEditor connection={editor} registrations={registrations} onClose={() => setEditor(undefined)} onSave={async (input) => { if (editor) await updateChannelConnection(editor.id, input); else await createChannelConnection(input); await load() }} />}
    {deleting && <ConfirmationDialog title={t('channels.confirmDeleteTitle')} description={t('channels.confirmDelete', { name: deleting.name })} cancelLabel={t('meta.cancel')} confirmLabel={t('channels.delete')} onCancel={() => setDeleting(null)} onConfirm={() => void remove()} />}
  </main>
}

function ConnectionEditor({ connection, registrations, onClose, onSave }: { connection: ChannelConnection | null; registrations: RegistrationOption[]; onClose: () => void; onSave: (input: ChannelConnectionInput) => Promise<void> }) {
  const { t } = useTranslation()
  const [form, setForm] = useState<ChannelConnectionInput>(connection ? { channel: connection.channel, name: connection.name, registration_id: connection.registration.id, enabled: connection.enabled, secret_refs: connection.secret_refs, allowlist: connection.allowlist } : blank())
  const [secrets, setSecrets] = useState<ProviderSecret[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [guideField, setGuideField] = useState<string | null>(null)
  useEffect(() => { void fetchProviderSecrets().then(setSecrets).catch(() => setError(t('channels.secretsLoadFailed'))) }, [t])
  const selectedRegistration = registrations.find((registration) => registration.value === form.registration_id)
  const changeChannel = (channel: ChannelProvider) => setForm({ ...form, channel, secret_refs: Object.fromEntries(requirements[channel].map((key) => [key, ''])) })
  const updateSecret = (field: string, secretId: string) => setForm((current) => ({ ...current, secret_refs: { ...current.secret_refs, [field]: secretId } }))
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (requirements[form.channel].some((field) => !form.secret_refs[field])) { setError(t('channels.selectRequiredSecrets')); return }
    setSaving(true)
    try { await onSave({ ...form, allowlist: form.allowlist.filter(Boolean) }); onClose() } catch { setError(t('channels.saveFailed')) } finally { setSaving(false) }
  }
  return <div className="confirmation-backdrop"><form className="confirmation-dialog channel-editor" aria-label={connection ? t('channels.configure') : t('channels.add')} onSubmit={(event) => void submit(event)}>
    <header className="channel-editor-header"><h2>{connection ? t('channels.configure') : t('channels.add')}</h2><p>{t('channels.secretHint')}</p></header>
    {error && <p role="alert" className="operations-feedback is-error">{error}</p>}
    <section className="channel-editor-section"><div className="channel-editor-section-heading"><span>01</span><div><h3>{t('channels.connectionIdentity')}</h3><p>{t('channels.connectionIdentityHint')}</p></div></div><div className="channel-identity-grid"><label>{t('channels.name')}<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label>{t('channels.provider')}<ContextCombobox label={t('channels.provider')} value={form.channel} options={(['telegram', 'slack', 'discord'] as ChannelProvider[]).map((value) => ({ value, label: value }))} onChange={(value) => changeChannel(value as ChannelProvider)} disabled={Boolean(connection)} /></label><label className="channel-enabled"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} /><span><strong>{t('channels.enabled')}</strong><small>{t('channels.enabledHint')}</small></span></label></div></section>
    <section className="channel-editor-section"><div className="channel-editor-section-heading"><span>02</span><div><h3>{t('channels.registration')}</h3><p>{t('channels.targetAgentHint')}</p></div></div><label>{t('channels.registration')}<ContextCombobox label={t('channels.registration')} value={form.registration_id} options={registrations} searchable onChange={(registration_id) => setForm({ ...form, registration_id })} /></label>{selectedRegistration && <p className="channel-selection">{t('channels.selectedRegistration', selectedRegistration)}</p>}</section>
    <section className="channel-editor-section channel-credentials"><div className="channel-editor-section-heading"><span>03</span><div><h3>{t('channels.credentials')}</h3><p>{t('channels.credentialsHint')}</p></div></div>{requirements[form.channel].map((field) => <SecretBinding field={field} key={field} provider={form.channel} secrets={secrets} selectedId={form.secret_refs[field] ?? ''} onSelect={(secretId) => updateSecret(field, secretId)} onCreated={(secret) => { setSecrets((current) => [...current, secret]); updateSecret(field, secret.id) }} onRotated={(secret) => setSecrets((current) => current.map((item) => item.id === secret.id ? secret : item))} onGuide={() => setGuideField(field)} />)}</section>
    <section className="channel-editor-section"><div className="channel-editor-section-heading"><span>04</span><div><h3>{t('channels.allowlist')}</h3><p>{t(`channels.guides.${form.channel}.allowlist`)}</p></div></div><label className="channel-allowlist">{t('channels.allowlist')}<textarea aria-describedby="channel-allowlist-help" value={form.allowlist.join('\n')} onChange={(event) => setForm({ ...form, allowlist: event.target.value.split('\n').map((value) => value.trim()) })} /></label><small id="channel-allowlist-help">{t('channels.allowlistHint')}</small></section>
    <footer className="confirmation-actions"><button type="button" className="confirmation-cancel" onClick={onClose}>{t('meta.cancel')}</button><button type="submit" disabled={saving}>{saving ? t('meta.loading') : t('meta.save')}</button></footer>
    {guideField && <ProviderGuideModal provider={form.channel} field={guideField} onClose={() => setGuideField(null)} />}
  </form></div>
}

function SecretBinding({ field, provider, secrets, selectedId, onSelect, onCreated, onRotated, onGuide }: { field: string; provider: ChannelProvider; secrets: ProviderSecret[]; selectedId: string; onSelect: (id: string) => void; onCreated: (secret: ProviderSecret) => void; onRotated: (secret: ProviderSecret) => void; onGuide: () => void }) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<'create' | 'rotate' | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const valueRef = useRef<HTMLInputElement>(null)
  const label = t(`channels.secretFields.${field}`)
  const providerSecrets = secrets.filter((secret) => secret.provider === provider)
  const selected = providerSecrets.find((secret) => secret.id === selectedId)
  async function create() { const value = valueRef.current?.value; if (!value) return; setBusy(true); try { onCreated(await createProviderSecret({ provider, name, value })); setName(''); setMode(null) } finally { if (valueRef.current) valueRef.current.value = ''; setBusy(false) } }
  async function rotate() { if (!selected) return; const value = valueRef.current?.value; if (!value) return; setBusy(true); try { onRotated(await rotateProviderSecret(selected.id, value)); setMode(null) } finally { if (valueRef.current) valueRef.current.value = ''; setBusy(false) } }
  return <fieldset className="channel-credential"><legend>{label} <button type="button" className="channel-guide-btn" aria-label={t('channels.setupGuide')} onClick={onGuide}>?</button></legend><ContextCombobox label={t('channels.vaultSecret', { field: label })} value={selectedId} options={providerSecrets.map((secret) => ({ value: secret.id, label: `${secret.name} · v${secret.version}` }))} emptyLabel={t('channels.noVaultSecrets')} searchable onChange={onSelect} /><small>{selected ? t('channels.secretSelected', { mask: selected.value_masked, version: selected.version }) : t('channels.selectVaultSecret')}</small>{mode === null && <div className="operations-actions"><button type="button" onClick={() => setMode('create')}>{t('channels.createVaultSecret')}</button>{selected && <button type="button" onClick={() => setMode('rotate')}>{t('channels.rotateVaultSecret')}</button>}</div>}{mode === 'create' && <div className="channel-secret-form"><label>{t('channels.secretName', { field: label })}<input aria-label={t('channels.secretName', { field: label })} required pattern="[a-z][a-z0-9_-]{0,63}" value={name} onChange={(event) => setName(event.target.value)} /></label><label>{t('channels.secretValue', { field: label })}<input ref={valueRef} aria-label={t('channels.secretValue', { field: label })} required type="password" autoComplete="new-password" /></label><button type="button" disabled={busy || !name} onClick={() => void create()}>{t('channels.saveVaultSecret')}</button></div>}{mode === 'rotate' && <div className="channel-secret-form"><label>{t('channels.replacementValue', { field: label })}<input ref={valueRef} aria-label={t('channels.replacementValue', { field: label })} required type="password" autoComplete="new-password" /></label><button type="button" disabled={busy} onClick={() => void rotate()}>{t('channels.saveRotation')}</button></div>}</fieldset>
}

function ProviderGuideModal({ provider, field, onClose }: { provider: ChannelProvider; field: string; onClose: () => void }) {
  const { t } = useTranslation()
  const label = t(`channels.secretFields.${field}`)
  return <div className="confirmation-backdrop" onClick={onClose}><div className="provider-guide-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-label={t('channels.setupGuide')}><button className="mesh-close" onClick={onClose} aria-label={t('meta.back')}>×</button><h2>{t('channels.setupGuide')}</h2><p><strong>{label}</strong> · {t(`channels.guides.${provider}.vault`)}</p><p><strong>{t('channels.webhookPath')}:</strong> <code>{t(`channels.guides.${provider}.path`)}</code></p><ol><li>{t(`channels.guides.${provider}.console1`)}</li><li>{t(`channels.guides.${provider}.console2`)}</li><li>{t(`channels.guides.${provider}.console3`)}</li></ol><p><strong>{t('channels.allowlist')}:</strong> {t(`channels.guides.${provider}.allowlist`)}</p><p><strong>{t('channels.verificationChecklist')}:</strong> {t(`channels.guides.${provider}.verify`)}</p></div></div>
}
