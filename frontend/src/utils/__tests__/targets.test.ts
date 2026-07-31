import { describe, it, expect } from 'vitest'
import { fmtRange, hrZoneText, restText, durationText, targetPills } from '../targets'
import type { TemplateItem } from '@/types/workout'

const item = (over: Partial<TemplateItem> = {}): TemplateItem => ({
  id: 'x',
  exercise_key: 'plank',
  section: 'main',
  position: 0,
  target_reps: null,
  target_duration_seconds: null,
  target_load_kg: null,
  target_distance_m: null,
  rest_seconds: null,
  variant: null,
  notes: null,
  ...over,
})

const texts = (i: TemplateItem) => targetPills(i).map((p) => p.text)

describe('fmtRange', () => {
  it('renders a range', () => expect(fmtRange(8, 12)).toBe('8-12'))
  it('renders a lone bound', () => expect(fmtRange(8, null)).toBe('8'))
  it('collapses equal bounds', () => expect(fmtRange(10, 10)).toBe('10'))
  it('is empty with nothing set', () => expect(fmtRange(null, null)).toBe(''))
})

describe('hrZoneText', () => {
  it('renders a zone', () =>
    expect(hrZoneText(item({ target_hr_min: 160, target_hr_max: 175 }))).toBe('HR 160-175'))
  it('renders a floor', () => expect(hrZoneText(item({ target_hr_min: 120 }))).toBe('HR 120+'))
  it('renders a ceiling', () => expect(hrZoneText(item({ target_hr_max: 145 }))).toBe('HR ≤145'))
  it('is empty without a zone', () => expect(hrZoneText(item())).toBe(''))
})

describe('restText', () => {
  it('says full recovery rather than inventing a number', () =>
    expect(restText(item({ rest_mode: 'full' }))).toBe('full recovery'))
  it('full recovery wins over a stored number', () =>
    expect(restText(item({ rest_mode: 'full', rest_seconds: 60 }))).toBe('full recovery'))
  it('renders an autoregulated range', () =>
    expect(restText(item({ rest_seconds: 60, rest_seconds_max: 90, rest_mode: 'autoregulated' })))
      .toBe('rest 60-90s (by feel)'))
  it('renders by feel with no numbers', () =>
    expect(restText(item({ rest_mode: 'autoregulated' }))).toBe('rest by feel'))
  it('is empty when no rest is prescribed', () => expect(restText(item())).toBe(''))
})

describe('durationText', () => {
  it('keeps a range instead of collapsing to the lower bound', () =>
    expect(durationText(item({ target_duration_seconds: 40, target_duration_max_seconds: 42 })))
      .toBe('40-42s'))
  it('formats a single duration', () =>
    expect(durationText(item({ target_duration_seconds: 1200 }))).toBe('20 min'))
})

describe('targetPills', () => {
  it('shows a rep range, not its lower bound', () => {
    // The bug: 8-12 rendered as "8 reps", which reads as the prescription.
    expect(texts(item({ target_reps: 8, target_reps_max: 12 }))).toContain('8-12 reps')
  })

  it('shows a load range in lb', () => {
    expect(texts(item({ target_load_kg: 2.26796, target_load_max_kg: 3.62874 }))).toContain('5-8 lb')
  })

  it('carries the whole speed-endurance prescription', () => {
    const out = texts(
      item({
        target_reps: 8,
        target_reps_max: 12,
        target_distance_m: 200,
        target_duration_seconds: 40,
        target_duration_max_seconds: 42,
        rest_seconds: 60,
        rest_seconds_max: 90,
        rest_mode: 'autoregulated',
      }),
    )
    expect(out).toContain('8-12 reps')
    expect(out).toContain('40-42s')
    expect(out).toContain('200 m')
    expect(out).toContain('rest 60-90s (by feel)')
  })

  it('shows the heart-rate zone the aerobic day is built on', () => {
    expect(texts(item({ target_hr_min: 120, target_hr_max: 145 }))).toContain('HR 120-145')
  })

  it('shows cadence and speed', () => {
    const out = texts(item({ target_cadence: 170, target_speed_kph: 32.19 }))
    expect(out).toContain('170/min')
    expect(out).toContain('20 mph')
  })

  it('is empty for an item with no targets', () => expect(texts(item())).toEqual([]))
})
