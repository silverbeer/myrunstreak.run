import { describe, it, expect } from 'vitest'
import {
  buildExercisePatch,
  exerciseToForm,
  parseList,
  type ExerciseFormState,
} from '@/utils/exerciseEditForm'
import type { Exercise } from '@/types/workout'

const ex = (over: Partial<Exercise> = {}): Exercise => ({
  key: 'goblet_squat',
  display_name: 'Goblet Squat',
  category: 'strength',
  measures: ['reps', 'load_kg'],
  is_benchmark: false,
  owner_id: 'me',
  visibility: 'private',
  created_by: 'me',
  forked_from: null,
  aliases: ['kb squat'],
  movement_pattern: 'squat',
  equipment: ['kettlebell', 'none'],
  body_region: [],
  laterality: null,
  difficulty: 'beginner',
  tags: [],
  media_url: null,
  thumbnail_url: null,
  cues: ['Chest up', 'Knees out'],
  instructions: null,
  ...over,
})

describe('parseList', () => {
  it('trims, drops blanks, de-dupes, keeps order', () => {
    expect(parseList('a, b ,, a ,  c')).toEqual(['a', 'b', 'c'])
  })
  it('empty string → empty array', () => {
    expect(parseList('   ')).toEqual([])
  })
})

describe('exerciseToForm', () => {
  it('maps the exercise into form state, joining lists and dropping the none sentinel', () => {
    const f = exerciseToForm(ex())
    expect(f).toMatchObject({
      display_name: 'Goblet Squat',
      category: 'strength',
      movement_pattern: 'squat',
      difficulty: 'beginner',
      visibility: 'private',
      is_benchmark: false,
      measures: ['reps', 'load_kg'],
      aliases: 'kb squat',
      equipment: 'kettlebell', // 'none' filtered out
      cues: 'Chest up, Knees out',
    })
  })
})

describe('buildExercisePatch', () => {
  const base: ExerciseFormState = {
    display_name: '  Goblet Squat  ',
    category: 'strength',
    movement_pattern: 'squat',
    difficulty: '',
    visibility: 'public',
    is_benchmark: true,
    measures: ['reps', 'time_s'],
    aliases: 'kb squat, goblet',
    equipment: 'kettlebell',
    cues: 'Chest up, , Brace',
  }

  it('trims name, parses lists, and coerces empty difficulty to null', () => {
    const p = buildExercisePatch(base)
    expect(p).toEqual({
      display_name: 'Goblet Squat',
      category: 'strength',
      movement_pattern: 'squat',
      difficulty: null,
      visibility: 'public',
      is_benchmark: true,
      measures: ['reps', 'time_s'],
      aliases: ['kb squat', 'goblet'],
      equipment: ['kettlebell'],
      cues: ['Chest up', 'Brace'],
    })
  })

  it('round-trips through exerciseToForm without dropping data', () => {
    const p = buildExercisePatch(exerciseToForm(ex()))
    expect(p.measures).toEqual(['reps', 'load_kg'])
    expect(p.cues).toEqual(['Chest up', 'Knees out'])
    expect(p.aliases).toEqual(['kb squat'])
    expect(p.equipment).toEqual(['kettlebell'])
  })
})
