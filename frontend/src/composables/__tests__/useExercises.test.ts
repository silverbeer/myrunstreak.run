import { describe, it, expect, vi, beforeEach } from 'vitest'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCallMock(...args),
}))

// Fresh module per test (mirrors useCoach tests) so nothing leaks between cases.
async function freshModule() {
  vi.resetModules()
  return import('../useExercises')
}

const exercise = (over: Record<string, unknown> = {}) => ({
  key: 'pushups',
  display_name: 'Push-ups',
  category: 'strength',
  visibility: 'public',
  owner_id: null,
  ...over,
})

beforeEach(() => apiCallMock.mockReset())

describe('useExercises', () => {
  it('load populates the catalog', async () => {
    apiCallMock.mockResolvedValue([exercise()])
    const { useExercises } = await freshModule()
    const { exercises, load } = useExercises()
    await load()
    expect(apiCallMock).toHaveBeenCalledWith('/workouts/exercises')
    expect(exercises.value).toHaveLength(1)
  })

  it('create POSTs and appends the new exercise', async () => {
    const created = exercise({ key: 'goblet_squat', display_name: 'Goblet Squat', visibility: 'private', owner_id: 'u1' })
    apiCallMock.mockResolvedValue(created)
    const { useExercises } = await freshModule()
    const { exercises, create } = useExercises()
    const result = await create({ display_name: 'Goblet Squat', category: 'strength' })
    expect(result).toEqual(created)
    expect(exercises.value).toContainEqual(created)
    const [path, opts] = apiCallMock.mock.calls[0]
    expect(path).toBe('/workouts/exercises')
    expect(opts.method).toBe('POST')
  })

  it('publish POSTs to the publish endpoint and updates the row in place', async () => {
    const priv = exercise({ key: 'goblet_squat', visibility: 'private', owner_id: 'u1' })
    const pub = { ...priv, visibility: 'public' }
    apiCallMock.mockResolvedValueOnce([priv]).mockResolvedValueOnce(pub)
    const { useExercises } = await freshModule()
    const { exercises, load, publish } = useExercises()
    await load() // seeds [priv]
    const result = await publish('goblet_squat')
    expect(apiCallMock).toHaveBeenLastCalledWith('/workouts/exercises/goblet_squat/publish', {
      method: 'POST',
    })
    expect(result?.visibility).toBe('public')
    expect(exercises.value.find((e) => e.key === 'goblet_squat')?.visibility).toBe('public')
  })
})
