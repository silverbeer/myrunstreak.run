import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AdminView from '../AdminView.vue'

// Hoisted mocks (vi.mock is hoisted above imports).
const h = vi.hoisted(() => ({
  inviteCoach: vi.fn(),
  listInvites: vi.fn(),
  loadRoles: vi.fn().mockResolvedValue(undefined),
  replace: vi.fn(),
  isAdmin: { value: true },
}))

vi.mock('@/composables/useCoach', () => ({
  useRoles: () => ({ isAdmin: h.isAdmin, loadRoles: h.loadRoles }),
  inviteCoach: (...a: unknown[]) => h.inviteCoach(...a),
  listInvites: () => h.listInvites(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ replace: h.replace }) }))

const invite = (over: Record<string, unknown> = {}) => ({
  id: 'i1',
  token: 'tok123',
  email: 'coach@x.com',
  created_by: 'admin',
  expires_at: '2099-01-01T00:00:00Z',
  grant_role: 'coach',
  athlete_id: null,
  redeemed_at: null,
  redeemed_by: null,
  created_at: '2026-07-01T00:00:00Z',
  ...over,
})

beforeEach(() => {
  vi.clearAllMocks()
  h.isAdmin.value = true
  h.listInvites.mockResolvedValue([])
})

describe('AdminView', () => {
  it('redirects non-admins to the dashboard', async () => {
    h.isAdmin.value = false
    mount(AdminView)
    await flushPromises()
    expect(h.replace).toHaveBeenCalledWith('/dashboard')
    expect(h.listInvites).not.toHaveBeenCalled()
  })

  it('renders the invite form and issued invites for an admin', async () => {
    h.listInvites.mockResolvedValue([invite(), invite({ id: 'i2', email: 'b@x.com', redeemed_at: '2026-07-02T00:00:00Z' })])
    const w = mount(AdminView)
    await flushPromises()
    expect(h.replace).not.toHaveBeenCalled()
    expect(w.text()).toContain('Invite a coach')
    expect(w.text()).toContain('coach@x.com')
    expect(w.text()).toContain('Pending') // active invite
    expect(w.text()).toContain('Redeemed') // redeemed invite
  })

  it('issues a coach invite and shows the copyable link', async () => {
    h.inviteCoach.mockResolvedValue(invite({ token: 'newtok' }))
    const w = mount(AdminView)
    await flushPromises()

    await w.find('input[type="email"]').setValue('coach@x.com')
    await w.find('form').trigger('submit')
    await flushPromises()

    expect(h.inviteCoach).toHaveBeenCalledWith('coach@x.com')
    expect(w.text()).toContain('/signup?invite=newtok')
    // list refreshed after issuing (once on mount, once after invite)
    expect(h.listInvites).toHaveBeenCalledTimes(2)
  })
})
