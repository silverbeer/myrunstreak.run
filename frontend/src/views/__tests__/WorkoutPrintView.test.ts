import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCallMock(...args),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { athleteId: 'a1', templateId: 't1' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

import WorkoutPrintView from '../WorkoutPrintView.vue'

const template = {
  id: 't1',
  name: 'Track Thursday',
  type: 'intervals',
  rounds: 1,
  source: 'Matthew',
  notes: 'Goal for final rep: 400m broken into 100m sections',
  items: [
    { id: 'i1', exercise_key: 'easy_jog', section: 'warmup', position: 0, target_reps: null, target_duration_seconds: null, target_load_kg: null, target_distance_m: 804, rest_seconds: null, variant: null, notes: '1/2 mile warm up' },
    { id: 'i2', exercise_key: 'interval_run', section: 'main', position: 1, target_reps: 3, target_duration_seconds: null, target_load_kg: null, target_distance_m: 200, rest_seconds: 120, variant: null, notes: null },
    { id: 'i3', exercise_key: 'interval_run', section: 'main', position: 2, target_reps: 1, target_duration_seconds: null, target_load_kg: null, target_distance_m: 400, rest_seconds: null, variant: null, notes: null,
      segments: [
        { distance_m: 100, target_s_min: 20, target_s_max: 22, label: '0-100' },
        { distance_m: 100, target_s_min: 15, target_s_max: null, label: '100-200' },
      ] },
  ],
}

const exercises = [
  { key: 'easy_jog', display_name: 'Easy jog', measures: ['distance_m', 'duration_s'], cues: ['Conversational pace'], is_benchmark: false },
  { key: 'interval_run', display_name: 'Interval run', measures: ['distance_m', 'time_s'], cues: [], is_benchmark: true },
]

beforeEach(() => {
  apiCallMock.mockReset()
  apiCallMock.mockImplementation((path: string) => {
    if (path.startsWith('/workouts/templates/')) return Promise.resolve(template)
    if (path.startsWith('/athletes/')) return Promise.resolve({ id: 'a1', display_name: 'Gabe' })
    if (path === '/workouts/exercises') return Promise.resolve(exercises)
    return Promise.reject(new Error(`unexpected: ${path}`))
  })
})

describe('WorkoutPrintView (SB-231)', () => {
  it('renders the take-home sheet: title, meta blanks, sections', async () => {
    const w = mount(WorkoutPrintView)
    await flushPromises()
    expect(w.text()).toContain('Gabe — Track Thursday')
    expect(w.text()).toContain('Date:')
    expect(w.text()).toContain('Felt:')
    expect(w.text()).toContain('Warm-up')
    expect(w.text()).toContain('Workout')
    expect(w.text()).toContain('Great work!')
    expect(w.text()).toContain('fold here')
  })

  it('renders attempt rows for timed reps and segment goals for broken reps', async () => {
    const w = mount(WorkoutPrintView)
    await flushPromises()
    // 3x200 -> attempts 1..3 (interval_run measures time_s)
    expect(w.text()).toContain('Attempt')
    // broken 400 -> labeled segment rows with goals
    expect(w.text()).toContain('0-100')
    expect(w.text()).toContain('(20-22s)')
    expect(w.text()).toContain('100-200')
    expect(w.text()).toContain('(15s)')
  })

  it('acts as the athlete when fetching the template', async () => {
    mount(WorkoutPrintView)
    await flushPromises()
    expect(apiCallMock).toHaveBeenCalledWith(
      '/workouts/templates/t1',
      expect.objectContaining({ headers: { 'X-Act-As-Athlete': 'a1' } }),
    )
  })
})
