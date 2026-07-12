import { describe, it, expect } from 'vitest'
import { parseRunQuery } from '../runQuery'

// Fixed "today" so season/year math is deterministic: July 12, 2026.
const TODAY = new Date(Date.UTC(2026, 6, 12))

const parse = (q: string, unit: 'mi' | 'km' = 'mi') => parseRunQuery(q, unit, TODAY)

describe('parseRunQuery (SB-269 natural-language search)', () => {
  it('the flagship: "rainy 5 milers last summer"', () => {
    const { filters, chips, ignored } = parse('rainy 5 milers last summer')
    expect(filters.weather_type).toBe('rainy')
    // ~5 miles -> 8.05km ± 0.5
    expect(filters.distance_min).toBeCloseTo(7.55, 1)
    expect(filters.distance_max).toBeCloseTo(8.55, 1)
    // last summer (said in July 2026, summer already started) -> summer 2025
    expect(filters.date_from).toBe('2025-06-01')
    expect(filters.date_to).toBe('2025-08-31')
    expect(chips).toContain('rainy')
    expect(ignored).toEqual([])
  })

  it('pace: "hot runs under 9:30" converts min/mi to min/km', () => {
    const { filters, chips } = parse('hot runs under 9:30')
    expect(filters.temp_min).toBe(24)
    expect(filters.pace_max).toBeCloseTo(9.5 / 1.609344, 3)
    expect(chips).toContain('pace under 9:30/mi')
  })

  it('pace in km mode stays min/km', () => {
    const { filters } = parse('under 5:30', 'km')
    expect(filters.pace_max).toBeCloseTo(5.5, 3)
  })

  it('"faster than 9:00" and "slower than 10:00"', () => {
    expect(parse('faster than 9:00').filters.pace_max).toBeCloseTo(9 / 1.609344, 3)
    expect(parse('slower than 10:00').filters.pace_min).toBeCloseTo(10 / 1.609344, 3)
  })

  it('distances: "10k" and "3 miles"', () => {
    const k = parse('10k').filters
    expect(k.distance_min).toBeCloseTo(9.5, 1)
    expect(k.distance_max).toBeCloseTo(10.5, 1)
    const mi = parse('3 miles').filters
    expect(mi.distance_min).toBeCloseTo(3 * 1.609344 - 0.5, 1)
  })

  it('long/short shorthands are unit-aware', () => {
    expect(parse('long runs').filters.distance_min).toBeCloseTo(5 * 1.609344, 2)
    expect(parse('short runs', 'km').filters.distance_max).toBe(3)
  })

  it('month names: past month uses this year, future month rolls back', () => {
    const may = parse('may').filters // May 2026 already happened by Jul 12
    expect(may.date_from).toBe('2026-05-01')
    const dec = parse('december').filters // December 2026 hasn't -> 2025
    expect(dec.date_from).toBe('2025-12-01')
    expect(dec.date_to).toBe('2025-12-31')
  })

  it('month with explicit year', () => {
    const { filters } = parse('january 2023')
    expect(filters.date_from).toBe('2023-01-01')
    expect(filters.date_to).toBe('2023-01-31')
  })

  it('bare year', () => {
    const { filters } = parse('2019')
    expect(filters.date_from).toBe('2019-01-01')
    expect(filters.date_to).toBe('2019-12-31')
  })

  it('winter spans the year boundary', () => {
    const { filters } = parse('last winter')
    expect(filters.date_from).toBe('2025-12-01')
    expect(filters.date_to).toBe('2026-02-28')
  })

  it('sort words: "fastest long runs"', () => {
    const { filters } = parse('fastest long runs')
    expect(filters.sort).toBe('pace')
    expect(filters.order).toBe('asc')
    expect(filters.distance_min).toBeCloseTo(8.05, 1)
  })

  it('unknown tokens are surfaced, stopwords are not', () => {
    const { ignored } = parse('show me sparkly runs')
    expect(ignored).toEqual(['sparkly'])
  })

  it('empty query parses to nothing', () => {
    const { filters, chips, ignored } = parse('')
    expect(filters).toEqual({})
    expect(chips).toEqual([])
    expect(ignored).toEqual([])
  })
})

describe('time of day (SB-270)', () => {
  it('"early morning runs" — early wins the tighter bound', () => {
    const { filters } = parse('early morning runs')
    // "early" sets hour_max 6, then "morning" widens to 9 (last wins) — both
    // chips show, so the translation is visible either way.
    expect(filters.hour_max).toBe(9)
  })

  it('"morning runs" and "evening runs in july"', () => {
    expect(parse('morning runs').filters.hour_max).toBe(9)
    const evening = parse('evening runs in july').filters
    expect(evening.hour_min).toBe(16)
    expect(evening.date_from).toBe('2026-07-01')
  })

  it('"early runs" flags the early-bird band', () => {
    expect(parse('early runs').filters.hour_max).toBe(6)
  })
})
