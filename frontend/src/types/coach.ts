export interface MyRoles {
  roles: string[]
  is_admin: boolean
}

export interface Athlete {
  id: string
  display_name: string
  birth_year: number | null
  linked_user_id: string | null
  created_by: string | null
  notes: string | null
  created_at: string
}

export interface AthleteCreate {
  display_name: string
  birth_year?: number | null
  notes?: string | null
}

export type WorkoutType = 'circuit' | 'intervals' | 'test' | string

export interface ExerciseSet {
  id: string
  exercise_key: string
  round_number: number | null
  reps: number | null
  duration_seconds: number | null
  load_kg: number | null
  distance_m: number | null
  time_seconds: number | null
  rpe: number | null
}

export interface WorkoutSession {
  id: string
  athlete_id: string | null
  session_date: string
  type: WorkoutType
  total_minutes: number | null
  how_felt: string | null
  notes: string | null
  sets: ExerciseSet[]
}
