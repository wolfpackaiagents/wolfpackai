import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import ConfirmationDialog from '../components/ConfirmationDialog'
import ContextCombobox from '../components/ContextCombobox'
import { createSchedule, fetchMeshCatalog, fetchScheduleRuns, fetchSchedules, scheduleAction, updateSchedule } from '../lib/api'
import type { MeshCatalog, Schedule, ScheduleInput, ScheduleRun, ScheduleStatus } from '../lib/types'

const blank = (): ScheduleInput => ({ registration_id: '', name: '', schedule_type: 'interval', timezone: 'UTC', at: null, interval_seconds: 3600, cron: null, payload: {}, max_attempts: 3, retry_delay_seconds: 60 })

function instructionFor(schedule: Schedule) {
  return typeof schedule.payload.instruction === 'string' ? schedule.payload.instruction : ''
}

function parametersFor(schedule: Schedule) {
  const parameters = schedule.payload.parameters
  return parameters && typeof parameters === 'object' && !Array.isArray(parameters) ? parameters as Record<string, unknown> : {}
}

export default function Schedules() {
  const { t } = useTranslation()
  const [items, setItems] = useState<Schedule[]>([])
  const [catalog, setCatalog] = useState<MeshCatalog | null>(null)
  const [status, setStatus] = useState<ScheduleStatus | ''>('')
  const [editor, setEditor] = useState<Schedule | null | undefined>(undefined)
  const [runs, setRuns] = useState<ScheduleRun[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [pendingCancel, setPendingCancel] = useState<Schedule | null>(null)
  const [error, setError] = useState('')
  const selectedSchedule = items.find((item) => item.id === selected) ?? null

  const load = async () => {
    try { setItems(await fetchSchedules(status || undefined)); setError('') } catch { setError(t('schedules.requestFailed')) }
  }

  useEffect(() => { void load() }, [status])
  useEffect(() => { void fetchMeshCatalog().then(setCatalog) }, [])

  async function select(id: string) {
    setSelected(id)
    try { setRuns(await fetchScheduleRuns(id)) } catch { setError(t('schedules.historyFailed')) }
  }

  async function act(item: Schedule, action: 'pause' | 'resume' | 'run-now') {
    try {
      await scheduleAction(item.id, action)
      await load()
      if (selected === item.id) await select(item.id)
    } catch { setError(t('schedules.actionFailed')) }
  }

  const registrations = catalog?.environments.flatMap((environment) => environment.registrations.map((registration) => ({ value: registration.id, label: `${environment.name} / ${registration.definition_name} v${registration.definition_version}` }))) ?? []

  return <main className="operations-console schedules-page">
    <header className="operations-hero"><div className="operations-hero-grid" /><div className="operations-hero-copy"><p className="operations-eyebrow">OPERATE / DURABLE TRIGGERS</p><h1>{t('schedules.title')}</h1><p>{t('schedules.subtitle')}</p></div><div className="operations-hero-action"><button className="primary-hero-action" onClick={() => setEditor(null)}>{t('schedules.create')} <b>+</b></button></div></header>
    {error && <p role="alert" className="operations-feedback is-error">{error}</p>}
    <section className="operations-section"><div className="operations-section-heading"><div><p>01 / SCHEDULES</p><h2>{t('schedules.title')}</h2></div><div className="operations-filter"><span>{t('schedules.status')}</span><ContextCombobox label={t('schedules.status')} value={status} allLabel={t('schedules.allStatuses')} options={(['active', 'paused', 'cancelled', 'completed'] as ScheduleStatus[]).map((value) => ({ value, label: t(`schedules.statuses.${value}`) }))} onChange={(value) => setStatus(value as ScheduleStatus)} /></div></div>
      <div className="operations-ledger"><div className="operations-ledger-head schedule-row"><span>{t('schedules.name')}</span><span>{t('schedules.instruction')}</span><span>{t('schedules.cadence')}</span><span>{t('schedules.nextRun')}</span><span>{t('schedules.retry')}</span><span>{t('meta.actions')}</span></div>{items.length === 0 ? <div className="operations-state">{t('schedules.empty')}</div> : items.map((item) => <article className="operations-ledger-row schedule-row" key={item.id} onClick={() => void select(item.id)}><div data-label={t('schedules.name')}><strong className="operations-tool">{item.name}</strong><span className={`operations-status is-${item.status}`}>{t(`schedules.statuses.${item.status}`)}</span></div><div data-label={t('schedules.instruction')} className="schedule-instruction">{instructionFor(item) || t('schedules.noInstruction')}</div><div data-label={t('schedules.cadence')}>{cadence(item)}</div><time data-label={t('schedules.nextRun')} className="operations-time">{item.next_run_at ? new Date(item.next_run_at).toLocaleString() : t('meta.notAvailable')}</time><div data-label={t('schedules.retry')} className="operations-time">{item.retry.max_attempts}x / {item.retry.delay_seconds}s</div><div data-label={t('meta.actions')} className="operations-actions" onClick={(event) => event.stopPropagation()}><button onClick={() => setEditor(item)}>{t('schedules.edit')}</button>{item.status === 'active' && <><button onClick={() => void act(item, 'pause')}>{t('schedules.pause')}</button><button onClick={() => void act(item, 'run-now')}>{t('schedules.runNow')}</button></>}{item.status === 'paused' && <button onClick={() => void act(item, 'resume')}>{t('schedules.resume')}</button>}{item.status !== 'cancelled' && <button className="operations-reject" onClick={() => setPendingCancel(item)}>{t('schedules.cancel')}</button>}</div></article>)}</div>
    </section>
    {selectedSchedule && <><section className="operations-section schedule-details"><div className="operations-section-heading"><div><p>02 / EXECUTION SPECIFICATION</p><h2>{t('schedules.executionSpec')}</h2></div></div><div className="operations-ledger"><div className="schedule-details-body"><div><span>{t('schedules.instruction')}</span><p>{instructionFor(selectedSchedule) || t('schedules.noInstruction')}</p></div><div><span>{t('schedules.parameters')}</span><code>{JSON.stringify(parametersFor(selectedSchedule), null, 2)}</code></div></div></div></section><section className="operations-section"><div className="operations-section-heading"><div><p>03 / EXECUTION HISTORY</p><h2>{t('schedules.runHistory')}</h2></div></div><div className="operations-ledger"><div className="operations-ledger-head schedule-run-row"><span>{t('schedules.status')}</span><span>{t('schedules.when')}</span><span>{t('schedules.retry')}</span><span>{t('schedules.trace')}</span></div>{runs.map((run) => <article className="operations-ledger-row schedule-run-row" key={run.id}><div data-label={t('schedules.status')}><span className={`operations-status is-${run.status}`}>{t(`schedules.runStatuses.${run.status}`)}</span>{run.error && <small>{run.error}</small>}</div><time data-label={t('schedules.when')} className="operations-time">{new Date(run.scheduled_for).toLocaleString()}</time><div data-label={t('schedules.retry')} className="operations-time">{run.attempt}/{run.max_attempts}{run.retry_at && `, ${t('schedules.retryAt')} ${new Date(run.retry_at).toLocaleString()}`}</div><div data-label={t('schedules.trace')}>{run.trace_context ? <Link className="operations-link" to={`/traces/${run.trace_context.id}`}>{run.trace_context.name}</Link> : run.trace_id ? <Link className="operations-link" to={`/traces/${run.trace_id}`}>{run.trace_id}</Link> : t('schedules.noTrace')}</div></article>)}</div></section></>}
    {editor !== undefined && <ScheduleEditor schedule={editor} registrations={registrations} onClose={() => setEditor(undefined)} onSave={async (input) => { if (editor) await updateSchedule(editor.id, input); else await createSchedule(input); await load() }} />}
    {pendingCancel && <ConfirmationDialog title={t('meta.confirmDestructiveAction')} description={t('schedules.cancelConfirm', { name: pendingCancel.name })} cancelLabel={t('meta.cancel')} confirmLabel={t('schedules.cancel')} onCancel={() => setPendingCancel(null)} onConfirm={() => { void scheduleAction(pendingCancel.id, 'cancel').then(load).catch(() => setError(t('schedules.actionFailed'))); setPendingCancel(null) }} />}
  </main>
}

function ScheduleEditor({ schedule, registrations, onClose, onSave }: { schedule: Schedule | null; registrations: { value: string; label: string }[]; onClose: () => void; onSave: (input: ScheduleInput) => Promise<void> }) {
  const { t } = useTranslation()
  const initialPayload = schedule?.payload ?? {}
  const [form, setForm] = useState<ScheduleInput>(schedule ? { registration_id: schedule.registration_id, name: schedule.name, schedule_type: schedule.schedule_type, timezone: schedule.timezone, at: schedule.at, interval_seconds: schedule.interval_seconds, cron: schedule.cron, payload: initialPayload, max_attempts: schedule.retry.max_attempts, retry_delay_seconds: schedule.retry.delay_seconds } : blank())
  const [instruction, setInstruction] = useState(schedule ? instructionFor(schedule) : '')
  const [parameters, setParameters] = useState(() => JSON.stringify(schedule ? parametersFor(schedule) : {}, null, 2))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedInstruction = instruction.trim()
    if (!trimmedInstruction) { setError(t('schedules.instructionRequired')); return }
    let parsedParameters: Record<string, unknown>
    try {
      const parsed = JSON.parse(parameters)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Parameters must be an object')
      parsedParameters = parsed as Record<string, unknown>
    } catch { setError(t('schedules.parametersInvalid')); return }
    setSaving(true)
    try {
      await onSave({ ...form, payload: { ...form.payload, instruction: trimmedInstruction, parameters: parsedParameters } })
      onClose()
    } catch { setError(t('schedules.saveFailed')) } finally { setSaving(false) }
  }

  return <div className="confirmation-backdrop"><form className="confirmation-dialog schedule-editor" aria-label={schedule ? t('schedules.edit') : t('schedules.create')} onSubmit={(event) => void submit(event)}><h2>{schedule ? t('schedules.edit') : t('schedules.create')}</h2>{error && <p role="alert">{error}</p>}<label>{t('schedules.name')}<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><ContextCombobox label={t('schedules.registration')} value={form.registration_id} options={registrations} searchable onChange={(registration_id) => setForm({ ...form, registration_id })} /><ContextCombobox label={t('schedules.type')} value={form.schedule_type} options={['interval', 'cron', 'at'].map((value) => ({ value, label: t(`schedules.types.${value}`) }))} onChange={(schedule_type) => setForm({ ...form, schedule_type: schedule_type as ScheduleInput['schedule_type'] })} />{form.schedule_type === 'interval' && <label>{t('schedules.interval')}<input type="number" min="1" value={form.interval_seconds ?? ''} onChange={(event) => setForm({ ...form, interval_seconds: Number(event.target.value) })} /></label>}{form.schedule_type === 'cron' && <label>{t('schedules.cron')}<input required value={form.cron ?? ''} onChange={(event) => setForm({ ...form, cron: event.target.value })} /></label>}{form.schedule_type === 'at' && <label>{t('schedules.at')}<input required type="datetime-local" value={form.at?.slice(0, 16) ?? ''} onChange={(event) => setForm({ ...form, at: new Date(event.target.value).toISOString() })} /></label>}<label>{t('schedules.instruction')}<textarea required value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder={t('schedules.instructionPlaceholder')} /></label><label>{t('schedules.parameters')}<textarea value={parameters} onChange={(event) => setParameters(event.target.value)} spellCheck={false} aria-describedby="schedule-parameters-hint" /></label><small id="schedule-parameters-hint">{t('schedules.parametersHint')}</small><label>{t('schedules.maxAttempts')}<input type="number" min="1" value={form.max_attempts} onChange={(event) => setForm({ ...form, max_attempts: Number(event.target.value) })} /></label><label>{t('schedules.retryDelay')}<input type="number" min="1" value={form.retry_delay_seconds} onChange={(event) => setForm({ ...form, retry_delay_seconds: Number(event.target.value) })} /></label><div className="confirmation-actions"><button type="button" className="confirmation-cancel" onClick={onClose}>{t('meta.cancel')}</button><button disabled={saving} className="operations-approve">{saving ? t('meta.loading') : t('meta.save')}</button></div></form></div>
}

function cadence(schedule: Schedule) { return schedule.schedule_type === 'interval' ? `${schedule.interval_seconds}s` : schedule.schedule_type === 'cron' ? schedule.cron : schedule.at ? new Date(schedule.at).toLocaleString() : 'N/A' }
