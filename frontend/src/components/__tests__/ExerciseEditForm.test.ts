import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ExerciseEditForm from '../ExerciseEditForm.vue'
import type { Exercise, ExerciseUpdate } from '@/types/workout'

const ex = (over: Partial<Exercise> = {}): Exercise => ({
  key: 'goblet_squat',
  display_name: 'Goblet Squat',
  category: 'strength',
  measures: ['reps', 'load_kg'],
  is_benchmark: false,
  owner_id: 'u1',
  visibility: 'private',
  created_by: 'u1',
  forked_from: null,
  aliases: ['kb squat'],
  movement_pattern: 'squat',
  equipment: ['kettlebell'],
  body_region: [],
  laterality: null,
  difficulty: 'beginner',
  tags: [],
  media_url: null,
  thumbnail_url: null,
  cues: ['Chest up'],
  instructions: null,
  ...over,
})

describe('ExerciseEditForm', () => {
  it('prefills inputs from the exercise', () => {
    const w = mount(ExerciseEditForm, { props: { exercise: ex() } })
    expect((w.find('[data-testid="edit-name"]').element as HTMLInputElement).value).toBe('Goblet Squat')
    expect((w.find('[data-testid="edit-aliases"]').element as HTMLInputElement).value).toBe('kb squat')
    expect((w.find('[data-testid="edit-cues"]').element as HTMLTextAreaElement).value).toBe('Chest up')
  })

  it('shows a Canonical badge only when owner_id is null', () => {
    expect(mount(ExerciseEditForm, { props: { exercise: ex() } }).find('[data-testid="canonical-badge"]').exists()).toBe(false)
    const canonical = mount(ExerciseEditForm, { props: { exercise: ex({ owner_id: null }) } })
    expect(canonical.find('[data-testid="canonical-badge"]').exists()).toBe(true)
  })

  it('emits a patch reflecting edits (name, measures toggle, cues)', async () => {
    const w = mount(ExerciseEditForm, { props: { exercise: ex() } })
    await w.find('[data-testid="edit-name"]').setValue('Goblet Squat 2.0')
    await w.find('[data-testid="edit-measure-time_s"] input').setValue(true) // add time_s
    await w.find('[data-testid="edit-cues"]').setValue('Chest up, Brace')
    await w.find('[data-testid="edit-form"]').trigger('submit')

    const patch = w.emitted('save')?.[0]?.[0] as ExerciseUpdate
    expect(patch.display_name).toBe('Goblet Squat 2.0')
    expect(patch.measures).toEqual(['reps', 'load_kg', 'time_s'])
    expect(patch.cues).toEqual(['Chest up', 'Brace'])
  })

  it('does not emit save when the name is blanked', async () => {
    const w = mount(ExerciseEditForm, { props: { exercise: ex() } })
    await w.find('[data-testid="edit-name"]').setValue('   ')
    await w.find('[data-testid="edit-form"]').trigger('submit')
    expect(w.emitted('save')).toBeUndefined()
  })

  it('emits cancel', async () => {
    const w = mount(ExerciseEditForm, { props: { exercise: ex() } })
    await w.find('[data-testid="edit-cancel"]').trigger('click')
    expect(w.emitted('cancel')).toBeTruthy()
  })
})
