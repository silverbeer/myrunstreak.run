import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const apiCallMock = vi.fn()
vi.mock('@/config/api', () => ({
  apiCall: (...args: unknown[]) => apiCallMock(...args),
}))

import CoachView from '../CoachView.vue'

const athlete = (id: string, name: string) => ({
  id,
  display_name: name,
  birth_year: 2012,
  linked_user_id: null,
  created_by: 'u',
  notes: null,
  created_at: '2026-07-01T00:00:00Z',
  profile: null,
})

const home = {
  athletes: [
    {
      athlete: athlete('a1', 'Gabe'),
      last_session_date: '2026-07-05',
      sessions_count: 3,
      latest_template_id: 't1',
      latest_template_name: 'Track Thursday',
      latest_template_created_at: '2026-07-08T12:00:00Z',
      needs_attention: true,
    },
    {
      athlete: athlete('a2', 'Maya'),
      last_session_date: '2026-07-10',
      sessions_count: 8,
      latest_template_id: null,
      latest_template_name: null,
      latest_template_created_at: null,
      needs_attention: false,
    },
  ],
  recent_sessions: [
    {
      id: 's1',
      athlete_id: 'a1',
      athlete_name: 'Gabe',
      session_date: '2026-07-05',
      type: 'intervals',
      template_id: 't1',
      template_name: 'Track Thursday',
      how_felt: 'strong through the 200s',
    },
  ],
  pending_invites: 2,
}

const globalStubs = { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } }

beforeEach(() => {
  apiCallMock.mockReset()
})

describe('CoachView (SB-266)', () => {
  it('renders athlete cards with training state + attention badge', async () => {
    apiCallMock.mockResolvedValue(home)
    const w = mount(CoachView, globalStubs)
    await flushPromises()

    expect(apiCallMock).toHaveBeenCalledWith('/coach/home')
    expect(w.text()).toContain('Gabe')
    expect(w.text()).toContain('workout waiting')
    expect(w.text()).toContain('Track Thursday')
    expect(w.text()).toContain('Coaching 2')
    expect(w.text()).toContain('2 pending invites')
  })

  it('renders the recent-activity feed', async () => {
    apiCallMock.mockResolvedValue(home)
    const w = mount(CoachView, globalStubs)
    await flushPromises()
    expect(w.text()).toContain('Recent activity')
    expect(w.text()).toContain('strong through the 200s')
  })

  it('shows the empty state with no athletes', async () => {
    apiCallMock.mockResolvedValue({ athletes: [], recent_sessions: [], pending_invites: 0 })
    const w = mount(CoachView, globalStubs)
    await flushPromises()
    expect(w.text()).toContain('No athletes yet')
  })
})
