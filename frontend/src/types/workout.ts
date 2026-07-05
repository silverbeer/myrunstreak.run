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
