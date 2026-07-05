import { describe, it, expect } from 'vitest'
import { lbToKg, buildTemplatePayload, fmtDuration } from '@/utils/workoutPayload'
import type { BuilderItem, Exercise, WorkoutSectionKey } from '@/types/workout'

const ex = (key: string, measures: string[] = []): Exercise => ({
  key,
  display_name: key,
  category: 'strength',
  measures,
  is_benchmark: false,
  owner_id: null,
  visibility: 'public',
  created_by: null,
  forked_from: null,
  aliases: [],
  movement_pattern: null,
  equipment: [],
  body_region: [],
  laterality: null,
  difficulty: null,
  tags: [],
  media_url: null,
  thumbnail_url: null,
  cues: [],
  instructions: null,
})

let uid = 0
const item = (key: string, section: WorkoutSectionKey, over: Partial<BuilderItem> = {}): BuilderItem => ({
  uid: uid++,
  exercise: ex(key),
  section,
  reps: null,
  duration_s: null,
  load_lb: null,
  distance_m: null,
  rest_s: null,
  variant: null,
  notes: null,
  ...over,
})

describe('lbToKg', () => {
  it('converts lb to kg at 1 decimal', () => {
    expect(lbToKg(10)).toBe(4.5)
    expect(lbToKg(5)).toBe(2.3)
  })
  it('passes null through', () => {
    expect(lbToKg(null)).toBeNull()
  })
})

describe('fmtDuration', () => {
  it('shows whole minutes as "N min"', () => {
    expect(fmtDuration(480)).toBe('8 min')
    expect(fmtDuration(60)).toBe('1 min')
  })
  it('shows mm:ss for non-round minutes', () => {
    expect(fmtDuration(90)).toBe('1:30')
  })
  it('shows seconds under a minute', () => {
    expect(fmtDuration(45)).toBe('45s')
  })
})

describe('buildTemplatePayload', () => {
  it('orders items warm-up → main → cool-down with a running position', () => {
    const items = [
      item('cooldown_jog', 'cooldown'),
      item('pushups', 'main'),
      item('warmup_jog', 'warmup'),
      item('plank', 'main'),
    ]
    const payload = buildTemplatePayload('Sat', 'circuit', 2, items)
    expect(payload.items.map((i) => [i.exercise_key, i.section, i.position])).toEqual([
      ['warmup_jog', 'warmup', 0],
      ['pushups', 'main', 1],
      ['plank', 'main', 2],
      ['cooldown_jog', 'cooldown', 3],
    ])
  })

  it('converts load lb → kg and trims blank variant/notes to null', () => {
    const items = [item('farmers_carry', 'main', { load_lb: 10, variant: '  ', notes: ' go ' })]
    const payload = buildTemplatePayload('W', 'circuit', 1, items)
    expect(payload.items[0].target_load_kg).toBe(4.5)
    expect(payload.items[0].variant).toBeNull()
    expect(payload.items[0].notes).toBe('go')
  })

  it('carries name/type/rounds and passes numeric targets through', () => {
    const items = [item('pushups', 'main', { reps: 15, duration_s: 60, rest_s: 30 })]
    const payload = buildTemplatePayload('  Circuit  ', 'intervals', 3, items)
    expect(payload).toMatchObject({ name: 'Circuit', type: 'intervals', rounds: 3 })
    expect(payload.items[0]).toMatchObject({
      target_reps: 15,
      target_duration_seconds: 60,
      rest_seconds: 30,
    })
  })
})
