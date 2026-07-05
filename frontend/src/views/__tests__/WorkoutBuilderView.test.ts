import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({
  createTemplate: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  isCoach: { value: true },
  loadRoles: vi.fn().mockResolvedValue(undefined),
  load: vi.fn().mockResolvedValue(undefined),
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
]

vi.mock('@/composables/useExercises', async () => {
  const { ref } = await import('vue')
  return { useExercises: () => ({ exercises: ref(catalog), load: h.load, loading: ref(false), error: ref(null) }) }
})
vi.mock('@/composables/useCoach', () => ({
  useRoles: () => ({ isCoach: h.isCoach, loadRoles: h.loadRoles }),
}))
vi.mock('@/composables/useWorkoutTemplates', () => ({
  createTemplate: (...a: unknown[]) => h.createTemplate(...a),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { athleteId: 'ath1' } }),
  useRouter: () => ({ push: h.push, replace: h.replace }),
  RouterLink: { template: '<a><slot /></a>' },
}))

beforeEach(() => {
  vi.clearAllMocks()
  h.isCoach.value = true
})

async function mountBuilder() {
  const WorkoutBuilderView = (await import('../WorkoutBuilderView.vue')).default
  const w = mount(WorkoutBuilderView, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return w
}

describe('WorkoutBuilderView', () => {
  it('redirects non-coaches', async () => {
    h.isCoach.value = false
    await mountBuilder()
    expect(h.replace).toHaveBeenCalledWith('/dashboard')
  })

  it('adds an exercise to a section via the picker', async () => {
    const w = await mountBuilder()
    await w.find('[data-testid="add-main"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect(w.find('[data-testid="item-pushups"]').exists()).toBe(true)
  })

  it('save is disabled until there is a name and an item', async () => {
    const w = await mountBuilder()
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(true)
    await w.find('[data-testid="tpl-name"]').setValue('Saturday Circuit')
    await w.find('[data-testid="add-main"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect((w.find('[data-testid="save"]').element as HTMLButtonElement).disabled).toBe(false)
  })

  it('saves a template with act-as, section, and lb→kg conversion', async () => {
    h.createTemplate.mockResolvedValue({ id: 't1' })
    const w = await mountBuilder()
    await w.find('[data-testid="tpl-name"]').setValue('Saturday Circuit')
    await w.find('[data-testid="add-main"]').trigger('click')
    await w.find('[data-testid="ex-farmers_carry"]').trigger('click')
    await w.find('[data-testid="load-lb"]').setValue(10)
    await w.find('[data-testid="save"]').trigger('click')
    await flushPromises()

    expect(h.createTemplate).toHaveBeenCalledTimes(1)
    const [payload, athleteId] = h.createTemplate.mock.calls[0]
    expect(athleteId).toBe('ath1')
    expect(payload.name).toBe('Saturday Circuit')
    expect(payload.items[0]).toMatchObject({
      exercise_key: 'farmers_carry',
      section: 'main',
      target_load_kg: 4.5, // 10 lb
    })
    expect(h.push).toHaveBeenCalledWith('/coach/ath1')
  })

  it('removes an added item', async () => {
    const w = await mountBuilder()
    await w.find('[data-testid="add-main"]').trigger('click')
    await w.find('[data-testid="ex-pushups"]').trigger('click')
    expect(w.find('[data-testid="item-pushups"]').exists()).toBe(true)
    await w.find('[data-testid="remove-pushups"]').trigger('click')
    expect(w.find('[data-testid="item-pushups"]').exists()).toBe(false)
  })
})
