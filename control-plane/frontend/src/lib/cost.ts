import { formatNumber } from '../i18n/format'

export type CostCoverage = { reported: number; total: number }
export type ReportedCost = { amount: number; currency: string; coverage: CostCoverage | null }
type CostPayload = { amount?: unknown; total?: unknown; total_cost?: unknown; value?: unknown; currency?: unknown; coverage?: unknown; cost_coverage?: unknown }

function finite(value: unknown): number | null { return typeof value === 'number' && Number.isFinite(value) ? value : null }

export function costCoverage(value: unknown): CostCoverage | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const source = value as Record<string, unknown>
  const reported = finite(source.reported ?? source.reported_count ?? source.with_cost)
  const total = finite(source.total ?? source.total_count ?? source.observations)
  return reported !== null && total !== null && reported >= 0 && total >= 0 ? { reported, total } : null
}

export function reportedCost(value: unknown, currency?: unknown, coverage?: unknown): ReportedCost | null {
  const source = value && typeof value === 'object' && !Array.isArray(value) ? value as CostPayload : null
  const amount = finite(source?.amount ?? source?.total ?? source?.total_cost ?? source?.value ?? value)
  const code = typeof (source?.currency ?? currency) === 'string' ? String(source?.currency ?? currency).toUpperCase() : ''
  if (amount === null || !/^[A-Z]{3}$/.test(code)) return null
  return { amount, currency: code, coverage: costCoverage(source?.coverage ?? source?.cost_coverage ?? coverage) }
}

export function combineReportedCosts(costs: Array<ReportedCost | null>): ReportedCost | null {
  const known = costs.filter((cost): cost is ReportedCost => cost !== null)
  if (!known.length || new Set(known.map((cost) => cost.currency)).size !== 1) return null
  const coverage = known.every((cost) => cost.coverage)
    ? known.reduce<CostCoverage>((sum, cost) => ({ reported: sum.reported + cost.coverage!.reported, total: sum.total + cost.coverage!.total }), { reported: 0, total: 0 })
    : null
  return { amount: known.reduce((sum, cost) => sum + cost.amount, 0), currency: known[0].currency, coverage }
}

export function formatCost(cost: ReportedCost | null): string | null {
  if (!cost) return null
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency: cost.currency, maximumFractionDigits: 4 }).format(cost.amount) } catch { return null }
}

export function formatCostCoverage(coverage: CostCoverage | null): string | null {
  if (!coverage) return null
  if (coverage.total === 0) return '0 / 0'
  return `${formatNumber(coverage.reported)} / ${formatNumber(coverage.total)} (${new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 0 }).format(coverage.reported / coverage.total)})`
}
