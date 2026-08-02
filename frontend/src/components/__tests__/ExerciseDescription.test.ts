import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ExerciseDescription from '../ExerciseDescription.vue'
import type { Exercise } from '@/types/workout'

const make = (over: Partial<Exercise> = {}): Exercise =>
  ({
    key: 'aquaman',
    display_name: 'Aquaman',
    category: 'strength',
    measures: ['duration_s'],
    is_benchmark: false,
    owner_id: null,
    visibility: 'public',
    created_by: null,
    forked_from: null,
    aliases: [],
    movement_pattern: null,
    equipment: [],
    body_region: [],
    laterality: null,
    difficulty: null,
    tags: [],
    media_url: null,
    thumbnail_url: null,
    // The real cues from the catalog — the ones Gabe could not see (SB-525).
    cues: ['Prone: lift opposite arm + leg', 'Long through the spine'],
    instructions: null,
    ...over,
  }) as Exercise

describe('ExerciseDescription (SB-525)', () => {
  it('answers "what is Aquaman" from the cues already in the catalog', () => {
    const w = mount(ExerciseDescription, { props: { exercise: make() } })
    expect(w.text()).toContain('Prone: lift opposite arm + leg')
    expect(w.text()).toContain('Long through the spine')
  })

  it('shows instructions alongside cues when both exist', () => {
    const w = mount(ExerciseDescription, {
      props: { exercise: make({ instructions: 'Hold two seconds at the top.' }) },
    })
    expect(w.text()).toContain('Long through the spine')
    expect(w.text()).toContain('Hold two seconds at the top.')
  })

  it('shows instructions on their own when there are no cues', () => {
    const w = mount(ExerciseDescription, {
      props: { exercise: make({ cues: [], instructions: 'Ten metres, walking.' }) },
    })
    expect(w.text()).toContain('Ten metres, walking.')
    expect(w.text()).not.toContain('No description')
  })

  it('says so honestly rather than showing an empty panel', () => {
    // 14 of 57 exercises have neither cues nor instructions. Silence would read
    // as a bug; the athlete should know there is simply nothing written yet.
    const w = mount(ExerciseDescription, {
      props: { exercise: make({ cues: [], instructions: null }) },
    })
    expect(w.text()).toContain('No description added for this exercise yet.')
  })

  it('does not blow up when the exercise is missing from the catalog', () => {
    const w = mount(ExerciseDescription, { props: { exercise: null } })
    expect(w.text()).toContain('No description added for this exercise yet.')
  })
})
