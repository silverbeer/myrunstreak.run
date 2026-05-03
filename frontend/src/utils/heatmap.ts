import type { RecentRun } from '@/types/runs'

export interface HeatmapCell {
  date: string
  iso: string
  distanceKm: number
  bucket: 0 | 1 | 2 | 3 | 4
  inFuture: boolean
}

export type HeatmapGrid = HeatmapCell[][]

const DAY_MS = 86_400_000

const startOfDayUtc = (d: Date): Date =>
  new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))

const isoDateOnly = (d: Date): string => d.toISOString().slice(0, 10)

const bucketFor = (km: number): HeatmapCell['bucket'] => {
  if (km <= 0) return 0
  if (km < 5) return 1
  if (km < 10) return 2
  if (km < 16) return 3
  return 4
}

export const buildHeatmapGrid = (
  runs: Pick<RecentRun, 'date' | 'distance_km'>[],
  weeks = 12,
  today: Date = new Date(),
): HeatmapGrid => {
  const distanceByDay = new Map<string, number>()
  for (const run of runs) {
    const day = isoDateOnly(startOfDayUtc(new Date(run.date)))
    distanceByDay.set(day, (distanceByDay.get(day) ?? 0) + run.distance_km)
  }

  const today0 = startOfDayUtc(today)
  const weekday = today0.getUTCDay()
  const lastSaturday = new Date(today0.getTime() + (6 - weekday) * DAY_MS)
  const totalDays = weeks * 7
  const firstDay = new Date(lastSaturday.getTime() - (totalDays - 1) * DAY_MS)

  const grid: HeatmapGrid = []
  for (let w = 0; w < weeks; w++) {
    const week: HeatmapCell[] = []
    for (let d = 0; d < 7; d++) {
      const cellDate = new Date(firstDay.getTime() + (w * 7 + d) * DAY_MS)
      const iso = isoDateOnly(cellDate)
      const km = distanceByDay.get(iso) ?? 0
      week.push({
        date: iso,
        iso,
        distanceKm: km,
        bucket: bucketFor(km),
        inFuture: cellDate.getTime() > today0.getTime(),
      })
    }
    grid.push(week)
  }
  return grid
}
