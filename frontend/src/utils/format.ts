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
