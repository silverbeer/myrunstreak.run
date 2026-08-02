import { describe, it, expect } from 'vitest'
import {
  blankAttempt,
  buildSessionPayload,
  defaultSessionName,
  templateToRows,
  type SessionMeta,
} from '@/utils/sessionPayload'
import type { Exercise, LoggerAttempt, LoggerRow, WorkoutTemplate } from '@/types/workout'

const ex = (key: string, measures: string[] = ['reps']): Exercise => ({
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
  name: null,
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

  it('keeps a movement that has nothing to measure (SB-486)', () => {
    // A tick-box exercise carries no `measures`, so there is nothing for the
    // athlete to type — the row's presence is the record. Dropping it as
    // "empty" would make a completed workout read as half-done.
    const p = buildSessionPayload(meta, [
      row('pushups', { attempts: [attempt({ reps: 8 })] }),
      { ...row('skywalker'), exercise: ex('skywalker', []) },
    ])

    expect(p.sets).toHaveLength(2)
    const tick = p.sets.find((s) => s.exercise_key === 'skywalker')
    expect(tick).toBeDefined()
    expect(tick?.reps ?? null).toBeNull()
  })

  it('still drops a measurable exercise the athlete left blank', () => {
    // The distinction: nothing *could* be entered vs nothing *was*.
    const p = buildSessionPayload(meta, [row('plank', { attempts: [attempt()] })])
    expect(p.sets).toHaveLength(0)
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


describe('defaultSessionName (SB-536)', () => {
  it('names a session after its own day and date', () => {
    // The weekday is what he recognises; the date is what tells two Sundays
    // apart on the Completed list.
    expect(defaultSessionName('2026-08-02')).toBe('Sunday 2 Aug')
    expect(defaultSessionName('2026-01-01')).toBe('Thursday 1 Jan')
  })

  it('reads the session date, never the clock', () => {
    // A workout done Sunday but entered on Tuesday must not be called Tuesday,
    // and must carry no time of day — SB-531's version took the weekday from
    // the session and the hour from `new Date()`.
    const name = defaultSessionName('2026-08-02')
    expect(name).toBe('Sunday 2 Aug')
    expect(name).not.toMatch(/morning|afternoon|evening/)
  })

  it('does not shift a day in negative-offset zones (timezone-safe)', () => {
    // new Date('2026-08-01') is UTC midnight → Jul 31 locally in the US.
    expect(defaultSessionName('2026-08-01')).toBe('Saturday 1 Aug')
  })

  it('falls back to something printable when the date is unusable', () => {
    expect(defaultSessionName('')).toBe('Workout')
    expect(defaultSessionName('nope')).toBe('Workout')
  })
})

describe('buildSessionPayload — naming (SB-536)', () => {
  const rows = [row('pushups', { attempts: [attempt({ reps: 10 })] })]

  it('carries the name through', () => {
    const p = buildSessionPayload({ ...meta, name: 'Garage circuit' }, rows)
    expect(p.name).toBe('Garage circuit')
  })

  it('treats a blank name as no name at all', () => {
    // An empty string is a label that reads as nothing; null falls the row back
    // to the plan name, then the type.
    expect(buildSessionPayload({ ...meta, name: '   ' }, rows).name).toBeNull()
    expect(buildSessionPayload({ ...meta, name: null }, rows).name).toBeNull()
  })
})
