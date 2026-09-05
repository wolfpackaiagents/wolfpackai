import i18n from './index'

function locale() {
  return i18n.resolvedLanguage || i18n.language || 'en'
}

export function formatDateTime(value: Date | string | null | undefined): string {
  if (!value) return i18n.t('meta.notAvailable')
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? i18n.t('meta.notAvailable') : new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function formatTime(value: Date | string | null | undefined): string {
  if (!value) return i18n.t('meta.notAvailable')
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? i18n.t('meta.notAvailable') : new Intl.DateTimeFormat(locale(), { timeStyle: 'short' }).format(date)
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(locale()).format(value)
}

export function formatDuration(milliseconds: number | null | undefined): string {
  if (milliseconds === null || milliseconds === undefined) return i18n.t('meta.notAvailable')
  if (milliseconds < 1_000) return i18n.t('format.milliseconds', { value: Math.round(milliseconds) })
  return i18n.t('format.seconds', { value: new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 }).format(milliseconds / 1_000) })
}
