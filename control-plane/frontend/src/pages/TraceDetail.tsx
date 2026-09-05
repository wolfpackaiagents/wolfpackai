import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { fetchTrace } from '../lib/api'
import type { Observation, TraceSummary } from '../lib/types'
import { formatDuration as formatLocalizedDuration, formatTime as formatLocalizedTime } from '../i18n/format'
import { formatCost, formatCostCoverage, reportedCost } from '../lib/cost'

type View = 'flow' | 'timeline' | 'tree'

export default function TraceDetail() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const [trace, setTrace] = useState<TraceSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Observation | null>(null)
  const [view, setView] = useState<View>('flow')

  useEffect(() => {
    if (!id) return
    setError(null)
    fetchTrace(id)
      .then((result) => {
        setTrace(result)
        setSelected(getRoots(result.observations)[0] ?? result.observations[0] ?? null)
      })
      .catch((reason) => setError(String(reason)))
  }, [id])

  if (error) return <div className="text-red-300">{t('meta.error')}: {error}</div>
  if (!trace) return <p className="text-slate-500">{t('meta.loading')}</p>

  const observations = trace.observations ?? []
  const tabs: View[] = ['flow', 'timeline', 'tree']

  return (
    <div className="space-y-5 trace-explorer trace-console">
      <header className="trace-explorer-header">
        <div className="min-w-0">
          <p className="trace-kicker">OPERATE / RUN INSPECTION</p><Link to="/traces" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-orange-200">&larr; {t('meta.back')}</Link>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{trace.name || t('traceDetail.unnamedTrace')}</h1>
            <code className="max-w-full truncate rounded bg-slate-900 px-2 py-1 text-xs text-slate-400">{trace.id}</code>
          </div>
        </div>
        <div className="trace-view-tabs" aria-label={t('traceDetail.views')}>
          {tabs.map((tab) => (
            <button key={tab} type="button" onClick={() => setView(tab)} className={view === tab ? 'is-active' : ''} aria-pressed={view === tab}>
              {t(`traceDetail.view${tab[0].toUpperCase()}${tab.slice(1)}`)}
            </button>
          ))}
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Meta label={t('traceDetail.colStart')} value={formatTime(trace.start_time)} />
        <Meta label={t('traceDetail.colLatency')} value={formatDuration(trace.latency_ms)} />
        <Meta label={t('traceDetail.colSession')} value={trace.session_id || t('traceDetail.notAvailable')} />
        <Meta label={t('traceDetail.colEnv')} value={trace.environment || t('traceDetail.notAvailable')} />
        <Meta label={t('traceDetail.metaCost')} value={formatCost(reportedCost(trace.cost, trace.cost_currency, trace.cost_coverage)) ?? t('traceDetail.notAvailable')} />
        <Meta label={t('traceDetail.costCoverage')} value={formatCostCoverage(reportedCost(trace.cost, trace.cost_currency, trace.cost_coverage)?.coverage ?? null) ?? t('traceDetail.costCoverageUnknown')} />
      </div>

      {observations.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 px-5 py-12 text-center text-sm text-slate-500">{t('traceDetail.noObservations')}</div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/40 p-3 sm:p-4">
            {view === 'flow' && <FlowView observations={observations} selectedId={selected?.id} onSelect={setSelected} />}
            {view === 'timeline' && <TimelineView observations={observations} selectedId={selected?.id} onSelect={setSelected} />}
            {view === 'tree' && <TreeView observations={observations} selectedId={selected?.id} onSelect={setSelected} />}
          </section>
          <aside className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/40 p-4 xl:sticky xl:top-20 xl:self-start">
            {selected ? <ObservationDetail obs={selected} /> : <p className="text-sm text-slate-500">{t('traceDetail.selectSpan')}</p>}
          </aside>
        </div>
      )}
    </div>
  )
}

function FlowView({ observations, selectedId, onSelect }: ExplorerViewProps) {
  const { t } = useTranslation()
  const rows = flattenTree(observations)
  const nodeWidth = 156
  const nodeHeight = 52
  const gutter = 30
  const width = Math.max(620, Math.max(...rows.map((row) => row.depth), 0) * 190 + nodeWidth + gutter * 2)
  const height = Math.max(240, rows.length * 82 + gutter * 2)
  const byId = new Map(observations.map((observation) => [observation.id, observation]))

  return (
    <div>
      <ViewHeading title={t('traceDetail.flowTitle')} description={t('traceDetail.flowHint')} />
      <div className="trace-flow-scroll">
        <svg className="trace-flow" viewBox={`0 0 ${width} ${height}`} role="list" aria-label={t('traceDetail.flowTitle')}>
          {rows.map(({ observation, depth }, index) => {
            const parent = observation.parent_observation_id ? byId.get(observation.parent_observation_id) : undefined
            const parentIndex = parent ? rows.findIndex((row) => row.observation.id === parent.id) : -1
            if (parentIndex < 0) return null
            const x1 = gutter + (depth - 1) * 190 + nodeWidth
            const y1 = gutter + parentIndex * 82 + nodeHeight / 2
            const x2 = gutter + depth * 190
            const y2 = gutter + index * 82 + nodeHeight / 2
            return <path key={`${observation.id}-edge`} d={`M ${x1} ${y1} C ${x1 + 34} ${y1}, ${x2 - 34} ${y2}, ${x2} ${y2}`} className="trace-flow-edge" />
          })}
          {rows.map(({ observation, depth }, index) => {
            const x = gutter + depth * 190
            const y = gutter + index * 82
            const active = selectedId === observation.id
            return (
              <g key={observation.id} role="listitem" className={`trace-flow-node ${active ? 'is-active' : ''}`} onClick={() => onSelect(observation)} onKeyDown={(event) => event.key === 'Enter' && onSelect(observation)} tabIndex={0} aria-label={`${observation.name || observation.id}, ${observation.type}`}>
                <rect x={x} y={y} width={nodeWidth} height={nodeHeight} rx="8" />
                <circle cx={x + 14} cy={y + 17} r="4" className={statusClass(observation)} />
                <text x={x + 25} y={y + 21} className="trace-flow-name">{truncate(observation.name || observation.id, 18)}</text>
                <text x={x + 12} y={y + 40} className="trace-flow-type">{observation.type} {formatObservationDuration(observation)}</text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

function TimelineView({ observations, selectedId, onSelect }: ExplorerViewProps) {
  const { t } = useTranslation()
  const timed = observations.map((observation) => ({ observation, start: toMillis(observation.start_time), end: toMillis(observation.end_time) }))
  const validStarts = timed.map((item) => item.start).filter((value): value is number => value !== null)
  const min = validStarts.length ? Math.min(...validStarts) : 0
  const max = Math.max(...timed.map((item) => item.end ?? item.start ?? min), min + 1)
  const total = Math.max(max - min, 1)

  return (
    <div>
      <ViewHeading title={t('traceDetail.timelineTitle')} description={t('traceDetail.timelineHint')} />
      <div className="trace-timeline" role="list">
        {timed.map(({ observation, start, end }) => {
          const offset = start === null ? 0 : ((start - min) / total) * 100
          const duration = start === null || end === null ? 2 : Math.max(((Math.max(end, start + 1) - start) / total) * 100, 1.2)
          return (
            <button key={observation.id} type="button" onClick={() => onSelect(observation)} className={`trace-timeline-row ${selectedId === observation.id ? 'is-active' : ''}`} role="listitem">
              <span className="trace-timeline-label"><span className={`trace-dot ${statusClass(observation)}`} />{observation.name || observation.id}</span>
              <span className="trace-timeline-track"><span className={`trace-timeline-bar ${statusClass(observation)}`} style={{ marginLeft: `${offset}%`, width: `${duration}%` }} /></span>
              <span className="font-mono text-xs text-slate-400">{formatObservationDuration(observation)}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function TreeView({ observations, selectedId, onSelect }: ExplorerViewProps) {
  const { t } = useTranslation()
  return <div><ViewHeading title={t('traceDetail.spanTree')} description={t('traceDetail.treeHint')} /><div className="space-y-1">{flattenTree(observations).map(({ observation, depth }) => <TreeNode key={observation.id} observation={observation} depth={depth} active={selectedId === observation.id} onSelect={onSelect} />)}</div></div>
}

function TreeNode({ observation, depth, active, onSelect }: { observation: Observation; depth: number; active: boolean; onSelect: (observation: Observation) => void }) {
  return <button type="button" onClick={() => onSelect(observation)} style={{ marginLeft: `${depth * 18}px`, width: `calc(100% - ${depth * 18}px)` }} className={`trace-tree-node ${active ? 'is-active' : ''}`}><span className={`trace-dot ${statusClass(observation)}`} /><span className="min-w-0 flex-1 truncate">{observation.name || observation.id}</span><span className="text-[10px] text-slate-500">{observation.type}</span><span className="font-mono text-[11px] text-slate-400">{formatObservationDuration(observation)}</span></button>
}

function ObservationDetail({ obs }: { obs: Observation }) {
  const { t } = useTranslation()
  const tokens = (obs.usage?.input_tokens || 0) + (obs.usage?.output_tokens || 0)
  return <div className="space-y-5"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 className="truncate text-lg font-semibold">{obs.name || obs.id}</h2><p className="mt-1 font-mono text-xs text-slate-500">{obs.type} · {obs.id}</p></div><span className={`rounded px-2 py-1 text-xs ${obs.level === 'ERROR' ? 'bg-red-500/15 text-red-300' : 'bg-slate-800 text-slate-300'}`}>{obs.level}</span></div><div className="grid grid-cols-3 gap-2 text-sm"><MiniStat label={t('traceDetail.metaModel')} value={obs.model || t('traceDetail.notAvailable')} /><MiniStat label={t('traceDetail.metaTokens')} value={tokens ? String(tokens) : t('traceDetail.notAvailable')} /><MiniStat label={t('traceDetail.metaCost')} value={formatCost(reportedCost(obs.cost, obs.cost_currency, obs.cost_coverage)) ?? t('traceDetail.notAvailable')} /></div><Block label={t('traceDetail.input')} value={obs.input} /><Block label={t('traceDetail.output')} value={obs.output} />{obs.metadata && <Block label={t('traceDetail.metadata')} value={obs.metadata} />}{obs.status_message && <Block label={t('traceDetail.message')} value={obs.status_message} />}</div>
}

function Block({ label, value }: { label: string; value: unknown }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const empty = value === null || value === undefined || value === ''
  const text = empty ? '' : typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  async function copy() { await navigator.clipboard?.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 1600) }
  return <div><div className="mb-1 flex items-center justify-between gap-3"><div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>{!empty && <button type="button" onClick={copy} className="text-xs text-slate-400 hover:text-orange-200">{copied ? t('traceDetail.copied') : t('traceDetail.copyJson')}</button>}</div>{empty ? <div className="rounded border border-dashed border-slate-800 px-3 py-4 text-xs text-slate-500">{t('traceDetail.noPayload')}</div> : <pre className="max-h-64 overflow-auto rounded border border-slate-800 bg-slate-950 p-3 text-xs whitespace-pre-wrap">{text}</pre>}</div>
}

function ViewHeading({ title, description }: { title: string; description: string }) { return <div className="mb-4"><h2 className="text-sm font-semibold">{title}</h2><p className="mt-1 text-xs text-slate-500">{description}</p></div> }
function MiniStat({ label, value }: { label: string; value: string | number }) { return <div className="rounded bg-slate-950/60 p-2"><div className="text-[10px] uppercase text-slate-500">{label}</div><div className="truncate">{value}</div></div> }
function Meta({ label, value }: { label: string; value: string }) { return <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3"><div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div><div className="mt-0.5 truncate text-sm">{value}</div></div> }

interface ExplorerViewProps { observations: Observation[]; selectedId?: string; onSelect: (observation: Observation) => void }
function getRoots(observations: Observation[]) { const ids = new Set(observations.map((observation) => observation.id)); return observations.filter((observation) => !observation.parent_observation_id || !ids.has(observation.parent_observation_id)) }
function flattenTree(observations: Observation[]) { const children = new Map<string, Observation[]>(); observations.forEach((observation) => { if (observation.parent_observation_id) children.set(observation.parent_observation_id, [...(children.get(observation.parent_observation_id) || []), observation]) }); const rows: Array<{ observation: Observation; depth: number }> = []; const visit = (observation: Observation, depth: number) => { rows.push({ observation, depth }); children.get(observation.id)?.forEach((child) => visit(child, depth + 1)) }; getRoots(observations).forEach((root) => visit(root, 0)); return rows }
function toMillis(value: string | null) { const parsed = value ? new Date(value).getTime() : NaN; return Number.isNaN(parsed) ? null : parsed }
function formatDuration(value: number | null) { return formatLocalizedDuration(value) }
function formatObservationDuration(observation: Observation) { const start = toMillis(observation.start_time); const end = toMillis(observation.end_time); return start === null || end === null ? formatLocalizedDuration(null) : formatLocalizedDuration(Math.max(0, end - start)) }
function formatTime(value: string | null) { return formatLocalizedTime(value) }
function statusClass(observation: Observation) { return observation.level === 'ERROR' ? 'is-error' : observation.type === 'GENERATION' ? 'is-generation' : observation.type === 'TOOL' ? 'is-tool' : 'is-default' }
function truncate(value: string, length: number) { return value.length > length ? `${value.slice(0, length - 1)}…` : value }
