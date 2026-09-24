import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, Link } from 'react-router-dom'
import { fetchPrediction, fetchPredictionInteractions, fetchPredictionScores, fetchPredictionSimulation, fetchPredictionSummary } from '../lib/api'
import type { PredictionRun, PredictionInteractionGraph, PredictionSimulation, PredictionSummary } from '../lib/types'
import { formatDateTime } from '../i18n/format'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, PieChart, Pie, Cell } from 'recharts'

type Tab = 'overview' | 'agents' | 'graph' | 'interactions' | 'rounds' | 'timeline' | 'report' | 'scores'

const STATUS_BADGE: Record<string, string> = {
  running: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  completed: 'bg-primary-tint text-primary border-primary-tint-strong',
  evaluated: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
}

const STANCE_BADGE: Record<string, string> = {
  concorda: 'bg-primary-tint text-primary border-primary-tint-strong',
  discorda: 'bg-red-500/15 text-red-300 border-red-500/30',
  parcial: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
}

function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*.*?\*\*)/).filter(Boolean)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('**') && part.endsWith('**')
          ? <strong key={i} className="text-primary font-semibold">{part.slice(2, -2)}</strong>
          : <span key={i}>{part}</span>,
      )}
    </>
  )
}

function Markdown({ source }: { source: string }) {
  const blocks: JSX.Element[] = []
  let bullets: string[] = []

  const flushBullets = () => {
    if (!bullets.length) return
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="list-disc ml-5 mb-3 space-y-1">
        {bullets.map((item, i) => (
          <li key={i} className="text-text-secondary text-sm leading-relaxed"><InlineMarkdown text={item} /></li>
        ))}
      </ul>,
    )
    bullets = []
  }

  source.split('\n').forEach((raw, index) => {
    const line = raw.trimEnd()
    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      flushBullets()
      const level = heading[1].length
      const text = heading[2]
      const styles = [
        'text-text text-xl font-bold mt-6 mb-3',
        'text-primary text-lg font-semibold mt-6 mb-3',
        'text-text-secondary text-base font-semibold mt-5 mb-2',
        'text-text-secondary text-sm font-semibold mt-4 mb-2',
      ]
      blocks.push(
        <p key={`h-${index}`} className={styles[Math.min(level, styles.length) - 1]}>
          <InlineMarkdown text={text} />
        </p>,
      )
      return
    }
    if (/^[-*]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*]\s+/, ''))
      return
    }
    flushBullets()
    if (line.trim()) {
      blocks.push(
        <p key={`p-${index}`} className="text-text-secondary text-sm mb-2 leading-relaxed">
          <InlineMarkdown text={line} />
        </p>,
      )
    }
  })
  flushBullets()
  return <div>{blocks}</div>
}

function KvTable({ data }: { data: Record<string, unknown> }) {
  return (
    <table className="w-full">
      <tbody>
        {Object.entries(data).map(([key, val]) => (
          <tr key={key} className="border-t border-line">
            <td className="p-2 text-text-secondary text-xs font-medium uppercase tracking-wider w-1/3 align-top">{key.replace(/_/g, ' ')}</td>
            <td className="p-2 text-text text-sm">{typeof val === 'string' ? val : JSON.stringify(val)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function PredictionBody({ value }: { value: unknown }) {
  if (value == null) return null
  if (typeof value === 'string') return <Markdown source={value} />
  if (typeof value === 'object' && Object.keys(value as object).length > 0) {
    return <KvTable data={value as Record<string, unknown>} />
  }
  return null
}

const PT_GRAPH_LABELS: Record<string, string> = {
  Candidate: 'Candidato', 'Former President': 'Ex-presidente', 'Polling Agency': 'Instituto de pesquisa',
  'Judicial Body': 'Órgão judicial', Adversarial: 'Adversários', 'Running Mate': 'Chapa',
  Support: 'Apoio', 'Polling Result': 'Pesquisa', influences: 'influencia', actor: 'agente',
}

function SocialGraph({ simulation }: { simulation: PredictionSimulation }) {
  const { t, i18n } = useTranslation()
  const width = 920
  const height = 540
  const actors = simulation.entities.filter((entity) => entity.entity_type === 'actor')
  const contextEntities = simulation.entities.filter((entity) => entity.entity_type !== 'actor')
  const actorIds = new Set(actors.map((entity) => entity.id))
  const contextColumns = Math.max(1, Math.min(3, Math.ceil(Math.sqrt(contextEntities.length))))
  const positions = new Map<string, { x: number, y: number }>()
  actors.forEach((entity, index) => positions.set(entity.id, {
    x: 155,
    y: 100 + index * Math.min(125, 360 / Math.max(actors.length - 1, 1)),
  }))
  contextEntities.forEach((entity, index) => positions.set(entity.id, {
    x: 415 + (index % contextColumns) * 190,
    y: 90 + Math.floor(index / contextColumns) * 125,
  }))
  const displayLabel = (label: string) => i18n.language.startsWith('pt') ? (PT_GRAPH_LABELS[label] ?? label) : label
  const entityById = new Map(simulation.entities.map((entity) => [entity.id, entity]))
  const evidenceRelations = simulation.relationships.filter((relationship) =>
    !actorIds.has(relationship.source_entity_id) || !actorIds.has(relationship.target_entity_id),
  )

  return (
    <div className="bg-surface border border-line rounded-lg overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 p-4 border-b border-line">
        <div>
          <h3 className="text-sm font-semibold text-text">{t('predictions.socialGraph')}</h3>
          <p className="text-xs text-text-secondary mt-1">{t('predictions.socialGraphDescription')}</p>
        </div>
        <span className="text-xs text-primary">{t('predictions.graphStats', { nodes: simulation.entities.length, relationships: simulation.relationships.length })}</span>
      </div>
       <div className="p-2 overflow-x-auto">
         <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[620px] h-auto" role="img" aria-label="Grafo social da simulação">
          <defs>
            <marker id="social-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-primary)" />
            </marker>
          </defs>
           <text x="155" y="34" textAnchor="middle" fill="var(--color-primary)" fontSize="12" fontWeight="600">{t('predictions.agents')}</text>
           <text x="650" y="34" textAnchor="middle" fill="#ffb74d" fontSize="12" fontWeight="600">{t('predictions.graphContext')}</text>
           <line x1="310" y1="52" x2="310" y2="510" stroke="var(--color-line)" strokeDasharray="5 8" />
           {simulation.relationships.map((relationship) => {
             const source = positions.get(relationship.source_entity_id)
             const target = positions.get(relationship.target_entity_id)
             if (!source || !target) return null
             const strength = typeof relationship.attributes.strength === 'number' ? relationship.attributes.strength : 0.5
             const isActorLink = actorIds.has(relationship.source_entity_id) && actorIds.has(relationship.target_entity_id)
             const labelX = (source.x + target.x) / 2
             const labelY = (source.y + target.y) / 2 - 7
             return (
               <g key={relationship.id}>
                 <line x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                   stroke={isActorLink ? 'var(--color-primary)' : '#d6a45c'} strokeWidth={1 + strength * 2} opacity={0.45 + strength * 0.4} markerEnd="url(#social-arrow)">
                   <title>{displayLabel(relationship.relationship_type)} · {Math.round(strength * 100)}%</title>
                 </line>
                 {!isActorLink && <text x={labelX} y={labelY} textAnchor="middle" fill="#d6a45c" fontSize="9">{displayLabel(relationship.relationship_type)}</text>}
               </g>
             )
           })}
          {simulation.entities.map((entity) => {
            const point = positions.get(entity.id)!
            const isActor = entity.entity_type === 'actor'
            return (
              <g key={entity.id} transform={`translate(${point.x} ${point.y})`}>
                <circle r="39" fill={isActor ? '#e8f0fe' : '#fff7e6'} stroke={isActor ? 'var(--color-primary)' : '#ffb74d'} strokeWidth="2" />
                <text y="-3" textAnchor="middle" fill="var(--color-text)" fontSize="11" fontWeight="600">{entity.name.length > 17 ? `${entity.name.slice(0, 16)}…` : entity.name}</text>
                <text y="14" textAnchor="middle" fill={isActor ? 'var(--color-text-secondary)' : '#d6a45c'} fontSize="8">{displayLabel(entity.entity_type)}</text>
                <title>{entity.name}</title>
              </g>
            )
          })}
         </svg>
       </div>
       {evidenceRelations.length > 0 && (
         <div className="border-t border-line p-4">
           <p className="text-xs font-semibold uppercase tracking-wider text-[#d6a45c] mb-3">{t('predictions.graphEvidence')}</p>
           <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
             {evidenceRelations.map((relationship) => {
               const evidence = typeof relationship.attributes.evidence === 'string' ? relationship.attributes.evidence : null
               return <div key={relationship.id} className="rounded border border-line bg-surface-alt p-3">
                 <p className="text-xs text-text">{entityById.get(relationship.source_entity_id)?.name} <span className="text-[#d6a45c]">{displayLabel(relationship.relationship_type)}</span> {entityById.get(relationship.target_entity_id)?.name}</p>
                 <p className="mt-1 text-xs text-text-secondary">{evidence ? `“${evidence}”` : t('predictions.graphEvidenceUnavailable')}</p>
               </div>
             })}
           </div>
         </div>
       )}
     </div>
  )
}

export default function PredictionDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const [prediction, setPrediction] = useState<PredictionRun | null>(null)
  const [summary, setSummary] = useState<PredictionSummary | null>(null)
  const [graph, setGraph] = useState<PredictionInteractionGraph | null>(null)
  const [simulation, setSimulation] = useState<PredictionSimulation | null>(null)
  const [scores, setScores] = useState<{ name: string; value: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('overview')

  useEffect(() => {
    if (!id) return
    let alive = true
    setLoading(true)
    void Promise.all([
      fetchPrediction(id),
      fetchPredictionSummary(id).catch(() => null),
      fetchPredictionInteractions(id).catch(() => null),
      fetchPredictionScores(id).catch(() => null),
      fetchPredictionSimulation(id).catch(() => null),
    ])
      .then(([pred, summ, gr, sc, sim]) => {
        if (!alive) return
        setPrediction(pred)
        setSummary(summ)
        setGraph(gr)
        setSimulation(sim)
        setScores((sc?.scores ?? []).map((s) => ({ name: s.name, value: s.value ?? 0 })))
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [id])

  if (loading) return <div className="p-6 text-text-secondary">{t('meta.loading')}</div>
  if (!prediction) return <div className="p-6 text-primary">{t('meta.error')}</div>

  const nodeMap: Record<string, string> = {}
  graph?.nodes.forEach((n) => { nodeMap[n.id] = n.label })
  simulation?.entities.forEach((entity) => { nodeMap[entity.id] = entity.name })
  const roundById = new Map(simulation?.rounds.map((round) => [round.id, round.number]))
  const interactionEdges = simulation
    ? simulation.events
      .filter((event) => event.event_type.startsWith('interaction.'))
      .map((event) => ({
        source: event.entity_id ?? '',
        target: typeof event.payload.target_entity_id === 'string' ? event.payload.target_entity_id : '',
        type: typeof event.payload.stance === 'string' ? event.payload.stance : event.event_type,
        content: typeof event.payload.content === 'string' ? event.payload.content : '',
        round: roundById.get(event.round_id ?? '') ?? 0,
      }))
    : graph?.edges ?? []
  const rounds = prediction.report?.rounds ?? []
  const synthesis = prediction.report?.synthesis ?? ''

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: t('predictions.overview') },
    { key: 'agents', label: `${t('predictions.agents')} (${prediction.agent_count})` },
    ...(simulation ? [{ key: 'graph' as Tab, label: `${t('predictions.socialGraph')} (${simulation.relationships.length})` }] : []),
    { key: 'interactions', label: `${t('predictions.interactions')} (${interactionEdges.length})` },
    { key: 'rounds', label: `${t('predictions.rounds')} (${rounds.length})` },
    ...(simulation ? [{ key: 'timeline' as Tab, label: `${t('predictions.timeline')} (${simulation.events.length})` }] : []),
    { key: 'report', label: t('predictions.report') },
    { key: 'scores', label: `${t('predictions.scores')} (${scores.length})` },
  ]

  const confidenceData = prediction.agents.map((a) => ({ name: a.persona_name, value: (a.confidence ?? 0.5) * 100 }))
  const colors = [/* #c7f36b */ '#4ade80', '#60a5fa', '#fbbf24', '#a78bfa', '#fb923c']

  return (
    <section className="ops-console">
      <header className="ops-header">
        <div>
          <p><Link to="/predictions" className="text-text-secondary hover:text-text">{t('predictions.title')}</Link></p>
          <h1 className="text-text">{prediction.name}</h1>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
            <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_BADGE[prediction.status] ?? 'border-line text-text-secondary'}`}>
              {t(`predictions.statuses.${prediction.status}`, { defaultValue: prediction.status })}
            </span>
            {prediction.horizon_date && (
               <span className="text-xs text-text-secondary">{t('predictions.horizon')}: {new Date(prediction.horizon_date).toLocaleDateString(undefined, { timeZone: 'UTC' })}</span>
            )}
            {prediction.accuracy_score != null && (
              <span className="text-xs text-primary">{t('predictions.accuracy')}: {Math.round(prediction.accuracy_score * 100)}%</span>
            )}
            {prediction.accuracy_score == null && (
              <span className="text-xs text-text-secondary">{t('predictions.accuracyPending')}</span>
            )}
            <span className="text-xs text-text-secondary">{formatDateTime(prediction.created_at)}</span>
            <span className="text-xs text-text-secondary">{t('predictions.agentCount', { count: prediction.agent_count })}</span>
            <span className="text-xs text-text-secondary">{t('predictions.interactionCount', { count: interactionEdges.length })}</span>
          </div>
        </div>
      </header>

      <div className="flex gap-1 px-6 py-2 border-b border-line overflow-x-auto">
        {tabs.map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={`px-3 py-1.5 text-sm rounded-t whitespace-nowrap transition-colors ${tab === item.key ? 'bg-surface text-primary border border-b-0 border-line font-medium' : 'text-text-secondary hover:text-text'}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="p-6">
        {tab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-4">
              {prediction.seed_summary && (
                <div className="bg-surface border border-line rounded-lg p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2">{t('predictions.seedMaterial')}</h3>
                  <Markdown source={prediction.seed_summary} />
                </div>
              )}
              {prediction.scenario_params && Object.keys(prediction.scenario_params).length > 0 && (
                <div className="bg-surface border border-line rounded-lg p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2">{t('predictions.scenarioParameters')}</h3>
                  <KvTable data={prediction.scenario_params as Record<string, unknown>} />
                </div>
              )}
            </div>
            <div className="space-y-4">
              {prediction.agents.length > 0 && (
                <div className="bg-surface border border-line rounded-lg p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2">{t('predictions.agentConfidence')}</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie data={confidenceData} dataKey="value" cx="50%" cy="50%" outerRadius={70}
                        label={({ name, value }: { name: string; value: number }) => `${name} ${value.toFixed(0)}%`}>
                        {confidenceData.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-line)', borderRadius: '8px', color: 'var(--color-text)' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="bg-surface border border-line rounded-lg p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2">{t('predictions.convergenceAnalysis')}</h3>
                {summary && summary.convergences.length > 0 ? (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={summary.convergences.map((c) => ({ name: c.agents.join(' × '), rate: c.rate * 100 }))}>
                      <CartesianGrid stroke="var(--color-line)" vertical={false} />
                      <XAxis dataKey="name" stroke="var(--color-text-secondary)" fontSize={10} angle={-20} textAnchor="end" height={60} />
                      <YAxis domain={[0, 100]} stroke="var(--color-text-secondary)" fontSize={10} tickFormatter={(v: number) => `${v}%`} />
                      <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-line)', borderRadius: '8px', color: 'var(--color-text)' }} formatter={(v: number) => `${v.toFixed(0)}%`} />
                      <Bar dataKey="rate" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-text-secondary text-sm py-2">{t('predictions.noConvergence')}</p>
                )}
              </div>
              {prediction.report?.auto_generated_personas && (
                <p className="text-xs text-text-secondary italic">{t('predictions.autoPersonas')}</p>
              )}
            </div>
          </div>
        )}

        {tab === 'agents' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {prediction.agents.map((agent) => {
              const profile = (agent.persona_profile ?? {}) as Record<string, string>
              const revisions = simulation?.revisions.filter((revision) => revision.entity_id === agent.entity_id) ?? []
              const latestRevision = revisions[revisions.length - 1]
              return (
                <div key={agent.id} className="bg-surface border border-line rounded-lg overflow-hidden">
                  <div className="flex items-start justify-between p-4 border-b border-line">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-white font-bold text-sm">
                        {agent.persona_name.charAt(0)}
                      </div>
                      <div>
                        <h3 className="font-semibold text-text">{agent.persona_name}</h3>
                        <p className="text-xs text-text-secondary">{profile.role}{profile.bias ? ` · ${profile.bias}` : ''}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-1">
                        <div className="w-16 h-1.5 bg-surface-alt rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-primary to-primary/70 rounded-full" style={{ width: `${(agent.confidence ?? 0.5) * 100}%` }} />
                        </div>
                        <span className="text-primary text-xs font-medium">{agent.confidence != null ? `${Math.round(agent.confidence * 100)}%` : '-'}</span>
                      </div>
                      <div className={`text-xs mt-0.5 inline-block px-1.5 py-0.5 rounded border ${STATUS_BADGE[agent.status] ?? ''}`}>
                        {t(`predictions.statuses.${agent.status}`, { defaultValue: agent.status })}
                      </div>
                    </div>
                  </div>
                  <div className="p-3">
                    <p className="text-xs text-text-secondary mb-1 uppercase tracking-wider">{t('predictions.prediction')}</p>
                    <PredictionBody value={agent.prediction} />
                  </div>
                  {latestRevision && (
                    <div className="mx-3 mb-3 p-2 bg-surface-alt border border-line rounded">
                      <p className="text-xs text-text-secondary">{t('predictions.revision', { number: latestRevision.revision })}</p>
                      <p className="text-xs text-text-secondary mt-1">{t('predictions.revisionCount', { count: revisions.length })}</p>
                    </div>
                  )}
                  {agent.trace_id && (
                    <div className="px-4 pb-3">
                      <Link to={`/traces/${agent.trace_id}`} className="text-xs text-primary hover:underline">{t('predictions.viewTrace')} →</Link>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {tab === 'graph' && simulation && <SocialGraph simulation={simulation} />}

        {tab === 'interactions' && (
          interactionEdges.length ? (
            <div className="space-y-6">
              {[...new Set(interactionEdges.map((e) => e.round))].sort().map((round) => (
                <div key={round}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center text-white text-xs font-bold">{round}</div>
                    <h3 className="text-sm font-medium text-text">{t('predictions.round', { number: round })}</h3>
                  </div>
                  <div className="space-y-2 ml-8 border-l-2 border-line pl-4">
                    {interactionEdges.filter((e) => e.round === round).map((edge, i) => (
                      <div key={i} className="relative">
                        <div className="absolute -left-[19px] top-4 w-3 h-3 rounded-full bg-surface-alt border-2 border-primary" />
                        <div className="bg-surface border border-line rounded-lg p-3">
                          <div className="flex items-center gap-2 text-sm flex-wrap">
                            <span className="font-medium text-primary">{nodeMap[edge.source] ?? edge.source}</span>
                            <span className="text-text-secondary">→</span>
                            <span className="font-medium text-primary">{nodeMap[edge.target] ?? edge.target}</span>
                            {edge.type && (
                              <span className={`text-[11px] px-1.5 py-0.5 rounded border ${STANCE_BADGE[edge.type] ?? 'border-line text-text-secondary'}`}>{edge.type}</span>
                            )}
                          </div>
                          <p className="text-text-secondary text-sm mt-1">{edge.content}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-text-secondary text-sm p-4">{t('predictions.noInteractions')}</p>
          )
        )}

        {tab === 'rounds' && (
          rounds.length ? (
            <div className="space-y-6">
              {rounds.map((round) => (
                <div key={round.round} className="bg-surface border border-line rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-primary mb-3">{t('predictions.round', { number: round.round })}</h3>
                  <div className="space-y-2 mb-4">
                    {(round.interactions ?? []).map((item, i) => (
                      <div key={i} className="border-l-2 border-line pl-3">
                        <div className="flex items-center gap-2 text-sm flex-wrap">
                          <span className="text-primary">{item.source}</span>
                          <span className="text-text-secondary">→</span>
                          <span className="text-primary">{item.target}</span>
                          <span className={`text-[11px] px-1.5 py-0.5 rounded border ${STANCE_BADGE[item.stance] ?? 'border-line text-text-secondary'}`}>{item.stance}</span>
                        </div>
                        <p className="text-text-secondary text-sm">{item.content}</p>
                      </div>
                    ))}
                  </div>
                  {(round.revisions ?? []).length > 0 && (
                    <div>
                      <p className="text-xs uppercase tracking-wider text-text-secondary mb-2">{t('predictions.revisions')}</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {(round.revisions ?? []).map((rev, i) => (
                          <div key={i} className="bg-surface-alt border border-line rounded p-2">
                            <p className="text-xs text-primary mb-1">{rev.persona_name}</p>
                            <PredictionBody value={rev.prediction} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-text-secondary text-sm p-4">{t('predictions.noInteractions')}</p>
          )
        )}

        {tab === 'timeline' && (
          simulation && simulation.events.length ? (
            <div className="max-w-4xl space-y-3">
              {simulation.events.map((event) => {
                const actor = simulation.entities.find((entity) => entity.id === event.entity_id)
                const targetId = typeof event.payload.target_entity_id === 'string' ? event.payload.target_entity_id : null
                const target = simulation.entities.find((entity) => entity.id === targetId)
                const traceId = prediction.agents.find((agent) => agent.id === event.agent_run_id)?.trace_id
                const isSimulated = event.event_type === 'scenario.injected'
                return (
                  <article key={event.id} className="bg-surface border border-line rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs text-text-secondary">
                      <span className="text-primary font-semibold">#{event.sequence}</span>
                      <span>{event.event_type}</span>
                      {actor && <span>{actor.name}{target ? ` → ${target.name}` : ''}</span>}
                      {isSimulated && <span className="px-1.5 py-0.5 rounded border border-amber-500/30 text-amber-300">{t('predictions.simulatedEvent')}</span>}
                      <span className="ml-auto">{formatDateTime(event.created_at)}</span>
                    </div>
                    {typeof event.payload.content === 'string' && <p className="text-text-secondary text-sm mt-2">{event.payload.content}</p>}
                    {typeof event.payload.stance === 'string' && <span className={`inline-block text-[11px] mt-2 px-1.5 py-0.5 rounded border ${STANCE_BADGE[event.payload.stance] ?? 'border-line text-text-secondary'}`}>{event.payload.stance}</span>}
                    {typeof event.payload.impact === 'string' && event.payload.impact && (
                      <p className="text-xs text-text-secondary mt-2 border-l-2 border-primary pl-2"><strong className="text-text">{t('predictions.impact')}:</strong> {event.payload.impact}</p>
                    )}
                    {traceId && <Link to={`/traces/${traceId}`} className="inline-block text-xs text-primary hover:underline mt-2">{t('predictions.viewTrace')} →</Link>}
                  </article>
                )
              })}
            </div>
          ) : (
            <p className="text-text-secondary text-sm p-4">{t('predictions.noInteractions')}</p>
          )
        )}

        {tab === 'report' && (
          <div className="bg-surface border border-line rounded-lg p-6 max-w-3xl">
            <Markdown source={synthesis} />
          </div>
        )}

        {tab === 'scores' && (
          <div className="bg-surface border border-line rounded-lg p-4 max-w-xl">
            {scores.length === 0 ? (
              <div className="text-center py-8 text-text-secondary">
                <p className="text-sm">{t('predictions.noScores')}</p>
                <p className="text-xs mt-1">{t('predictions.noScoresHint')}</p>
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-line">
                    <th className="text-left text-text-secondary text-xs font-semibold uppercase tracking-wider p-2">{t('predictions.metric')}</th>
                    <th className="text-right text-text-secondary text-xs font-semibold uppercase tracking-wider p-2">{t('predictions.value')}</th>
                  </tr>
                </thead>
                <tbody>
                  {scores.map((s, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="p-2 text-text-secondary text-sm">{s.name}</td>
                      <td className="p-2 text-right"><span className="text-primary font-medium">{s.value.toFixed(2)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
