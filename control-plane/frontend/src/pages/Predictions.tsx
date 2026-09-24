import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import ConfirmationDialog from '../components/ConfirmationDialog'
import { fetchPredictions, deletePrediction } from '../lib/api'
import type { PredictionRun } from '../lib/types'
import { formatDateTime, formatNumber } from '../i18n/format'

const STATUS_LABELS: Record<string, string> = { running: 'Running', completed: 'Completed', evaluated: 'Evaluated' }
const STATUS_COLORS: Record<string, string> = { running: 'text-yellow-400 border-yellow-600/40', completed: 'text-primary border-primary', evaluated: 'text-sky-400 border-sky-600/40' }

export default function Predictions() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<PredictionRun[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
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

  async function executeDelete(id: string) {
    setConfirmDeleteId(null)
    setDeleting(id)
    try {
      await deletePrediction(id)
      setData((prev) => prev.filter((p) => p.id !== id))
      setTotal((prev) => prev - 1)
    } finally {
      setDeleting(null)
    }
  }

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
          className="bg-surface border border-line rounded px-3 py-1.5 text-sm text-text">
          <option value="">{t('meta.allStatuses') || 'All statuses'}</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <section className="ops-table">
        {loading ? <div className="p-6 text-text-secondary">{t('meta.loading')}</div>
        : data.length === 0 ? <div className="p-6 text-text-secondary">{t('predictions.empty')}</div>
        : <table>
            <thead>
              <tr>
                <th>{t('predictions.name')}</th>
                <th>{t('predictions.status')}</th>
                <th>{t('predictions.horizon')}</th>
                <th>{t('predictions.agents')}</th>
                <th>{t('predictions.accuracy')}</th>
                <th>{t('predictions.created')}</th>
                <th className="w-16"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td><Link to={`/predictions/${p.id}`} className="text-primary underline-offset-2 hover:underline">{p.name}</Link></td>
                  <td><span className={`border rounded px-2 py-0.5 text-xs ${STATUS_COLORS[p.status] || ''}`}>{STATUS_LABELS[p.status] || p.status}</span></td>
                  <td className="text-text-secondary">{p.horizon_date ? new Date(p.horizon_date).toLocaleDateString(undefined, { timeZone: 'UTC' }) : '-'}</td>
                  <td>{p.agent_count}</td>
                  <td>{p.accuracy_score != null
                    ? `${Math.round(p.accuracy_score * 100)}%`
                    : <span className="text-text-secondary text-xs">{t('predictions.accuracyPendingShort')}</span>}</td>
                  <td className="text-text-secondary text-sm">{formatDateTime(p.created_at)}</td>
                  <td>
                    <button onClick={() => setConfirmDeleteId(p.id)} disabled={deleting === p.id}
                      className="text-xs text-error hover:opacity-80 transition-opacity disabled:opacity-30">
                      {deleting === p.id ? '...' : t('predictions.delete')}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>}
      </section>

      {total > 20 && (
        <div className="flex gap-2 p-4 justify-center">
          <button disabled={page === 0} onClick={() => setFilter('page', String(page - 1))}
            className="px-3 py-1 bg-surface border border-line rounded text-sm text-text hover:bg-surface-hover disabled:opacity-40">{t('meta.previous') || 'Previous'}</button>
          <span className="px-3 py-1 text-sm text-text-secondary">{t('meta.page', { page: page + 1 }) || `Page ${page + 1}`}</span>
          <button disabled={data.length < 20} onClick={() => setFilter('page', String(page + 1))}
            className="px-3 py-1 bg-surface border border-line rounded text-sm text-text hover:bg-surface-hover disabled:opacity-40">{t('meta.next') || 'Next'}</button>
        </div>
      )}

      {confirmDeleteId && (
        <ConfirmationDialog
          title={t('predictions.deleteConfirmTitle') || t('predictions.delete')}
          description={t('predictions.deleteConfirm')}
          cancelLabel={t('meta.cancel')}
          confirmLabel={t('predictions.delete')}
          onCancel={() => setConfirmDeleteId(null)}
          onConfirm={() => void executeDelete(confirmDeleteId)}
        />
      )}
    </section>
  )
}
