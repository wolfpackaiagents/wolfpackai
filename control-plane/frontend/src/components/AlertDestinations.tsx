import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { createAlertDestination, deleteAlertDestination, fetchAlertDestinations, testAlertDestination, updateAlertDestination } from '../lib/api'
import type { AlertDestination, AlertDestinationInput, AlertDestinationType } from '../lib/types'

const emptyInput: AlertDestinationInput = { name: '', destination_type: 'slack_webhook', config: {}, enabled: true }

const CONFIG_FIELDS: Record<AlertDestinationType, Array<{ key: string; label: string; type: string; placeholder: string }>> = {
  slack_webhook: [
    { key: 'webhook_url', label: 'Slack Webhook URL', type: 'url', placeholder: 'https://hooks.slack.com/services/...' },
  ],
  discord_webhook: [
    { key: 'webhook_url', label: 'Discord Webhook URL', type: 'url', placeholder: 'https://discord.com/api/webhooks/...' },
  ],
  smtp: [
    { key: 'host', label: 'SMTP Host', type: 'text', placeholder: 'smtp.example.com' },
    { key: 'port', label: 'Port', type: 'number', placeholder: '587' },
    { key: 'username', label: 'Username', type: 'text', placeholder: '' },
    { key: 'password', label: 'Password', type: 'password', placeholder: '' },
    { key: 'from', label: 'From Address', type: 'email', placeholder: 'amp@wolfpack.ai' },
    { key: 'to', label: 'To Addresses (comma-separated)', type: 'text', placeholder: 'team@example.com' },
  ],
}

export default function AlertDestinations() {
  const { t } = useTranslation()
  const [destinations, setDestinations] = useState<AlertDestination[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [input, setInput] = useState<AlertDestinationInput>(emptyInput)
  const [working, setWorking] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [testing, setTesting] = useState<string | null>(null)
  const [testStatus, setTestStatus] = useState<{ id: string; message: string } | null>(null)

  useEffect(() => { void load() }, [t])

  async function load() {
    try {
      const items = await fetchAlertDestinations()
      setDestinations(items)
    } catch { setError(t('resilience.requestFailed')) }
  }

  function reset() { setShowForm(false); setEditingId(null); setInput(emptyInput); setTestStatus(null) }

  function changeType(type: string) {
    setInput((prev) => {
      const fresh: Record<string, unknown> = {}
      for (const field of CONFIG_FIELDS[type as AlertDestinationType] || []) fresh[field.key] = ''
      return { ...prev, destination_type: type as AlertDestinationType, config: fresh }
    })
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setWorking('form'); setError('')
    try {
      const dest = editingId ? await updateAlertDestination(editingId, input) : await createAlertDestination(input)
      setDestinations((items) => editingId ? items.map((d) => d.id === dest.id ? dest : d) : [...items, dest])
      reset()
    } catch { setError(t('resilience.requestFailed')) }
    finally { setWorking(null) }
  }

  async function remove(id: string) {
    setWorking(id); setError('')
    try { await deleteAlertDestination(id); setDestinations((items) => items.filter((d) => d.id !== id)); if (editingId === id) reset() }
    catch { setError(t('resilience.requestFailed')) }
    finally { setWorking(null) }
  }

  async function test(id: string) {
    setTesting(id); setTestStatus(null); setError('')
    try { await testAlertDestination(id); setTestStatus({ id, message: 'Test sent successfully!' }) }
    catch (err: unknown) { setTestStatus({ id, message: err instanceof Error ? err.message : 'Test failed' }) }
    finally { setTesting(null) }
  }

  function edit(dest: AlertDestination) {
    setInput({ name: dest.name, destination_type: dest.destination_type as AlertDestinationType, config: dest.config as Record<string, unknown>, enabled: dest.enabled })
    setEditingId(dest.id); setShowForm(true); setTestStatus(null)
  }

  return <section className="operations-section">
    <div className="operations-section-heading">
      <div><p>04</p><h2>Notification Destinations</h2></div>
      {!showForm && <button onClick={() => { reset(); setShowForm(true) }} className="operations-refresh">Add Destination</button>}
    </div>

    {error && <p role="alert" className="operations-feedback is-error">{error}</p>}

    {showForm && <form onSubmit={(event) => void save(event)} className="schedule-editor">
      <label>Name
        <input required value={input.name} onChange={(e) => setInput({ ...input, name: e.target.value })} />
      </label>
      <label>Type
        <select required value={input.destination_type} onChange={(e) => changeType(e.target.value)}>
          <option value="slack_webhook">Slack Webhook</option>
          <option value="discord_webhook">Discord Webhook</option>
          <option value="smtp">SMTP Email</option>
        </select>
      </label>
      {CONFIG_FIELDS[input.destination_type]?.map((field) => (
        <label key={field.key}>{field.label}
          <input
            required={field.key === 'webhook_url' || field.key === 'host'}
            type={field.type}
            value={(input.config[field.key] as string) ?? ''}
            placeholder={field.placeholder}
            onChange={(e) => setInput({ ...input, config: { ...input.config, [field.key]: field.type === 'number' ? Number(e.target.value) : e.target.value } })}
          />
        </label>
      ))}
      <label className="channel-enabled">
        <input type="checkbox" checked={input.enabled} onChange={(e) => setInput({ ...input, enabled: e.target.checked })} />
        <span><strong>Enabled</strong><small>Receive notifications when alerts are created</small></span>
      </label>
      <div className="operations-action-bar">
        <button type="submit" disabled={working === 'form'} className="operations-refresh">{working === 'form' ? 'Saving...' : editingId ? 'Update' : 'Create'}</button>
        <button type="button" onClick={reset} className="operations-refresh" style={{ opacity: 0.6 }}>Cancel</button>
      </div>
    </form>}

    {destinations.length === 0 ? <p className="operations-state">{t('resilience.unavailable')}</p> : <div className="operations-ledger">
      <div className="operations-ledger-head" style={{ display: 'grid', gridTemplateColumns: '2fr 1.5fr 3fr 1fr 1fr', gap: '0.5rem', padding: '0.5rem 0.75rem' }}>
        <span>Name</span><span>Type</span><span>Status</span><span>Last Notified</span><span />
      </div>
      {destinations.map((dest) => (
        <div key={dest.id} className="operations-ledger-row" style={{ display: 'grid', gridTemplateColumns: '2fr 1.5fr 3fr 1fr 1fr', gap: '0.5rem', alignItems: 'center', padding: '0.5rem 0.75rem' }}>
          <span>{dest.name}</span>
          <span style={{ textTransform: 'capitalize' }}>{dest.destination_type.replace('_', ' ')}</span>
          <span>
            <span className={`operations-severity is-${dest.enabled ? 'warning' : 'info'}`}>{dest.enabled ? 'Enabled' : 'Disabled'}</span>
            {dest.last_error && <span className="operations-severity is-danger" title={dest.last_error}>Error</span>}
          </span>
          <span className="operations-time">{dest.last_notified_at ? new Date(dest.last_notified_at).toLocaleString() : '-'}</span>
          <span style={{ display: 'flex', gap: '0.25rem' }}>
            <button onClick={() => edit(dest)} disabled={working === dest.id} className="operations-refresh" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>Edit</button>
            <button onClick={() => void test(dest.id)} disabled={testing === dest.id} className="operations-refresh" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>{testing === dest.id ? '...' : 'Test'}</button>
            <button onClick={() => void remove(dest.id)} disabled={working === dest.id} className="operations-refresh" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', opacity: 0.6 }}>Remove</button>
          </span>
          {testStatus?.id === dest.id && <p className="operations-feedback" style={{ gridColumn: '1 / -1', margin: 0 }}>{testStatus.message}</p>}
        </div>
      ))}
    </div>}
  </section>
}