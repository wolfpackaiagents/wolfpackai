import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchPredictions } from '../lib/api'
import type { PredictionRun } from '../lib/types'
import { formatDateTime, formatNumber } from '../i18n/format'

const STATUS_LABELS: Record<string, string> = { running: 'Running', completed: 'Completed', evaluated: 'Evaluated' }
const STATUS_COLORS: Record<string, string> = { running: 'text-yellow-400 border-yellow-600/40', completed: 'text-lime-400 border-lime-600/40', evaluated: 'text-sky-400 border-sky-600/40' }

export default function Predictions() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<PredictionRun[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const page = Number(params.get('page') ?? '0')
  const statusFilter = params.get('status') ?? ''

  useEffect(() => {
    let alive = true
    setLoading(true)
    void fetchPredictions({ status: statusFilter || undefined, page, per_page: 20 })
      .then((res) => { if (alive) { setData(res.predictions); setTotal(res.total) } })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [page, statusFilter])

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next)
  }

  return (
    <section className="ops-console">
      <header className="ops-header">
        <div>
          <p>AI Predictions</p>
          <h1>{t('predictions.title')}</h1>
          <span>{t('predictions.subtitle')}</span>
        </div>
        <strong>{formatNumber(total)} predictions</strong>
      </header>

      <div className="ops-filterbar">
        <select value={statusFilter} onChange={(e) => setFilter('status', e.target.value)}
          className="bg-[#1a2e28] border border-[#365047] rounded px-3 py-1.5 text-sm text-[#bcd0c8]">
          <option value="">{t('meta.allStatuses') || 'All statuses'}</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <section className="ops-table">
        {loading ? <div className="p-6 text-[#789087]">{t('meta.loading')}</div>
        : data.length === 0 ? <div className="p-6 text-[#789087]">{t('predictions.empty')}</div>
        : <table>
            <thead>
              <tr>
                <th>{t('predictions.name')}</th>
                <th>{t('predictions.status')}</th>
                <th>{t('predictions.horizon')}</th>
                <th>{t('predictions.agents')}</th>
                <th>{t('predictions.accuracy')}</th>
                <th>{t('predictions.created')}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td><Link to={`/predictions/${p.id}`} className="text-[#c7f36b] underline-offset-2 hover:underline">{p.name}</Link></td>
                  <td><span className={`border rounded px-2 py-0.5 text-xs ${STATUS_COLORS[p.status] || ''}`}>{STATUS_LABELS[p.status] || p.status}</span></td>
                  <td className="text-[#bcd0c8]">{p.horizon_date ? new Date(p.horizon_date).toLocaleDateString(undefined, { timeZone: 'UTC' }) : '-'}</td>
                  <td>{p.agent_count}</td>
                  <td>{p.accuracy_score != null
                    ? `${Math.round(p.accuracy_score * 100)}%`
                    : <span className="text-[#789087] text-xs">{t('predictions.accuracyPendingShort')}</span>}</td>
                  <td className="text-[#789087] text-sm">{formatDateTime(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>}
      </section>

      {total > 20 && (
        <div className="flex gap-2 p-4 justify-center">
          <button disabled={page === 0} onClick={() => setFilter('page', String(page - 1))}
            className="px-3 py-1 bg-[#1a2e28] border border-[#365047] rounded text-sm disabled:opacity-40">Previous</button>
          <span className="px-3 py-1 text-sm text-[#789087]">Page {page + 1}</span>
          <button disabled={data.length < 20} onClick={() => setFilter('page', String(page + 1))}
            className="px-3 py-1 bg-[#1a2e28] border border-[#365047] rounded text-sm disabled:opacity-40">Next</button>
        </div>
      )}
    </section>
  )
}
