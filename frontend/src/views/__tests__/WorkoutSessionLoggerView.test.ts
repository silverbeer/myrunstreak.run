import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({
  createSession: vi.fn(),
  getTemplate: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  isCoach: { value: true },
  loadRoles: vi.fn().mockResolvedValue(undefined),
  load: vi.fn().mockResolvedValue(undefined),
  params: { athleteId: 'ath1' } as Record<string, string>,
}))

const catalog = [
  {
    key: 'pushups', display_name: 'Push-ups', category: 'strength', measures: ['reps', 'duration_s'],
    is_benchmark: false, owner_id: null, visibility: 'public', created_by: null, forked_from: null,
    aliases: [], movement_pattern: 'push', equipment: [], body_region: [], laterality: null,
    difficulty: null, tags: [], media_url: null, thumbnail_url: null, cues: [], instructions: null,
  },
  {
    key: 'farmers_carry', display_name: "Farmer's carry", category: 'strength', measures: ['duration_s', 'load_kg'],
    is_benchmark: false, owner_id: null, visibility: 'public', created_by: null, forked_from: null,
    aliases: [], movement_pattern: 'carry', equipment: ['dumbbell'], body_region: [], laterality: null,
    difficulty: null, tags: [], media_url: null, thumbnail_url: null, cues: [], instructions: null,
  },
  {
    key: '40_yard_dash', display_name: '40-yard dash', category: 'test', measures: ['time_seconds'],
    is_benchmark: true, owner_id: null, visibility: 'public', created_by: null, forked_from: null,
    aliases: [], movement_pattern: 'sprint', equipment: [], body_region: [], laterality: null,
    difficulty: null, tags: [], media_url: null, thumbnail_url: null, cues: [], instructions: null,
  },
]

vi.mock('@/composables/useExercises', async () => {
  const { ref } = await import('vue')
  return { useExercises: () => ({ exercises: ref(catalog), load: h.load, loading: ref(false), error: ref(null) }) }
})
vi.mock('@/composables/useCoach', () => ({
  useRoles: () => ({ isCoach: h.isCoach, loadRoles: h.loadRoles }),
}))
vi.mock('@/composables/useWorkoutTemplates', () => ({
  getTemplate: (...a: unknown[]) => h.getTemplate(...a),
}))
vi.mock('@/composables/useWorkoutSessions', () => ({
  createSession: (...a: unknown[]) => h.createSession(...a),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: h.params }),
  useRouter: () => ({ push: h.push, replace: h.replace }),
  RouterLink: { template: '<a><slot /></a>' },
}))

beforeEach(() => {
  vi.clearAllMocks()
  h.isCoach.value = true
  h.params = { athleteId: 'ath1' }
})

async function mountLogger() {
  const View = (await import('../WorkoutSessionLoggerView.vue')).default
  const w = mount(View, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return w
}

describe('WorkoutSessionLoggerView', () => {
  it('redirects non-coaches', async () => {
    h.isCoach.value = false
    await mountLogger()
    expect(h.replace).toHaveBeenCalledWith('/dashboard')
  })

  it('adds an exercise via the picker', async () => {
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(true)
  })

  it('save is disabled until a set has a value', async () => {
    const w = await mountLogger()
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(true)
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    // row added but no value yet → still disabled
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(true)
    await w.find('[data-testid="reps-pushups-0"]').setValue(12)
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(false)
  })

  it('saves a session with act-as and lb→kg conversion', async () => {
    h.createSession.mockResolvedValue({ id: 's1' })
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-farmers_carry"]').trigger('click')
    await w.find('[data-testid="load_lb-farmers_carry-0"]').setValue(10)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()

    expect(h.createSession).toHaveBeenCalledTimes(1)
    const [payload, athleteId] = h.createSession.mock.calls[0]
    expect(athleteId).toBe('ath1')
    expect(payload.sets[0]).toMatchObject({ exercise_key: 'farmers_carry', load_kg: 4.5 })
    expect(h.push).toHaveBeenCalledWith('/coach/ath1')
  })

  it('logs a benchmark three times — three sets with time + set_index', async () => {
    h.createSession.mockResolvedValue({ id: 's2' })
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-40_yard_dash"]').trigger('click')
    await w.find('[data-testid="add-set-40_yard_dash"]').trigger('click')
    await w.find('[data-testid="add-set-40_yard_dash"]').trigger('click')
    await w.find('[data-testid="time_seconds-40_yard_dash-0"]').setValue(5.4)
    await w.find('[data-testid="time_seconds-40_yard_dash-1"]').setValue(5.2)
    await w.find('[data-testid="time_seconds-40_yard_dash-2"]').setValue(5.3)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()

    const [payload] = h.createSession.mock.calls[0]
    expect(payload.sets).toHaveLength(3)
    expect(payload.sets.map((s: { set_index: number; time_seconds: number }) => [s.set_index, s.time_seconds])).toEqual([
      [1, 5.4],
      [2, 5.2],
      [3, 5.3],
    ])
  })

  it('from a template: prefills rows and posts template_id', async () => {
    h.params = { athleteId: 'ath1', templateId: 't9' }
    h.getTemplate.mockResolvedValue({
      id: 't9',
      name: 'Monday - Circuit',
      type: 'circuit',
      rounds: 3,
      source: null,
      notes: null,
      created_at: null,
      items: [
        { id: 'i1', exercise_key: 'pushups', section: 'main', position: 0, target_reps: 15, target_duration_seconds: null, target_load_kg: null, target_distance_m: null, rest_seconds: null, variant: null, notes: null },
      ],
    })
    h.createSession.mockResolvedValue({ id: 's3' })
    const w = await mountLogger()

    expect(h.getTemplate).toHaveBeenCalledWith('t9', 'ath1')
    expect(w.find('[data-testid="from-template"]').text()).toContain('Monday - Circuit')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(true)

    await w.find('[data-testid="reps-pushups-0"]').setValue(14)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()
    const [payload] = h.createSession.mock.calls[0]
    expect(payload.template_id).toBe('t9')
    expect(payload.sets[0]).toMatchObject({ exercise_key: 'pushups', reps: 14 })
  })

  it('removes an added row', async () => {
    const w = await mountLogger()
    await w.find('[data-testid="add-exercise"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(true)
    await w.find('[data-testid="remove-pushups"]').trigger('click')
    expect(w.find('[data-testid="row-pushups"]').exists()).toBe(false)
  })
})
