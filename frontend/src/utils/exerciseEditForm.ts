import type { Exercise, ExerciseCategory, ExerciseUpdate, MovementPattern } from '@/types/workout'

/** Measure tokens an exercise can record (canonical seed vocabulary). Note the
 * token is `time_s` even though the logged-set column is `time_seconds`. */
export const MEASURE_OPTIONS: { token: string; label: string }[] = [
  { token: 'reps', label: 'Reps' },
  { token: 'duration_s', label: 'Duration (s)' },
  { token: 'load_kg', label: 'Load' },
  { token: 'distance_m', label: 'Distance (m)' },
  { token: 'time_s', label: 'Time (s)' },
]

export const DIFFICULTIES = ['beginner', 'intermediate', 'advanced'] as const

/** Editable shape backing the form — lists as comma text for easy typing. */
export interface ExerciseFormState {
  display_name: string
  category: ExerciseCategory
  movement_pattern: MovementPattern | null
  difficulty: string | null
  visibility: 'public' | 'private'
  is_benchmark: boolean
  measures: string[]
  aliases: string
  equipment: string
  cues: string
}

/** "a, b ,, a " → ['a','b'] — trimmed, blanks dropped, de-duped, order kept. */
export function parseList(raw: string): string[] {
  const out: string[] = []
  for (const part of raw.split(',')) {
    const v = part.trim()
    if (v && !out.includes(v)) out.push(v)
  }
  return out
}

/** Current exercise → form state (arrays joined for text inputs). */
export function exerciseToForm(ex: Exercise): ExerciseFormState {
  return {
    display_name: ex.display_name,
    category: ex.category,
    movement_pattern: ex.movement_pattern,
    difficulty: ex.difficulty,
    visibility: ex.visibility,
    is_benchmark: ex.is_benchmark,
    measures: [...ex.measures],
    aliases: ex.aliases.join(', '),
    equipment: ex.equipment.filter((e) => e !== 'none').join(', '),
    cues: ex.cues.join(', '),
  }
}

/** Form state → API patch. Pure + deterministic; sends the full editable set
 * (the backend patches every provided field). */
export function buildExercisePatch(form: ExerciseFormState): ExerciseUpdate {
  return {
    display_name: form.display_name.trim(),
    category: form.category,
    movement_pattern: form.movement_pattern,
    difficulty: form.difficulty || null,
    visibility: form.visibility,
    is_benchmark: form.is_benchmark,
    measures: form.measures,
    aliases: parseList(form.aliases),
    equipment: parseList(form.equipment),
    cues: parseList(form.cues),
  }
}
