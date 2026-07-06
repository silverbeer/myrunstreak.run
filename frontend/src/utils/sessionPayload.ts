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

/** A fresh empty attempt (one set of an exercise). */
export function blankAttempt(): LoggerAttempt {
  return {
    reps: null,
    duration_s: null,
    load_lb: null,
    distance_m: null,
    time_seconds: null,
    rpe: null,
  }
}

/** An attempt with no measurable value — dropped from the payload. */
function isEmptyAttempt(a: LoggerAttempt): boolean {
  return (
    a.reps == null &&
    a.duration_s == null &&
    a.load_lb == null &&
    a.distance_m == null &&
    a.time_seconds == null &&
    a.rpe == null
  )
}

export interface SessionMeta {
  session_date: string
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
    const multi = filled.length > 1
    filled.forEach((a, i) => {
      sets.push({
        exercise_key: row.exercise.key,
        round_number: row.round_number,
        set_index: multi ? i + 1 : null,
        variant: row.variant?.trim() || null,
        reps: a.reps,
        duration_seconds: a.duration_s,
        load_kg: lbToKg(a.load_lb),
        distance_m: a.distance_m,
        time_seconds: a.time_seconds,
        rpe: a.rpe,
        notes: i === 0 ? row.notes?.trim() || null : null,
      })
    })
  }
  return {
    session_date: meta.session_date,
    template_id: meta.template_id,
    type: meta.type,
    total_minutes: meta.total_minutes,
    how_felt: meta.how_felt,
    notes: meta.notes?.trim() || null,
    sets,
  }
}

/**
 * Prefill logger rows from a template's items (ordered by position), one blank
 * attempt each. The coach logs actuals against the prescription. `byKey` maps
 * exercise_key → catalog Exercise (for display name + which measures to show).
 */
export function templateToRows(
  tpl: WorkoutTemplate,
  byKey: Map<string, Exercise>,
  startUid: number,
): LoggerRow[] {
  return tpl.items
    .slice()
    .sort((a, b) => a.position - b.position)
    .map((it, i) => ({
      uid: startUid + i,
      exercise:
        byKey.get(it.exercise_key) ??
        ({ key: it.exercise_key, display_name: it.exercise_key, measures: [] } as unknown as Exercise),
      round_number: null,
      variant: it.variant,
      notes: null,
      attempts: [blankAttempt()],
    }))
}
