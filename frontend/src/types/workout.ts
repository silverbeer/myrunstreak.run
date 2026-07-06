export type ExerciseVisibility = 'private' | 'public'

export type MovementPattern =
  | 'squat'
  | 'hinge'
  | 'lunge'
  | 'push'
  | 'pull'
  | 'carry'
  | 'rotation'
  | 'anti_rotation'
  | 'jump'
  | 'sprint'
  | 'isometric'
  | 'mobility'
  | 'other'

export type ExerciseCategory = 'strength' | 'speed' | 'power' | 'mobility' | 'cardio' | 'test'

export interface Exercise {
  key: string
  display_name: string
  category: ExerciseCategory
  measures: string[]
  is_benchmark: boolean
  owner_id: string | null // null = canonical library
  visibility: ExerciseVisibility
  created_by: string | null
  forked_from: string | null
  aliases: string[]
  movement_pattern: MovementPattern | null
  equipment: string[]
  body_region: string[]
  laterality: string | null
  difficulty: string | null
  tags: string[]
  media_url: string | null
  thumbnail_url: string | null
  cues: string[]
  instructions: string | null
}

export interface ExerciseCreate {
  display_name: string
  category: ExerciseCategory
  measures?: string[]
  visibility?: ExerciseVisibility
  aliases?: string[]
  movement_pattern?: MovementPattern | null
  equipment?: string[]
  cues?: string[]
}

export type WorkoutSectionKey = 'warmup' | 'main' | 'cooldown'
export type WorkoutType = 'circuit' | 'intervals' | 'test' | 'session'

export interface TemplateItemInput {
  exercise_key: string
  section: string
  position: number
  target_reps?: number | null
  target_duration_seconds?: number | null
  target_load_kg?: number | null
  target_distance_m?: number | null
  rest_seconds?: number | null
  variant?: string | null
  notes?: string | null
}

export interface WorkoutTemplateInput {
  name: string
  type: WorkoutType
  rounds: number
  items: TemplateItemInput[]
}

export interface TemplateItem {
  id: string
  exercise_key: string
  section: string
  position: number
  target_reps: number | null
  target_duration_seconds: number | null
  target_load_kg: number | null
  target_distance_m: number | null
  rest_seconds: number | null
  variant: string | null
  notes: string | null
}

export interface WorkoutTemplate {
  id: string
  name: string
  type: WorkoutType
  rounds: number
  source: string | null
  notes: string | null
  items: TemplateItem[]
  created_at: string | null
}

/** One row while building — loads are entered in lb (US coach), stored as kg. */
export interface BuilderItem {
  uid: number
  exercise: Exercise
  section: WorkoutSectionKey
  reps: number | null
  duration_s: number | null
  load_lb: number | null
  distance_m: number | null
  rest_s: number | null
  variant: string | null
  notes: string | null
}

// --------------------------------------------------------------------------- //
// Session logging (the actual performance — SB-230)
// --------------------------------------------------------------------------- //

/** One logged set in the API payload. Only the used dimensions are filled. */
export interface SessionSetInput {
  exercise_key: string
  round_number?: number | null
  set_index?: number | null
  variant?: string | null
  reps?: number | null
  duration_seconds?: number | null
  load_kg?: number | null
  distance_m?: number | null
  time_seconds?: number | null
  rpe?: number | null
  notes?: string | null
}

export interface WorkoutSessionInput {
  session_date: string
  template_id?: string | null
  type: WorkoutType
  total_minutes?: number | null
  how_felt?: string | null
  notes?: string | null
  sets: SessionSetInput[]
}

/**
 * One attempt of an exercise while logging — a single set. A 40-dash logged
 * three times is three attempts on one row (each its own set_index/time).
 * Loads are entered in lb (US coach), stored as kg.
 */
export interface LoggerAttempt {
  reps: number | null
  duration_s: number | null
  load_lb: number | null
  distance_m: number | null
  time_seconds: number | null
  rpe: number | null
}

/** One exercise being logged, with one or more attempts (sets). */
export interface LoggerRow {
  uid: number
  exercise: Exercise
  round_number: number | null
  variant: string | null
  notes: string | null
  attempts: LoggerAttempt[]
}
