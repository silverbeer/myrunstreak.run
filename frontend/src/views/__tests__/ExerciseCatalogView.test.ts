import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

const h = vi.hoisted(() => ({
  update: vi.fn(),
  create: vi.fn(),
  publish: vi.fn(),
  load: vi.fn().mockResolvedValue(undefined),
  loadRoles: vi.fn().mockResolvedValue(undefined),
  isCoach: { value: true },
  isAdmin: { value: false },
  userId: { value: 'me' as string | null },
  replace: vi.fn(),
}))

const mk = (over: Record<string, unknown>) => ({
  key: 'k', display_name: 'X', category: 'strength', measures: [], is_benchmark: false,
  owner_id: null, visibility: 'public', created_by: null, forked_from: null, aliases: [],
  movement_pattern: null, equipment: [], body_region: [], laterality: null, difficulty: null,
  tags: [], media_url: null, thumbnail_url: null, cues: [], instructions: null, ...over,
})
const catalog = ref([
  mk({ key: 'pushups', display_name: 'Push-ups' }), // canonical (owner null)
  mk({ key: 'my_move', display_name: 'My Move', owner_id: 'me', visibility: 'private' }), // mine
  mk({ key: 'her_move', display_name: 'Her Move', owner_id: 'u2', visibility: 'public' }), // someone else's
])

vi.mock('@/composables/useExercises', () => ({
  useExercises: () => ({
    exercises: catalog, loading: ref(false), error: ref(null),
    load: h.load, create: h.create, update: h.update, publish: h.publish,
  }),
}))
vi.mock('@/composables/useCoach', () => ({
  useRoles: () => ({ isCoach: h.isCoach, isAdmin: h.isAdmin, loadRoles: h.loadRoles }),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { id: h.userId.value } }),
}))
vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: h.replace }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  h.isCoach.value = true
  h.isAdmin.value = false
  h.userId.value = 'me'
})

async function mountView() {
  const View = (await import('../ExerciseCatalogView.vue')).default
  const w = mount(View)
  await flushPromises()
  return w
}

describe('ExerciseCatalogView', () => {
  it('redirects non-coaches', async () => {
    h.isCoach.value = false
    await mountView()
    expect(h.replace).toHaveBeenCalledWith('/dashboard')
  })

  it('coach: Edit only on own exercises', async () => {
    const w = await mountView()
    expect(w.find('[data-testid="edit-my_move"]').exists()).toBe(true)
    expect(w.find('[data-testid="edit-pushups"]').exists()).toBe(false) // canonical
    expect(w.find('[data-testid="edit-her_move"]').exists()).toBe(false) // not owned
  })

  it('admin: Edit on every exercise, including canonical', async () => {
    h.isAdmin.value = true
    const w = await mountView()
    expect(w.find('[data-testid="edit-pushups"]').exists()).toBe(true)
    expect(w.find('[data-testid="edit-her_move"]').exists()).toBe(true)
    expect(w.find('[data-testid="edit-my_move"]').exists()).toBe(true)
  })

  it('editing then saving calls update(key, patch) and closes the form', async () => {
    h.update.mockResolvedValue(mk({ key: 'my_move', display_name: 'Renamed', owner_id: 'me' }))
    const w = await mountView()
    await w.find('[data-testid="edit-my_move"]').trigger('click')
    expect(w.find('[data-testid="edit-form"]').exists()).toBe(true)

    await w.find('[data-testid="edit-name"]').setValue('Renamed')
    await w.find('[data-testid="edit-form"]').trigger('submit')
    await flushPromises()

    expect(h.update).toHaveBeenCalledTimes(1)
    expect(h.update.mock.calls[0][0]).toBe('my_move')
    expect(h.update.mock.calls[0][1]).toMatchObject({ display_name: 'Renamed' })
    expect(w.find('[data-testid="edit-form"]').exists()).toBe(false) // closed on success
  })
})
