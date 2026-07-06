import { describe, it, expect } from 'vitest'
import {
  blankAttempt,
  buildSessionPayload,
  templateToRows,
  type SessionMeta,
} from '@/utils/sessionPayload'
import type { Exercise, LoggerAttempt, LoggerRow, WorkoutTemplate } from '@/types/workout'

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
const attempt = (over: Partial<LoggerAttempt> = {}): LoggerAttempt => ({ ...blankAttempt(), ...over })
const row = (key: string, over: Partial<LoggerRow> = {}): LoggerRow => ({
  uid: uid++,
  exercise: ex(key),
  round_number: null,
  variant: null,
  notes: null,
  attempts: [blankAttempt()],
  ...over,
})

const meta: SessionMeta = {
  session_date: '2026-07-06',
  type: 'circuit',
  total_minutes: 45,
  how_felt: 'good',
  notes: '  solid  ',
  template_id: 't1',
}

describe('buildSessionPayload', () => {
  it('carries session meta and trims notes', () => {
    const p = buildSessionPayload(meta, [row('pushups', { attempts: [attempt({ reps: 10 })] })])
    expect(p).toMatchObject({
      session_date: '2026-07-06',
      type: 'circuit',
      total_minutes: 45,
      how_felt: 'good',
      notes: 'solid',
      template_id: 't1',
    })
  })

  it('converts load lb → kg per attempt', () => {
    const p = buildSessionPayload(meta, [row('carry', { attempts: [attempt({ load_lb: 10 })] })])
    expect(p.sets[0].load_kg).toBe(4.5)
  })

  it('logs multiple attempts as sets with a 1-based set_index and time each', () => {
    const dash = row('40_yard_dash', {
      attempts: [
        attempt({ time_seconds: 5.4 }),
        attempt({ time_seconds: 5.2 }),
        attempt({ time_seconds: 5.3 }),
      ],
    })
    const p = buildSessionPayload(meta, [dash])
    expect(p.sets).toHaveLength(3)
    expect(p.sets.map((s) => [s.set_index, s.time_seconds])).toEqual([
      [1, 5.4],
      [2, 5.2],
      [3, 5.3],
    ])
    expect(p.sets.every((s) => s.exercise_key === '40_yard_dash')).toBe(true)
  })

  it('single attempt gets a null set_index', () => {
    const p = buildSessionPayload(meta, [row('pushups', { attempts: [attempt({ reps: 12 })] })])
    expect(p.sets).toHaveLength(1)
    expect(p.sets[0].set_index).toBeNull()
    expect(p.sets[0].reps).toBe(12)
  })

  it('drops empty attempts and fully-empty rows', () => {
    const p = buildSessionPayload(meta, [
      row('pushups', { attempts: [attempt({ reps: 8 }), attempt()] }), // 2nd empty
      row('plank', { attempts: [attempt()] }), // all empty → dropped
    ])
    expect(p.sets).toHaveLength(1)
    expect(p.sets[0].exercise_key).toBe('pushups')
    expect(p.sets[0].set_index).toBeNull() // only one non-empty attempt survived
  })

  it('carries round_number + trims variant, notes on first set only', () => {
    const p = buildSessionPayload(meta, [
      row('pushups', {
        round_number: 2,
        variant: '  left  ',
        notes: '  felt strong  ',
        attempts: [attempt({ reps: 10 }), attempt({ reps: 9 })],
      }),
    ])
    expect(p.sets[0]).toMatchObject({ round_number: 2, variant: 'left', notes: 'felt strong' })
    expect(p.sets[1].notes).toBeNull()
  })
})

describe('templateToRows', () => {
  const tpl: WorkoutTemplate = {
    id: 't1',
    name: 'Monday - Circuit',
    type: 'circuit',
    rounds: 3,
    source: null,
    notes: null,
    created_at: null,
    items: [
      { id: 'i2', exercise_key: 'plank', section: 'main', position: 1, target_reps: null, target_duration_seconds: 60, target_load_kg: null, target_distance_m: null, rest_seconds: null, variant: 'front', notes: null },
      { id: 'i1', exercise_key: 'pushups', section: 'main', position: 0, target_reps: 15, target_duration_seconds: null, target_load_kg: null, target_distance_m: null, rest_seconds: null, variant: null, notes: null },
    ],
  }

  it('prefills rows ordered by position, one blank attempt each, catalog name resolved', () => {
    const byKey = new Map([['pushups', ex('pushups', ['reps'])]])
    const rows = templateToRows(tpl, byKey, 10)
    expect(rows.map((r) => r.exercise.key)).toEqual(['pushups', 'plank'])
    expect(rows[0].uid).toBe(10)
    expect(rows[1].uid).toBe(11)
    expect(rows[0].exercise.measures).toEqual(['reps']) // resolved from catalog
    expect(rows[1].exercise.display_name).toBe('plank') // fallback (not in catalog)
    expect(rows[1].variant).toBe('front') // carried from template item
    expect(rows.every((r) => r.attempts.length === 1)).toBe(true)
  })
})
