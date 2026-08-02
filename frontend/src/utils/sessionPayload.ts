import type {
  Exercise,
  LoggerAttempt,
  LoggerRow,
  SessionSetInput,
  WorkoutSessionInput,
  WorkoutTemplate,
  WorkoutType,
} from '@/types/workout'
import { lbToKg } from '@/utils/workoutPayload'
import { groupByBlock, roundsFor } from '@/utils/circuits'

/** Felt options: emoji shown to the coach → stored how_felt string. */
export const FELT_OPTIONS: { emoji: string; value: string; label: string }[] = [
  { emoji: '☺', value: 'good', label: 'Good' },
  { emoji: '😐', value: 'ok', label: 'OK' },
  { emoji: '☹', value: 'rough', label: 'Rough' },
]

/** Today as an ISO date (YYYY-MM-DD), the default session_date. */
export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

const WEEKDAYS_LONG = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
]
const MONTHS_SHORT = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/**
 * What an unnamed session is called until someone says otherwise (SB-536):
 * "Sunday 2 Aug". The weekday is what he recognises; the date is what tells two
 * Sundays apart on the Completed list.
 *
 * Read entirely from the session's own date, never the clock. A workout done on
 * Sunday but entered on Tuesday evening must not be called "Tuesday" — and not
 * "Sunday evening" either: SB-531's version took the weekday from the session
 * and the time of day from `new Date()`, which is only right when you log the
 * moment you finish.
 *
 * Parsed part-wise, because `new Date('2026-08-02')` is UTC midnight and lands
 * on the day before west of Greenwich — every name would be off by one.
 */
export function defaultSessionName(dateOnly: string): string {
  const [y, m, d] = dateOnly.split('-').map(Number)
  if (!y || !m || !d) return 'Workout'
  const date = new Date(y, m - 1, d)
  if (Number.isNaN(date.getTime())) return 'Workout'
  return `${WEEKDAYS_LONG[date.getDay()]} ${d} ${MONTHS_SHORT[m - 1]}`
}

/** A fresh empty attempt (one set of an exercise), optionally in a round. */
export function blankAttempt(round: number | null = null): LoggerAttempt {
  return {
    round_number: round,
    reps: null,
    duration_s: null,
    load_lb: null,
    distance_m: null,
    time_seconds: null,
    hr_bpm: null,
    cadence: null,
    speed_mph: null,
    rpe: null,
  }
}

/** An attempt with no measurable value — dropped from the payload. */
function isEmptyAttempt(a: LoggerAttempt): boolean {
  // round_number is structure, not a measurement — an attempt carrying only
  // its round number is still an attempt nobody filled in.
  return (
    a.reps == null &&
    a.duration_s == null &&
    a.load_lb == null &&
    a.distance_m == null &&
    a.time_seconds == null &&
    a.hr_bpm == null &&
    a.cadence == null &&
    a.speed_mph == null &&
    a.rpe == null
  )
}

export interface SessionMeta {
  session_date: string
  name: string | null
  type: WorkoutType
  total_minutes: number | null
  how_felt: string | null
  notes: string | null
  template_id: string | null
}

/**
 * Turn the logger's local rows into the API payload. Each non-empty attempt
 * becomes a set with a 1-based set_index within its row; loads convert lb → kg.
 * Rows whose attempts are all empty are dropped. Pure + deterministic.
 */
export function buildSessionPayload(meta: SessionMeta, rows: LoggerRow[]): WorkoutSessionInput {
  const sets: SessionSetInput[] = []
  for (const row of rows) {
    const filled = row.attempts.filter((a) => !isEmptyAttempt(a))

    // Some movements have nothing to measure — a plank variation the coach just
    // wants ticked off. The catalog says so by carrying no `measures`, and
    // there is nothing for the athlete to type, so the row's presence IS the
    // record. Without this it would be dropped as "empty" and the workout would
    // read as half-done.
    if (filled.length === 0 && row.exercise.measures.length === 0) {
      sets.push({
        exercise_key: row.exercise.key,
        template_item_id: row.template_item_id,
        round_number: row.attempts[0]?.round_number ?? null,
        set_index: null,
        variant: row.variant?.trim() || null,
        notes: row.notes?.trim() || null,
      })
      continue
    }
    const multi = filled.length > 1
    filled.forEach((a, i) => {
      sets.push({
        exercise_key: row.exercise.key,
        // The link SB-527 added and nothing ever wrote (SB-545). Without it
        // "did he do what was prescribed?" is not answerable by query.
        template_item_id: row.template_item_id,
        round_number: a.round_number,
        set_index: multi ? i + 1 : null,
        variant: row.variant?.trim() || null,
        reps: a.reps,
        duration_seconds: a.duration_s,
        load_kg: lbToKg(a.load_lb),
        distance_m: a.distance_m,
        time_seconds: a.time_seconds,
        hr_bpm_avg: a.hr_bpm,
        cadence: a.cadence,
        speed_kph: a.speed_mph == null ? null : Math.round(a.speed_mph * 1.609344 * 100) / 100,
        rpe: a.rpe,
        notes: i === 0 ? row.notes?.trim() || null : null,
      })
    })
  }
  return {
    session_date: meta.session_date,
    // Blank means "no name given" — the row falls back to the template name,
    // then the type. An empty string would be a name that reads as nothing.
    name: meta.name?.trim() || null,
    template_id: meta.template_id,
    type: meta.type,
    total_minutes: meta.total_minutes,
    how_felt: meta.how_felt,
    notes: meta.notes?.trim() || null,
    sets,
  }
}

/**
 * Prefill logger rows from a template's items, in position order.
 *
 * An exercise in a circuit done twice arrives with two attempts, already
 * numbered R1 and R2 (SB-545). Before this the athlete got one empty box and an
 * empty "Round" field, and recording the prescription as written meant tapping
 * "+ Add set" on eleven cards and typing twenty-two round numbers — so the
 * rounds simply never got logged.
 *
 * Every row carries the `template_item_id` it answers, which is what makes
 * "did he do what was prescribed?" a query rather than a guess (SB-527).
 *
 * `byKey` maps exercise_key → catalog Exercise (display name + which measures
 * to show).
 */
export function templateToRows(
  tpl: WorkoutTemplate,
  byKey: Map<string, Exercise>,
  startUid: number,
): LoggerRow[] {
  const items = [...tpl.items].sort((a, b) => a.position - b.position)
  const roundsByItem = new Map<string, number>()
  for (const group of groupByBlock(items, tpl.blocks ?? [])) {
    const rounds = roundsFor(group, tpl.rounds)
    for (const it of group.items) roundsByItem.set(it.id, rounds)
  }

  return items.map((it, i) => {
    const rounds = roundsByItem.get(it.id) ?? 1
    return {
      uid: startUid + i,
      exercise:
        byKey.get(it.exercise_key) ??
        ({ key: it.exercise_key, display_name: it.exercise_key, measures: [] } as unknown as Exercise),
      template_item_id: it.id,
      variant: it.variant,
      notes: null,
      // One attempt per round, numbered. A single-round exercise keeps a null
      // round — there is no round 1 of 1 worth stating.
      attempts:
        rounds > 1
          ? Array.from({ length: rounds }, (_, r) => blankAttempt(r + 1))
          : [blankAttempt()],
    }
  })
}
