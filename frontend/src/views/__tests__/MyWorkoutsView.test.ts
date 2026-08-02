import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({ apiCall: (...a: unknown[]) => apiCallMock(...a) }))

const myAthlete: { value: unknown } = { value: null }
const loadMyAthlete = vi.fn(async () => {})
vi.mock('@/composables/useCoach', () => ({
  useMyAthlete: () => ({ myAthlete, loadMyAthlete }),
}))

const replaceMock = vi.fn()
const pushMock = vi.fn()
// The view now links to the build/log/print surfaces (SB-486), so the mock has
// to provide RouterLink as well as the router itself.
vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  // `to` is forwarded so tests can assert where a link actually goes.
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
}))

import MyWorkoutsView from '../MyWorkoutsView.vue'

const template = {
  id: 't1',
  user_id: 'coach',
  athlete_id: 'a1',
  created_by: 'coach',
  name: 'Monday At-Home',
  type: 'circuit',
  rounds: 1,
  source: 'Matthew',
  notes: null,
  items: [],
  created_at: '2026-07-20T00:00:00Z',
}

beforeEach(() => {
  apiCallMock.mockReset()
  loadMyAthlete.mockClear()
  replaceMock.mockClear()
  myAthlete.value = null
})

describe('MyWorkoutsView (SB-332)', () => {
  it('redirects a non-athlete to the dashboard without fetching', async () => {
    myAthlete.value = null
    mount(MyWorkoutsView)
    await flushPromises()
    expect(replaceMock).toHaveBeenCalledWith('/dashboard')
    expect(apiCallMock).not.toHaveBeenCalled()
  })

  it('renders assigned workouts for a linked athlete', async () => {
    myAthlete.value = { id: 'a1', display_name: 'Gabe' }
    apiCallMock.mockImplementation((path: string) => {
      if (path === '/me/workouts') return Promise.resolve([template])
      if (path === '/workouts/exercises') return Promise.resolve([])
      return Promise.reject(new Error(`unexpected: ${path}`))
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.text()).toContain('Monday At-Home')
    expect(w.text()).toContain('Coached by Matthew')
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('shows the empty state when nothing is assigned', async () => {
    myAthlete.value = { id: 'a1', display_name: 'Gabe' }
    apiCallMock.mockImplementation((path: string) => {
      if (path === '/me/workouts') return Promise.resolve([])
      if (path === '/workouts/exercises') return Promise.resolve([])
      return Promise.reject(new Error('unexpected'))
    })
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.text()).toContain('No workouts yet')
  })
})

describe('MyWorkoutsView — ad-hoc entry (SB-531)', () => {
  it('offers logging a workout with no plan behind it', async () => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
    apiCallMock.mockResolvedValue([])
    const w = mount(MyWorkoutsView)
    await flushPromises()
    const link = w.get('[data-testid="log-adhoc"]')
    expect(link.attributes('href')).toBe('/my/workouts/log')
    expect(w.text()).toContain('Did a workout on your own?')
  })

  it('demotes building a plan — it was the loudest control and the wrong verb', async () => {
    myAthlete.value = { id: 'ath1', linked_user_id: 'u1' }
    apiCallMock.mockResolvedValue([])
    const w = mount(MyWorkoutsView)
    await flushPromises()
    expect(w.text()).toContain('+ Build a workout')
    expect(w.text()).not.toContain('+ New workout')
  })
})
