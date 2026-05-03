import { describe, it, expect } from 'vitest'
import { buildHeatmapGrid } from '../heatmap'

const FIXED_TODAY = new Date('2026-05-03T12:00:00Z') // Sunday

describe('buildHeatmapGrid', () => {
  it('produces 12 weeks × 7 days by default', () => {
    const grid = buildHeatmapGrid([], 12, FIXED_TODAY)
    expect(grid.length).toBe(12)
    grid.forEach((week) => expect(week.length).toBe(7))
  })

  it('respects a custom number of weeks', () => {
    expect(buildHeatmapGrid([], 4, FIXED_TODAY).length).toBe(4)
  })

  it('ends the grid on the upcoming Saturday so today is included', () => {
    const grid = buildHeatmapGrid([], 12, FIXED_TODAY)
    const lastWeek = grid[grid.length - 1]
    expect(lastWeek[6].iso).toBe('2026-05-09')
  })

  it('marks future days as inFuture', () => {
    const grid = buildHeatmapGrid([], 12, FIXED_TODAY)
    const lastWeek = grid[grid.length - 1]
    expect(lastWeek[0].inFuture).toBe(false)
    expect(lastWeek[6].inFuture).toBe(true)
  })

  it('places a run on the correct day', () => {
    const grid = buildHeatmapGrid(
      [{ date: '2026-05-01T07:00:00Z', distance_km: 8.0 }],
      12,
      FIXED_TODAY,
    )
    const flat = grid.flat()
    const may1 = flat.find((c) => c.iso === '2026-05-01')
    expect(may1?.distanceKm).toBe(8)
    expect(may1?.bucket).toBe(2)
  })

  it('aggregates two runs on the same day', () => {
    const grid = buildHeatmapGrid(
      [
        { date: '2026-05-01T07:00:00Z', distance_km: 4 },
        { date: '2026-05-01T18:00:00Z', distance_km: 4 },
      ],
      12,
      FIXED_TODAY,
    )
    const may1 = grid.flat().find((c) => c.iso === '2026-05-01')
    expect(may1?.distanceKm).toBe(8)
  })

  it('assigns buckets by distance', () => {
    const cases: [number, number][] = [
      [0, 0],
      [3, 1],
      [7, 2],
      [13, 3],
      [21, 4],
    ]
    for (const [km, bucket] of cases) {
      const grid = buildHeatmapGrid(
        [{ date: '2026-05-01T07:00:00Z', distance_km: km }],
        12,
        FIXED_TODAY,
      )
      const cell = grid.flat().find((c) => c.iso === '2026-05-01')
      expect(cell?.bucket).toBe(bucket)
    }
  })

  it('ignores runs outside the visible window', () => {
    const grid = buildHeatmapGrid(
      [{ date: '2025-01-01T07:00:00Z', distance_km: 10 }],
      12,
      FIXED_TODAY,
    )
    const populated = grid.flat().filter((c) => c.distanceKm > 0)
    expect(populated.length).toBe(0)
  })
})
