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

/** A circuit within a template: its own rounds and trailing rest (SB-527). */
export interface TemplateBlock {
  id: string
  template_id: string
  label: string
  position: number
  rounds: number
  rest_after_seconds: number | null
}

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

/** Partial patch of an existing exercise (all fields optional). */
export interface ExerciseUpdate {
  display_name?: string
  category?: ExerciseCategory
  measures?: string[]
  is_benchmark?: boolean
  visibility?: ExerciseVisibility
  aliases?: string[]
  movement_pattern?: MovementPattern | null
  equipment?: string[]
  cues?: string[]
  difficulty?: string | null
  instructions?: string | null
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
  rest_seconds_max?: number | null
  rest_mode?: 'fixed' | 'range' | 'full' | 'autoregulated' | null
  target_reps_max?: number | null
  target_load_max_kg?: number | null
  variant?: string | null
  option_group?: string | null
  option_group_label?: string | null
  notes?: string | null
}

export interface WorkoutTemplateInput {
  name: string
  type: WorkoutType
  rounds: number
  scheduled_for?: string | null
  items: TemplateItemInput[]
}

/** Per-segment goal of a broken rep (SB-264). */
export interface SegmentTarget {
  distance_m: number
  target_s_min: number | null
  target_s_max: number | null
  label: string | null
}

export interface TemplateItem {
  id: string
  exercise_key: string
  section: string
  position: number
  target_reps: number | null
  // Upper bounds: a target may be a range (SB-446) — "8-12x200", "5-8lb
  // dumbbells", "60-90 second rest". The field above is the lower bound.
  target_reps_max?: number | null
  target_duration_seconds: number | null
  target_duration_max_seconds?: number | null
  target_load_kg: number | null
  target_load_max_kg?: number | null
  target_distance_m: number | null
  rest_seconds: number | null
  rest_seconds_max?: number | null
  rest_mode?: 'fixed' | 'range' | 'full' | 'autoregulated' | null
  segments?: SegmentTarget[] | null
  // HR / cadence / speed (SB-447). Speed is canonical kph, shown as mph.
  // Cadence is a per-minute count whose unit follows the movement.
  target_hr_min?: number | null
  target_hr_max?: number | null
  target_cadence?: number | null
  target_speed_kph?: number | null
  variant: string | null
  // Alternatives (SB-448): items sharing an option_group are a "pick one of N".
  // null = mandatory. The label is read from any member of the group.
  option_group?: string | null
  option_group_label?: string | null
  notes: string | null  /** Circuit membership (SB-527); null when outside any circuit. */
  block_id?: string | null
}

export interface WorkoutTemplate {
  id: string
  // Who authored it (SB-486): the coach who prescribed it, or the athlete
  // themselves. Drives who may edit it, and the "added by" badge.
  created_by?: string | null
  athlete_id?: string | null
  name: string
  type: WorkoutType
  rounds: number
  source: string | null
  notes: string | null
  items: TemplateItem[]
  created_at: string | null
  // Optional date the workout is scheduled for (SB-335).
  scheduled_for?: string | null
  // Completion (SB-334): a logged session references this template.
  has_session?: boolean
  // How many times it has been done (SB-530) — "done 5×" / "not yet" on Plans.
  session_count?: number
  last_session_date?: string | null  /** Circuits, in position order (SB-527). Empty for simple templates. */
  blocks?: TemplateBlock[]
}

/**
 * One planned occasion (SB-534): a plan put on a date, by someone.
 *
 * Separate from the template because a plan is reused and an occasion happens
 * once — and because `created_by` is what lets the screen say who scheduled it.
 */
export interface WorkoutScheduleEntry {
  id: string
  template_id: string
  athlete_id: string | null
  created_by: string | null
  scheduled_for: string
  notes: string | null
  created_at?: string | null
  // The pattern that produced it (SB-535); null when scheduled by hand.
  recurrence_id?: string | null
}

/**
 * A weekly pattern that generates occasions (SB-535). The rule is what repeats;
 * the occasions it produces are ordinary schedule rows, so everything reading
 * Coming up needs no knowledge that recurrence exists.
 */
export interface WorkoutRecurrence {
  id: string
  template_id: string
  athlete_id: string | null
  created_by: string | null
  // 0 = Sunday .. 6 = Saturday — the same numbers `Date.getDay()` returns.
  byweekday: number[]
  starts_on: string
  ends_on: string | null
  active: boolean
  generated_through: string | null
}

export interface WorkoutRecurrenceInput {
  template_id: string
  byweekday: number[]
  starts_on: string
  ends_on?: string | null
}

export interface WorkoutScheduleInput {
  template_id: string
  scheduled_for: string
  notes?: string | null
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
  // Which prescribed item this set answers (SB-527). Null for an ad-hoc set
  // with no prescription behind it. Without it "lunge, round 1, 45s" cannot be
  // attributed — `lunge` appears several times in one template (SB-545).
  template_item_id?: string | null
  // Measured HR / cadence / speed (SB-447). Speed is canonical kph.
  hr_bpm_avg?: number | null
  hr_bpm_max?: number | null
  cadence?: number | null
  speed_kph?: number | null
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
  // What the athlete calls it (SB-536). null = unnamed; the row falls back to
  // the template name, then the type.
  name?: string | null
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
  // Which round of the circuit this attempt is (SB-545). Rounds live on the
  // attempt rather than the row because a set is what happens in a round —
  // one exercise done twice is two sets with different round numbers, which is
  // exactly the R1/R2 columns the print sheet has always had.
  round_number: number | null
  reps: number | null
  duration_s: number | null
  load_lb: number | null
  distance_m: number | null
  time_seconds: number | null
  // Entered in the units a US athlete reads off a watch; converted on the way
  // out (SB-486). Cadence has no unit of its own — it follows the movement.
  hr_bpm: number | null
  cadence: number | null
  speed_mph: number | null
  rpe: number | null
}

/** One exercise being logged, with one or more attempts (sets). */
export interface LoggerRow {
  uid: number
  exercise: Exercise
  // The prescribed item this row answers; null for anything the athlete added
  // themselves, and for ad-hoc logging with no template behind it (SB-531).
  template_item_id: string | null
  variant: string | null
  notes: string | null
  attempts: LoggerAttempt[]
}
