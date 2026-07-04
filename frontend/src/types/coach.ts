export interface MyRoles {
  roles: string[]
  is_admin: boolean
}

export interface Invite {
  id: string
  token: string
  email: string
  created_by: string | null
  expires_at: string
  grant_role: string | null
  athlete_id: string | null
  redeemed_at: string | null
  redeemed_by: string | null
  created_at: string
}

export interface AthleteProfile {
  sport: string | null
  position: string | null
  team: string | null
  dominant_side: string | null
  jersey_number: string | null
  height_cm: number | null
  weight_kg: number | null
  date_of_birth: string | null
  sex: string | null
  bio: string | null
  personal_goals: string | null
  athlete_email: string | null
  athlete_phone: string | null
  guardian_name: string | null
  guardian_email: string | null
  guardian_phone: string | null
  coaching_notes: string | null
  updated_at: string | null
}

// Partial patch. Server enforces which keys the caller (coach vs athlete) may set.
export type AthleteProfileUpdate = Partial<Omit<AthleteProfile, 'updated_at'>>

// Fields the linked athlete may edit (mirrors backend ATHLETE_EDITABLE_FIELDS).
export const ATHLETE_EDITABLE_FIELDS = [
  'bio',
  'personal_goals',
  'athlete_email',
  'athlete_phone',
  'guardian_name',
  'guardian_email',
  'guardian_phone',
] as const

export interface Athlete {
  id: string
  display_name: string
  birth_year: number | null
  linked_user_id: string | null
  created_by: string | null
  notes: string | null
  created_at: string
  profile?: AthleteProfile | null
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
