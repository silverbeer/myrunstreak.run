import type { Unit } from '@/types/runs'

const KM_PER_MI = 1.609344

export const distanceLabel = (unit: Unit): string => (unit === 'mi' ? 'mi' : 'km')

export const formatDistance = (km: number, unit: Unit, decimals = 2): string => {
  const value = unit === 'mi' ? km / KM_PER_MI : km
  return value.toFixed(decimals)
}

export const formatDistanceWithUnit = (km: number, unit: Unit, decimals = 2): string =>
  `${formatDistance(km, unit, decimals)} ${distanceLabel(unit)}`

export const formatPace = (minPerKm: number | null | undefined, unit: Unit): string => {
  if (minPerKm === null || minPerKm === undefined || minPerKm <= 0) return '–'
  const minPerUnit = unit === 'mi' ? minPerKm * KM_PER_MI : minPerKm
  const totalSeconds = Math.round(minPerUnit * 60)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')} /${distanceLabel(unit)}`
}

export const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.round(seconds % 60)
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

/**
 * Format a monthly-summary month string (date-only, e.g. "2026-07-01") as a
 * short label like "Jul 26".
 *
 * Parses the year/month straight from the string rather than via `new Date()`.
 * `new Date("2026-07-01")` treats date-only ISO as UTC midnight, and formatting
 * it then renders in the browser's local zone — in any negative-offset zone
 * (e.g. US) that rolls back to the previous day, shifting every label a month
 * early (July's bar labeled "Jun 26"). String parsing keeps each label on its
 * own month in every timezone.
 */
export const formatMonthLabel = (month: string): string => {
  const [year, monthNum] = month.split('-').map(Number)
  const name = MONTHS[monthNum - 1]
  if (!name || Number.isNaN(year)) return month
  return `${name} ${String(year).slice(-2)}`
}

/**
 * Format a date-only string ('YYYY-MM-DD') as 'Jul 20'. Parses the parts
 * directly rather than via `new Date()`, which treats date-only ISO as UTC
 * midnight and shifts a day in negative-offset zones (same trap as
 * [[format-month-label]] / the SB monthly-distance fix).
 */
export const formatDayMonth = (dateOnly: string): string => {
  const [, month, day] = dateOnly.split('-').map(Number)
  const name = MONTHS[month - 1]
  if (!name || Number.isNaN(day)) return dateOnly
  return `${name} ${day}`
}

export const formatDate = (iso: string): string => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${WEEKDAYS[d.getDay()]} ${MONTHS[d.getMonth()]} ${d.getDate()}`
}

export const formatRelativeTime = (iso: string | null | undefined): string => {
  if (!iso) return 'Never'
  const d = new Date(iso)
  const diffMs = Date.now() - d.getTime()
  if (diffMs < 0) return 'Just now'
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDays = Math.floor(diffHr / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(iso)
}
