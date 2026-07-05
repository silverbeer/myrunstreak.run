import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WorkoutTemplateCard from '../WorkoutTemplateCard.vue'
import type { Exercise, TemplateItem, WorkoutTemplate } from '@/types/workout'

const ti = (over: Partial<TemplateItem>): TemplateItem => ({
  id: Math.random().toString(),
  exercise_key: 'x',
  section: 'main',
  position: 0,
  target_reps: null,
  target_duration_seconds: null,
  target_load_kg: null,
  target_distance_m: null,
  rest_seconds: null,
  variant: null,
  notes: null,
  ...over,
})

const template: WorkoutTemplate = {
  id: 't1',
  name: 'Monday - Circuit',
  type: 'circuit',
  rounds: 2,
  source: 'Matthew',
  notes: null,
  created_at: null,
  items: [
    ti({ exercise_key: 'easy_jog', section: 'warmup', position: 0, target_duration_seconds: 480 }),
    ti({ exercise_key: 'bicep_curl', section: 'main', position: 2, target_load_kg: 4.54, target_duration_seconds: 60 }),
    ti({ exercise_key: 'side_plank', section: 'main', position: 1, variant: 'left', target_duration_seconds: 60 }),
  ],
}

const exercises: Exercise[] = [
  { key: 'bicep_curl', display_name: 'Bicep curls', measures: [] } as unknown as Exercise,
]

describe('WorkoutTemplateCard', () => {
  it('renders name, type and rounds', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    expect(w.text()).toContain('Monday - Circuit')
    expect(w.text()).toContain('circuit')
    expect(w.text()).toContain('2× rounds')
  })

  it('groups items under section headings in canonical order', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    const text = w.text()
    expect(text).toContain('Warm-up')
    expect(text).toContain('Main')
    // warm-up heading appears before main
    expect(text.indexOf('Warm-up')).toBeLessThan(text.indexOf('Main'))
  })

  it('sorts items within a section by position', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    const text = w.text()
    // side_plank (pos 1) before bicep_curl (pos 2); no catalog → prettified keys
    expect(text.indexOf('Side plank')).toBeLessThan(text.indexOf('Bicep curl'))
  })

  it('uses the catalog display name, falls back to a prettified key', () => {
    const w = mount(WorkoutTemplateCard, { props: { template, exercises } })
    expect(w.text()).toContain('Bicep curls') // from catalog
    expect(w.text()).toContain('Side plank') // prettified from side_plank
    expect(w.text()).not.toContain('side_plank')
  })

  it('shows load in lb (kg → lb) and the variant', () => {
    const w = mount(WorkoutTemplateCard, { props: { template } })
    expect(w.text()).toContain('10 lb') // 4.54 kg → 10 lb
    expect(w.text()).toContain('(left)')
  })
})
